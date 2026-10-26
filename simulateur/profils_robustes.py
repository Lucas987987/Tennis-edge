"""Candidats contrôlés pour récence, shrinkage et joueurs peu documentés.

Le champion reste le profil hiérarchique actuel. Les challengers changent seulement
la demi-vie et la force du prior ; les matchs, l'ordre temporel et la période de
confirmation sont identiques pour tous. Aucun marché n'est utilisé.
"""
import argparse
import datetime as dt
import heapq
import json
import math
import os

import donnees
import match_simule as MS
import profils_service as PS
import stabilite as ST

CANDIDATS = {
    'champion': {'demi_vie': 365, 'prior_mult': 1.0},
    'recent': {'demi_vie': 180, 'prior_mult': 1.0},
    'prudent': {'demi_vie': 365, 'prior_mult': 2.0},
    'recent_prudent': {'demi_vie': 180, 'prior_mult': 2.0},
}
GROUPES = ('global', 'tres_peu_documente', 'peu_documente', 'documente',
           'transition_surface', 'retour_absence', 'best_of_5')


def _pertes():
    return {g: [] for g in GROUPES}


def _resume(L):
    if not L:
        return {'n': 0, 'log_loss': None, 'brier': None}
    # L'orientation fixe met le futur vainqueur à home : p = exp(-log_loss du match).
    brier = [(1-math.exp(-perte))**2 for perte in L]
    return {'n': len(L), 'log_loss': round(sum(L)/len(L), 6),
            'brier': round(sum(brier)/len(brier), 6)}


def selection(M, debut, maximum):
    """Sélection déterministe commune à tous les candidats, avant de voir leurs prévisions."""
    eligibles = [m for m in M if m['date'] >= debut and m.get('detail') and m.get('complet')
                 and not m.get('abandon') and m.get('sets') and m['circuit'] in ('ATP', 'WTA', 'CH', 'ITF')]
    if len(eligibles) <= maximum:
        return {id(m) for m in eligibles}
    pas = len(eligibles) / maximum
    return {id(eligibles[min(len(eligibles)-1, int(i*pas))]) for i in range(maximum)}


def evaluer_candidat(M, choisis, reglage, coupure, sigma=.15):
    P = PS.Profils(reglage['demi_vie'], reglage['prior_mult'])
    attente, serial = [], 0
    surfaces, derniers = {}, {}
    dec, conf = _pertes(), _pertes()
    for m in M:
        debut = dt.datetime.combine(m['date'], dt.time())
        while attente and attente[0][0] < debut:
            _, _, ancien = heapq.heappop(attente)
            P.ajouter(ancien)
        if id(m) in choisis:
            h, a = m['gagnant'], m['perdant']  # orientation fixe : le futur vainqueur est home
            ph, nh = P.profil(h, m['circuit'], m['surface'], m['date'])
            pa, na = P.profil(a, m['circuit'], m['surface'], m['date'])
            mu = P.moyenne(m['circuit'], m['surface'])
            cH, cA = MS.composantes(ph, pa, mu), MS.composantes(pa, ph, mu)
            p = MS.victoire_pure(cH, cA, m['bo']//2+1, sigma)
            perte = -math.log(min(1-1e-12, max(1e-12, p)))
            groupes = ['global']
            minimum_documentation = min(nh, na)
            if minimum_documentation < 100:
                groupes.append('tres_peu_documente')
            if minimum_documentation < 500:
                groupes.append('peu_documente')
            else:
                groupes.append('documente')
            if any(j in surfaces and surfaces[j] != m['surface'] for j in (h, a)):
                groupes.append('transition_surface')
            if any(j in derniers and (m['date']-derniers[j]).days > 45 for j in (h, a)):
                groupes.append('retour_absence')
            if m['bo'] == 5:
                groupes.append('best_of_5')
            cible = dec if m['date'] < coupure else conf
            for g in groupes:
                cible[g].append(perte)
        heapq.heappush(attente, (dt.datetime.combine(m['fin'], dt.time()), serial, m))
        serial += 1
        for j in (m['gagnant'], m['perdant']):
            surfaces[j] = m['surface']
            derniers[j] = m['date']
    return {'reglage': dict(reglage),
            'decouverte': {g: _resume(L) for g, L in dec.items()},
            'confirmation': {g: _resume(L) for g, L in conf.items()}}


def _verdict(rapports, champion='champion'):
    base = rapports[champion]
    eligibles = [n for n in CANDIDATS if n != champion
                 and (rapports[n]['decouverte']['global']['n'] or 0) >= 100
                 and (rapports[n]['confirmation']['global']['n'] or 0) >= 100]
    if not eligibles:
        return None, {'adopte': False, 'raison': 'échantillon insuffisant', 'll': {}}
    nom = min(eligibles, key=lambda n: rapports[n]['decouverte']['global']['log_loss'])
    r = rapports[nom]
    gain = base['confirmation']['global']['log_loss'] - r['confirmation']['global']['log_loss']
    controles = {}
    for groupe in ('peu_documente', 'tres_peu_documente'):
        b, c = base['confirmation'][groupe], r['confirmation'][groupe]
        # Le groupe très pauvre est facultatif s'il est absent ; s'il est présent, 30 matchs minimum.
        assez = c['n'] >= 30 or (groupe == 'tres_peu_documente' and c['n'] == 0)
        ok = assez and c['log_loss'] <= b['log_loss'] + .001
        controles[groupe] = {'n': c['n'], 'gain_log_loss': round(b['log_loss']-c['log_loss'], 6) if assez else None,
                             'delta_brier': round(c['brier']-b['brier'], 6) if assez else None,
                             'brier_avec': c['brier'], 'brier_sans': b['brier'],
                             'minimum_matchs': 30, 'ok': ok}
    faible_ok = all(x['ok'] for x in controles.values())
    return nom, {
        'adopte': gain >= ST.MARGE and faible_ok,
        'raison': f"gain confirmation {gain:+.6f} ; profils peu documentés {'validés' if faible_ok else 'non validés'}",
        'll': {'avec': r['confirmation']['global']['log_loss'], 'sans': base['confirmation']['global']['log_loss']},
        'controles_sous_groupes': controles,
        **CANDIDATS[nom], 'challenger': nom,
    }


def main(archive, racine='.', maximum=2000, coupure=dt.date(2025, 1, 1), debut=dt.date(2024, 1, 1)):
    M = donnees.charger(archive, 2021)
    choisis = selection(M, debut, maximum)
    rapports = {}
    for nom, reglage in CANDIDATS.items():
        print('Profils :', nom, flush=True)
        rapports[nom] = evaluer_candidat(M, choisis, reglage, coupure)
    nom, verdict = _verdict(rapports, champion)
    choix_path = os.path.join(racine, 'simulateur', 'choix_simulation.json')
    try:
        choix = json.load(open(choix_path, encoding='utf-8'))
    except (OSError, ValueError):
        choix = {}
    ancien = choix.get('profils_hierarchiques') or {}
    champion = ancien.get('challenger') if ancien.get('adopte') and ancien.get('challenger') in CANDIDATS else 'champion'
    etat_path = os.path.join(racine, 'simulateur', 'stabilite.json')
    etat = ST.lire(etat_path)
    decision = ST.appliquer(etat, 'profils_hierarchiques', ancien, verdict,
                            params=('demi_vie', 'prior_mult', 'challenger'))
    choix['profils_hierarchiques'] = decision
    ST.ecrire(etat, etat_path)
    json.dump(choix, open(choix_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    out = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(),
           'coupure_decouverte_confirmation': coupure.isoformat(), 'matchs_selectionnes': len(choisis),
           'regle': 'Challenger choisi sur découverte ; adoption seulement après confirmation, marge et deux semaines.',
           'champion_compare': champion, 'candidats': rapports, 'decision': decision}
    path = os.path.join(racine, 'simulateur', 'rapport_profils_robustes.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('Décision profils :', decision['stabilite'], flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('archive')
    ap.add_argument('--racine', default='.')
    ap.add_argument('--max', type=int, default=2000)
    args = ap.parse_args()
    main(args.archive, args.racine, args.max)
