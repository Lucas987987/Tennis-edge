"""Interactions service–retour horodatées, évaluées comme challenger indépendant.

Un profil n'existe qu'avec les feuilles dont le tournoi est terminé avant le match.
L'interaction est symétrique et ne consulte ni cote ni résultat du match courant.
Le champion reste la victoire pure des profils hiérarchiques ; aucune promotion automatique.
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
import profils_robustes as PR

LAMBDAS = (0.0, .005, .01, .02)
MIN_DECOUVERTE = 100
MIN_CONFIRMATION = 100
MARGE = .001


def _lg(p):
    p = min(max(float(p), 1e-6), 1-1e-6)
    return math.log(p/(1-p))


def _sg(z):
    return 1/(1+math.exp(-max(-40, min(40, z))))


def instantane(P, joueur, circuit, surface, jour):
    """Photographie pré-match explicite : jour de validité et documentation effective."""
    profil, n = P.profil(joueur, circuit, surface, jour)
    return {'joueur': joueur, 'disponible_avant': jour.isoformat(), 'balles_effectives': round(n, 2),
            'profil': profil}


def _force_service(p):
    return .60*p['w1'] + .40*p['w2j']


def _faiblesse_retour(p):
    # r1/r2j sont les points gagnés par le serveur adverse : haut = retour plus perméable.
    return .60*p['r1'] + .40*p['r2j']


def interaction(ph, pa, mu):
    """Interaction de styles, centrée sur le circuit et bornée contre les profils extrêmes."""
    sh, sa = (_force_service(ph)-_force_service(mu))/.05, (_force_service(pa)-_force_service(mu))/.05
    ra, rh = (_faiblesse_retour(pa)-_faiblesse_retour(mu))/.05, (_faiblesse_retour(ph)-_faiblesse_retour(mu))/.05
    return max(-4.0, min(4.0, sh*ra-sa*rh))


def evaluer(M, choisis, coupure, demi_vie=PS.DEMI_VIE, prior_mult=1.0, sigma=.15):
    P = PS.Profils(demi_vie, prior_mult)
    attente, serial = [], 0
    pertes = {x: {'decouverte': [], 'confirmation': []} for x in LAMBDAS}
    for m in M:
        debut = dt.datetime.combine(m['date'], dt.time())
        while attente and attente[0][0] < debut:
            _, _, ancien = heapq.heappop(attente)
            P.ajouter(ancien)  # disponible seulement après la fin réelle du tournoi
        if id(m) in choisis:
            h, a = m['gagnant'], m['perdant']  # orientation fixe du backtest, comme le champion
            ih, ia = instantane(P, h, m['circuit'], m['surface'], m['date']), instantane(P, a, m['circuit'], m['surface'], m['date'])
            mu = P.moyenne(m['circuit'], m['surface'])
            ch, ca = MS.composantes(ih['profil'], ia['profil'], mu), MS.composantes(ia['profil'], ih['profil'], mu)
            p0 = MS.victoire_pure(ch, ca, m['bo']//2+1, sigma)
            z = interaction(ih['profil'], ia['profil'], mu)
            periode = 'decouverte' if m['date'] < coupure else 'confirmation'
            for lam in LAMBDAS:
                p = _sg(_lg(p0)+lam*z)
                pertes[lam][periode].append(-math.log(min(1-1e-12, max(1e-12, p))))
        heapq.heappush(attente, (dt.datetime.combine(m['fin'], dt.time()), serial, m))
        serial += 1
    return {str(lam): {periode: PR._resume(vals) for periode, vals in groupes.items()}
            for lam, groupes in pertes.items()}


def decider(rapports):
    base = rapports[str(0.0)]
    eligibles = [x for x in LAMBDAS if x and rapports[str(x)]['decouverte']['n'] >= MIN_DECOUVERTE
                 and rapports[str(x)]['confirmation']['n'] >= MIN_CONFIRMATION]
    if not eligibles:
        return {'adopte': False, 'challenger': None, 'raison': 'échantillon insuffisant ; champion inchangé'}
    meilleur = min(eligibles, key=lambda x: rapports[str(x)]['decouverte']['log_loss'])
    gain = base['confirmation']['log_loss']-rapports[str(meilleur)]['confirmation']['log_loss']
    return {'adopte': gain >= MARGE, 'challenger': 'interaction_service_retour', 'lambda': meilleur,
            'gain_log_loss_confirmation': round(gain, 6), 'marge': MARGE,
            'll_champion': base['confirmation']['log_loss'], 'll_challenger': rapports[str(meilleur)]['confirmation']['log_loss'],
            'raison': 'challenger choisi sur découverte seulement, puis jugé sur confirmation disjointe'}


def main(archive, racine='.', maximum=2000, coupure=dt.date(2025, 1, 1), debut=dt.date(2024, 1, 1)):
    M = donnees.charger(archive, 2021)
    choisis = PR.selection(M, debut, maximum)
    try:
        choix = json.load(open(os.path.join(racine, 'simulateur', 'choix_simulation.json'), encoding='utf-8'))
        reglage = choix.get('profils_hierarchiques') or {}
        actif = reglage if reglage.get('adopte') else {}
    except (OSError, ValueError):
        actif = {}
    demi_vie = actif.get('demi_vie', PS.DEMI_VIE)
    prior_mult = actif.get('prior_mult', 1.0)
    rapports = evaluer(M, choisis, coupure, demi_vie=demi_vie, prior_mult=prior_mult)
    out = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(),
           'champion_profil': {'demi_vie': demi_vie, 'prior_mult': prior_mult},
           'coupure': coupure.isoformat(), 'n': len(choisis), 'lambdas': list(LAMBDAS),
           'regle': 'profils disponibles après fin des matchs seulement ; aucune variable de marché ; champion inchangé par ce rapport',
           'candidats': rapports, 'decision': decider(rapports)}
    path = os.path.join(racine, 'simulateur', 'rapport_styles_joueurs.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('Styles :', out['decision'], flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('archive')
    ap.add_argument('--racine', default='.')
    ap.add_argument('--max', type=int, default=2000)
    args = ap.parse_args()
    main(args.archive, args.racine, args.max)
