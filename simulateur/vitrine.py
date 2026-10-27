#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vitrine.py — les données du site public de l'algorithme (23/10/2026) : algo/donnees.json.

Le site public (algo/index.html, en français et en anglais) montre :
  — chaque match des prochaines heures en entier : % de victoire, cote juste (1 / %), sets, scores
    probables, feuille prévue et scénario représentatif rejouable point par point ;
  — le MATCH DU JOUR, toujours choisi séparément par sa règle fixe, sans influencer les autres simulations ;
  — le BILAN PUBLIC : tous les matchs pronostiqués depuis le début du journal, sans tri, pertes comprises ;
  — la CALIBRATION : ce que l'algo annonçait contre ce qui s'est passé (en direct, et rejoué hors échantillon).

Préversion Plus : le détail complet (sets, scores, feuille, simulation) est publié pour TOUS les matchs afin
de tester le catalogue et les parcours. Si une offre payante est activée plus tard, les éléments réservés
devront être déplacés vers un service à accès contrôlé : un simple masquage visuel ne protégerait pas ce JSON.

Rien d'autre ne sort : ni cote de bookmaker, ni signal d'alerte, ni canal privé. L'algo est une source
indépendante : il ne regarde pas le marché, le site non plus.

Règle du MATCH DU JOUR (fixée le 23/10/2026, avant toute publication) : parmi les matchs du jour (heure de
Paris) pas encore commencés au premier passage, ATP et WTA d'abord (Challenger seulement s'il n'y a rien
d'autre) ; l'affiche la plus forte = la plus grande somme des Elo des deux joueurs. Une fois choisi, le match
du jour ne change plus de la journée. La confiance de l'algo n'entre JAMAIS dans le choix : sinon le bilan
serait trié.

Règle du BILAN (fixée le 23/10/2026) : chaque match ATP, WTA et Challenger du journal depuis le 21/10/2026
(début du journal, premier pronostic jamais modifié), jugé sur le DERNIER pronostic affiché avant le début du
match (à défaut, le premier). Abandons et forfaits exclus (ils ne jugent pas un pronostic).
Usage : python simulateur/vitrine.py [racine]
"""
import datetime as dt
import gzip
import json
import math
import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join('algo', 'donnees.json')
DEBUT_BILAN = '2026-10-21'
CIRCUITS = ('ATP', 'WTA', 'CH')
VERSIONS = ('combinaison', 'simulation', 'stats')
BACS = [i / 10 for i in range(11)]
PARIS = dt.timezone(dt.timedelta(hours=2))          # remplacé par zoneinfo si disponible


def _paris():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo('Europe/Paris')
    except Exception:  # noqa: BLE001
        return PARIS


# joueur pas encore connu (« vainqueur du quart 1 ») : pas de pronostic public
PROVISOIRE = re.compile(r'^(?:W|L)(?:QF|SF|F|R\d+|Q)\d*$|^(?:TBD|TBA|Qualifier)$', re.I)


def connu(m):
    return not (PROVISOIRE.match(str(m.get('home') or '').strip()) or PROVISOIRE.match(str(m.get('away') or '').strip()))


def _lire(chemin, defaut=None):
    try:
        with open(chemin, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def version(m):
    """Version affichée d'un pronostic : Simulation + Elo, sinon simulation, sinon Elo."""
    for k in VERSIONS:
        v = m.get(k)
        if isinstance(v, dict) and v.get('p_home') is not None:
            return k, v
    return None, None


def cote(p):
    return round(1 / p, 2) if p and p > 0.001 else None


def _utc(s):
    d = dt.datetime.fromisoformat(str(s))
    return d.replace(tzinfo=dt.timezone.utc) if d.tzinfo is None else d


def jour_paris(s):
    return _utc(s).astimezone(_paris()).date().isoformat()


def elo_de(etat, cle):
    j = ((etat or {}).get('joueurs') or {}).get(cle) or {}
    return float(j.get('elo') or 1200.0)


def choisir_match_du_jour(matchs, etat, maintenant, precedent=None):
    """Règle fixe (voir l'en-tête). precedent : le choix déjà publié (gardé toute la journée)."""
    jour = maintenant.astimezone(_paris()).date().isoformat()
    if precedent and precedent.get('jour') == jour and any(m['uid'] == precedent.get('uid') for m in matchs):
        return precedent
    du_jour = [m for m in matchs if jour_paris(m['debut']) == jour and _utc(m['debut']) > maintenant
               and m.get('circuit') in CIRCUITS and version(m)[1]]
    if not du_jour:
        return None
    principal = [m for m in du_jour if m['circuit'] in ('ATP', 'WTA')]
    pool = principal or du_jour
    cles = lambda m: (m.get('cles') or [None, None])
    m = max(pool, key=lambda x: (elo_de(etat, cles(x)[0]) + elo_de(etat, cles(x)[1]), x['uid']))
    return {'jour': jour, 'uid': m['uid'],
            'elo': [round(elo_de(etat, cles(m)[0])), round(elo_de(etat, cles(m)[1]))]}


def _feuille_prevue(v):
    f = ((v.get('match_simule') or {}).get('feuille')) or []
    out = []
    for j in f[:2]:
        out.append({k: round((j.get(k) or {}).get('moy'), 1) for k in
                    ('aces', 'doubles_fautes', 'breaks', 'premiere_pct', 'jeux_service_gagnes_pct')
                    if isinstance(j.get(k), dict) and j[k].get('moy') is not None})
    return out or None


def _scores_public(v):
    """Scores des simulations de CETTE variante ; calcul exact seulement en repli."""
    sim = v.get('match_simule') or {}
    return (sim.get('scores') or v.get('scores_probables') or [])[:3]


def ligne_match(m, complet):
    k, v = version(m)
    p = float(v['p_home'])
    out = {'uid': m['uid'], 'debut': m['debut'], 'tournoi': m.get('tournoi'), 'circuit': m.get('circuit'),
           'surface': m.get('surface'), 'meilleur_des': m.get('meilleur_des', 3),
           'home': m['home'], 'away': m['away'], 'p_home': round(p, 3), 'version': k,
           'fiabilite': m.get('fiabilite'), 'cotes_justes': [cote(p), cote(1 - p)]}
    if not complet:
        out['simulation_disponible'] = False
        return out
    d = m.get('direct') or {}
    sim = v.get('match_simule') or {}
    out.update({
        'simulation_disponible': bool(d.get('a') and d.get('b') and sim.get('match_type')),
        'sets': v.get('sets'),
        'scores_probables': _scores_public(v),
        'jeux_moyen': v.get('jeux_moyen'),
        'tiebreak': v.get('tiebreak'),
        'set1_home': v.get('set1_home'),
        'feuille_prevue': _feuille_prevue(v),
        'simulation': ({'a': round(d['a'], 4), 'b': round(d['b'], 4),
                        'sets_gagnants': int(d.get('sets_gagnants') or (3 if m.get('meilleur_des') == 5 else 2)),
                        'tb_final': int(d.get('tb_final') or 7), 'n': int(sim.get('n') or 0),
                        'version': k, 'scenario': sim.get('match_type'),
                        'stabilite_score': sim.get('stabilite_score')}
                       if d.get('a') and d.get('b') else None),
    })
    return out


def _juge(m):
    """(p_home, gagnant) du pronostic jugé : dernier avant le match, sinon premier."""
    for bloc in ('dernier', 'premier'):
        b = m.get(bloc) or {}
        for k in VERSIONS:
            v = b.get(k)
            if isinstance(v, dict) and v.get('p_home') is not None and v.get('vainqueur_juste') is not None:
                return float(v['p_home']), k
    return None, None


def _mesures(points):
    """points : [(p annoncée pour le vainqueur RÉEL… non : p_home, y_home)]."""
    n = len(points)
    if not n:
        return None
    eps = 1e-6
    brier = sum((p - y) ** 2 for p, y in points) / n
    ll = -sum(y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps)) for p, y in points) / n
    ok = sum(1 for p, y in points if (p > 0.5) == (y == 1))
    return {'n': n, 'vainqueurs': ok, 'pct': round(100 * ok / n, 1), 'brier': round(brier, 4),
            'log_loss': round(ll, 4)}


def calibration(points, n_min=20):
    """Vu des DEUX joueurs : chaque match compte deux fois (p et 1 − p)."""
    deux = []
    for p, y in points:
        deux += [(p, y), (1 - p, 1 - y)]
    out = []
    for lo, hi in zip(BACS, BACS[1:]):
        s = [(p, y) for p, y in deux if lo <= p < hi or (hi == 1.0 and p == 1.0)]
        if len(s) >= n_min:
            out.append({'de': lo, 'a': hi, 'n': len(s), 'prevu': round(100 * sum(p for p, _ in s) / len(s), 1),
                        'reel': round(100 * sum(y for _, y in s) / len(s), 1)})
    return out


def bilan(resultats, debut=DEBUT_BILAN, seulement=None):
    lignes, points, par_c, par_jour = [], [], {}, {}
    for m in (resultats or {}).get('matchs') or []:
        if m.get('circuit') not in CIRCUITS or str(m.get('debut'))[:10] < debut or not connu(m):
            continue
        if seulement and not seulement(m):
            continue
        reel = m.get('reel') or {}
        if reel.get('interrompu') or reel.get('gagnant') not in ('home', 'away'):
            continue
        p, k = _juge(m)
        if p is None:
            continue
        y = 1 if reel['gagnant'] == 'home' else 0
        points.append((p, y))
        par_c.setdefault(m['circuit'], []).append((p, y))
        par_jour.setdefault(jour_paris(m['debut']), []).append((p, y))
        lignes.append({'debut': m['debut'], 'tournoi': m.get('tournoi'), 'circuit': m['circuit'],
                       'home': m['home'], 'away': m['away'], 'p_home': round(p, 3),
                       'gagnant': reel['gagnant'], 'score': reel.get('score'), 'juste': (p > 0.5) == (y == 1),
                       'fiabilite': m.get('fiabilite')})
    lignes.sort(key=lambda x: x['debut'], reverse=True)
    cumul, courbe = [], []
    for j in sorted(par_jour):
        cumul += par_jour[j]
        mm = _mesures(cumul)
        courbe.append({'jour': j, 'n': mm['n'], 'pct': mm['pct']})
    return {'depuis': debut, 'global': _mesures(points),
            'par_circuit': {c: _mesures(v) for c, v in par_c.items()},
            'calibration': calibration(points), 'courbe': courbe, 'derniers': lignes[:40]}


def rejoue(racine):
    """Calibration rejouée hors échantillon (entrainement_progressif.py : chaque semaine prédite avec un modèle
    entraîné sur les semaines d'avant). Version Simulation + Elo."""
    p = os.path.join(racine, 'simulateur', 'pronostics_hors_echantillon.jsonl.gz')
    points, jours = [], []
    try:
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            for l in f:
                r = json.loads(l)
                if r.get('circuit') in CIRCUITS and r.get('p_algo') is not None:
                    points.append((float(r['p_algo']), 1 if r['gagnant'] == 'home' else 0))
                    jours.append(r['jour'])
    except (OSError, ValueError):
        return None
    if not points:
        return None
    return {'du': min(jours), 'au': max(jours), 'global': _mesures(points), 'calibration': calibration(points)}


def validation_fiabilite(resultats):
    """Cohorte strictement prospective de la fiabilité circuit.

    Une note recalculée sur un match déjà journalisé ne le fait pas entrer dans
    cette cohorte : la date du premier enregistrement doit elle aussi suivre
    l'activation. Les probabilités et le bilan historique restent inchangés.
    """
    sys.path.insert(0, ICI)
    from fiabilite import ACTIVE_LE, VERSION_FIABILITE

    def eligible(m):
        f = m.get('fiabilite') or {}
        return (f.get('version_fiabilite') == VERSION_FIABILITE
                and str(m.get('pronostique_le') or '')[:10] >= ACTIVE_LE)

    out = bilan(resultats, debut=ACTIVE_LE, seulement=eligible)
    out.update({'version': VERSION_FIABILITE, 'depuis': ACTIVE_LE,
                'regle': "Premiers pronostics enregistrés après activation, portant la version circuit_v1 ; aucun ancien match recalculé."})
    return out


def qualite_donnees(racine):
    from qualite_donnees import auditer
    doc = _lire(os.path.join(racine, 'simulateur', 'profils_service.json'), {}) or {}
    return auditer(doc)


def construire(racine, maintenant=None):
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    pron = _lire(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics.json'), {}) or {}
    etat = _lire(os.path.join(racine, 'simulateur', 'elo_etat.json'), {})
    sys.path.insert(0, ICI)
    import elo as E
    etat = E.migrer_etat(etat)
    precedent = (_lire(os.path.join(racine, SORTIE), {}) or {}).get('match_du_jour')
    matchs = [m for m in pron.get('matchs') or [] if m.get('circuit') in CIRCUITS and version(m)[1] and connu(m)]
    mdj = choisir_match_du_jour(matchs, etat, maintenant, precedent)
    a_venir = sorted((m for m in matchs if _utc(m['debut']) > maintenant - dt.timedelta(hours=3)),
                     key=lambda m: (m['debut'], m['uid']))
    lignes = [ligne_match(m, complet=True) for m in a_venir]
    resultats = _lire(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), {})
    return {'genere_le': maintenant.isoformat(timespec='seconds'), 'pronostics_du': pron.get('genere_le'),
            'simulations': pron.get('simulations') or 20000, 'match_du_jour': mdj,
            'matchs': lignes, 'bilan': bilan(resultats),
            'validation_fiabilite': validation_fiabilite(resultats),
            'qualite_donnees': qualite_donnees(racine),
            'rejoue': rejoue(racine)}


def main(argv):
    racine = argv[1] if len(argv) > 1 else os.path.join(ICI, '..')
    doc = construire(racine)
    from validation_vitrine import valider
    valider(doc, int(os.environ.get('SIMULATIONS', '20000')))
    os.makedirs(os.path.join(racine, 'algo'), exist_ok=True)
    destination = os.path.join(racine, SORTIE)
    temporaire = destination + '.tmp'
    with open(temporaire, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(temporaire, destination)
    b = (doc['bilan'] or {}).get('global') or {}
    print(f"Site public : {len(doc['matchs'])} matchs · match du jour {(doc['match_du_jour'] or {}).get('uid')} · "
          f"bilan {b.get('vainqueurs')}/{b.get('n')} ({b.get('pct')} %)")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
