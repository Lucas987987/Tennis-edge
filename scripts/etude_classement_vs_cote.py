#!/usr/bin/env python3
"""etude_classement_vs_cote.py — jouer l'écart entre le classement marché
d'un joueur et sa cote du jour ?

    python scripts/etude_classement_vs_cote.py

LECTURE SEULE. N'écrit rien, ne sort pas sur le réseau, relançable.

LA QUESTION (Lucas, 09/10)
--------------------------
Le classement marché d'un joueur, c'est la médiane de ses cotes. Le jour
d'un match, il a une cote réelle. Si les deux divergent, faut-il jouer ?

  RÈGLE A — cote du jour PLUS BASSE que son classement
            (le marché le voit plus fort que d'habitude : « match facile »)
  RÈGLE B — cote du jour PLUS HAUTE que son classement
            (le marché le voit plus faible que d'habitude : « sous-coté
             par rapport à son niveau »)

CE QUI DIFFÈRE D'etude_difficulte_tous.py
-----------------------------------------
Cette étude-là mesurait un résidu contre la cote JUSTE (marge retirée), et
d'un seul côté de chaque match, tiré par ordre alphabétique. Ici :

  — les DEUX joueurs de chaque match sont évalués, chacun contre SA médiane ;
  — le gain est calculé au prix RÉEL Pinnacle, marge comprise, mise 1 :
    c'est ce qu'on aurait encaissé, pas une mesure de calibration.

MÉDIANE POINT-IN-TIME
---------------------
La médiane d'un joueur, lue le jour d'un match, ne contient que ses matchs
STRICTEMENT antérieurs (au moins MIN_COTES). La médiane de la fiche, elle,
contient tout — l'utiliser ici serait regarder l'avenir.

PRIX : la dernière cote Pinnacle avant le coup d'envoi (coupe pré-match),
celle des courbes. Résultat cherché dans les FENETRE_JOURS suivants.

LIRE LES RÉSULTATS HONNÊTEMENT
------------------------------
Quatre seuils × deux règles = huit essais. Sur huit essais sans aucun
effet réel, il y a environ une chance sur trois qu'au moins un « exclue
zéro » par hasard. Une règle ne compte que si elle tient : aux seuils
voisins, sur les deux moitiés de la période, et sur les matchs à venir.
"""

import math
import os
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import player_form as pf                                    # noqa: E402
import etude_difficulte_tous as edt                         # noqa: E402

MIN_COTES = int(os.environ.get('MIN_COTES', '4'))
SEUILS = (5, 10, 15, 20)


def cotes_pinnacle():
    """{(paire, date): {cle: (cote_brute, proba_juste)}} — clôture pré-match.

    Même lecture que player_form.cotes_sharp(), mais on garde le prix
    BRUT des deux côtés : c'est à ce prix-là qu'on aurait joué.
    """
    ref = {}
    for src in (os.environ.get('CURVES', 'book_curves_live.jsonl'),
                'book_curves.jsonl'):
        try:
            lignes = list(pf.ov.open_curves(src, verbose=False))
        except Exception:
            continue
        for ligne in lignes:
            try:
                r = pf.json.loads(ligne)
            except Exception:
                continue
            if r.get('book') != pf.SHARP:
                continue
            ct = pf._dt(r.get('commence_time'))
            if not ct:
                continue
            h = [q for q in (r.get('home_curve') or [])
                 if q and q[1] and pf._dt(q[0]) and pf._dt(q[0]) < ct]
            a = [q for q in (r.get('away_curve') or [])
                 if q and q[1] and pf._dt(q[0]) and pf._dt(q[0]) < ct]
            if not h or not a:
                continue
            ka = pf.cle_joueur(r.get('home_team') or r.get('home'))
            kb = pf.cle_joueur(r.get('away_team') or r.get('away'))
            if not ka or not kb or ka == kb:
                continue
            try:
                oh, oa = float(h[-1][1]), float(a[-1][1])
            except (TypeError, ValueError):
                continue
            if oh <= 1 or oa <= 1:
                continue
            ih, ia = 1 / oh, 1 / oa
            ref[(frozenset((ka, kb)), ct.date())] = {
                ka: (oh, ih / (ih + ia)), kb: (oa, ia / (ih + ia))}
    return ref


def construire(ref, R):
    """Un pari possible par JOUEUR et par match coté et dénoué."""
    par_jour = defaultdict(list)
    for (paire, d), cotes in ref.items():
        par_jour[d].append((paire, cotes))

    hist = defaultdict(list)
    P = []
    sans_res = ambigus = 0
    for jour in sorted(par_jour):
        for paire, cotes in par_jour[jour]:
            c = [r for r in R.get(paire, [])
                 if 0 <= (r[0] - jour).days <= edt.FENETRE_JOURS]
            if not c:
                sans_res += 1
                continue
            if len({r[1] for r in c}) > 1:
                ambigus += 1
                continue
            vainqueur = c[0][1]
            for j, (cote, p) in cotes.items():
                if len(hist[j]) < MIN_COTES:
                    continue
                med = st.median(hist[j])
                gagne = vainqueur == j
                P.append({
                    'd': jour, 'j': j, 'paire': paire,
                    'cote': cote, 'p': p, 'med': med,
                    'cote_classement': 1 / med,
                    # Positif : cote du jour PLUS BASSE que son classement.
                    'ec': (p - med) * 100,
                    'y': gagne,
                    'gain': (cote - 1) if gagne else -1.0,
                })
        # Historique injecté APRÈS la mesure du jour : point-in-time.
        for paire, cotes in par_jour[jour]:
            for j, (cote, p) in cotes.items():
                hist[j].append(p)
    return P, sans_res, ambigus


def ic(v):
    n = len(v)
    if n < 2:
        return float('nan'), float('nan'), float('nan')
    m = st.mean(v)
    h = 1.96 * st.stdev(v) / math.sqrt(n)
    return m, m - h, m + h


def ligne(nom, g):
    if not g:
        return f'  {nom:34}  n=    0'
    m, lo, hi = ic([x['gain'] for x in g])
    gagne = sum(x['y'] for x in g) / len(g)
    att = st.mean(x['p'] for x in g)
    cote = st.median(x['cote'] for x in g)
    flag = '  EXCLUT ZÉRO' if (lo > 0 or hi < 0) else ''
    return (f'  {nom:34}  n={len(g):5}  cote méd {cote:5.2f}  '
            f'gagne {100*gagne:5.1f}% (juste {100*att:5.1f}%)  '
            f'ROI {100*m:+6.1f}% [{100*lo:+6.1f};{100*hi:+6.1f}]{flag}')


def main():
    print('Chargement (courbes Pinnacle, coupe pré-match)…')
    try:
        matchs = pf.charger_matchs()
        ref = cotes_pinnacle()
    except Exception as e:
        print(f'  ÉCHEC du chargement : {type(e).__name__} {e}')
        return 1
    R = edt.charger_resultats(matchs)
    P, sans_res, ambigus = construire(ref, R)
    print(f'  matchs cotés : {len(ref)}   sans résultat : {sans_res}'
          f'   ambigus : {ambigus}')
    if not P:
        print('Aucun pari mesurable.')
        return 0
    jours = sorted({x['d'] for x in P})
    print(f'  paris mesurables (>= {MIN_COTES} cotes antérieures) : {len(P)}'
          f' sur {len({(x["paire"], x["d"]) for x in P})} matchs')
    print(f'  période {jours[0]} -> {jours[-1]}')
    marge = st.median(x['p'] * x['cote'] for x in P)
    print(f'  marge Pinnacle médiane : {100*(1/marge - 1) if marge else 0:+.1f} %'
          f'  (cote réelle / cote juste)')

    print('\n' + '=' * 78)
    print('0. LE TÉMOIN — jouer TOUT LE MONDE, sans règle')
    print('=' * 78)
    print(ligne('tous les paris', P))
    print('  Ce que coûte la marge seule. Une règle doit faire nettement mieux.')

    print('\n' + '=' * 78)
    print('1. LES DEUX RÈGLES, par seuil (écart en points de probabilité)')
    print('=' * 78)
    for s in SEUILS:
        A = [x for x in P if x['ec'] > s]
        B = [x for x in P if x['ec'] < -s]
        print(f'  seuil {s} pts')
        print(ligne(f'A  cote du jour < classement', A))
        print(ligne(f'B  cote du jour > classement', B))

    print('\n' + '=' * 78)
    print('2. STABILITÉ — les deux moitiés de la période')
    print('=' * 78)
    mil = jours[len(jours) // 2]
    for s in SEUILS:
        for nom, f in (('A', lambda x: x['ec'] > s),
                       ('B', lambda x: x['ec'] < -s)):
            g1 = [x for x in P if f(x) and x['d'] < mil]
            g2 = [x for x in P if f(x) and x['d'] >= mil]
            print(ligne(f'{nom} ±{s:<2} avant le {mil}', g1))
            print(ligne(f'{nom} ±{s:<2} à partir du {mil}', g2))

    print('\n' + '=' * 78)
    print('3. PAR NIVEAU DE COTE — la règle A est-elle juste « jouer les favoris » ?')
    print('=' * 78)
    print('  La règle A choisit surtout des favoris, la B des outsiders. Si le')
    print('  marché favorisait déjà un niveau de cote, la règle le capterait')
    print('  sans rien dire du classement. On compare donc, À COTE ÉGALE, les')
    print('  paris de la règle aux autres.')
    for lo_, hi_ in ((1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 100.0)):
        T = [x for x in P if lo_ <= x['cote'] < hi_]
        print(f'  cotes {lo_:.1f}–{hi_:.1f}')
        print(ligne('    tous', T))
        print(ligne('    A (> +10)', [x for x in T if x['ec'] > 10]))
        print(ligne('    B (< −10)', [x for x in T if x['ec'] < -10]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
