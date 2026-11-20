#!/usr/bin/env python3
"""etude_fiche_complete.py — toute la fiche contre les résultats.

    python scripts/etude_fiche_complete.py

LECTURE SEULE. N'écrit rien, ne touche à rien, ne sort pas sur le réseau.

LA QUESTION
-----------
La fiche duo affiche sept lignes : classement marché, rang, cote des
adversaires, écart du jour (+17 / −18), Elo et Elo par surface, favori à
l'ouverture, matchs gagnés, premiers sets gagnés.

Prises une par une elles n'ont rien donné. Ensemble ? C'est la bonne
question : un modèle peut trouver dans la combinaison ce qu'aucune
variable ne porte seule.

Ce script les met toutes ensemble et mesure UNE chose : le modèle
prédit-il mieux que la clôture Pinnacle ?

RÉPONSE : NON. En échantillon il fait mieux ; en validation croisée et
hors échantillon il fait PIRE. Et le gain en échantillon est exactement ce
que la même procédure produit quand on casse le lien entre les variables
et les résultats — c'est-à-dire quand il n'y a rien à trouver.

LA FORME DU TEST : LE MARCHÉ EN DÉCALAGE
-----------------------------------------
On ne compare pas un modèle maison à la clôture. On PART de la clôture :

    logit(p) = logit(prix du marché) + b0 + somme(b_i x_i)

Les b ne peuvent donc gagner que ce que le marché a laissé. S'ils valent
zéro, le prix contient déjà tout ce que la fiche sait. C'est la seule
écriture qui réponde à « qu'est-ce que la fiche AJOUTE ».

Toutes les variables sont des DIFFÉRENTIELS steamé moins adversaire, en
points de probabilité : c'est la lecture de la fiche duo, deux colonnes
côte à côte.

CE QUI EST RECONSTRUIT POINT-IN-TIME, ET CE QUI NE PEUT PAS L'ÊTRE
-------------------------------------------------------------------
Chaque variable est recalculée à la date de l'alerte, avec les seules
données antérieures. Les cotes viennent de moves_detail_hist, les bilans
de set_results, et les deux sources avancent ensemble jour par jour.

L'ELO EST EXCLU. elo_reference.json est un instantané : la note d'un
joueur contient le résultat des matchs qu'on cherche à prédire. Mesuré
dans etude_cotes_maison.py : sur la période contaminée l'Elo « bat » le
marché 0,2030 contre 0,2145, sur la seule fenêtre propre il perd 0,2327
contre 0,2192. Le faire entrer ici ferait briller le modèle pour la même
raison, et la validation croisée ne le rattraperait pas — la fuite est
dans la donnée, pas dans l'ajustement.

L'OBJECTION DE FOND, AVANT MÊME DE MESURER
-------------------------------------------
Sur les sept lignes, cinq sont CALCULÉES À PARTIR DES COTES :

    classement marché     médiane des cotes d'ouverture Pinnacle
    rang                  la même, rangée
    cote des adversaires  médiane des cotes de ses adversaires
    écart du jour         sa cote du jour contre sa médiane
    favori à l'ouverture  part de ses cotes sous 2,00

Leur demander de battre la clôture Pinnacle, c'est demander au marché de
se contredire avec ses propres chiffres. Deux seulement apportent une
information que le prix ne contient pas par construction : matchs gagnés
et premiers sets gagnés.

Ça ne rend pas le test inutile — le marché peut mal agréger ce qu'il sait.
Mais ça dit où regarder quand le résultat sera nul.
"""

import csv
import json
import math
import os
import random
import re
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_profiles as bp       # noqa: E402 — on réutilise SA machinerie

MOVES = os.environ.get('MOVES', 'moves_detail_hist.csv')
SETRES = os.environ.get('SETRES', 'set_results.json')

# Profondeur minimale, DES DEUX CÔTÉS. C'est la contrainte qui décide de
# tout : à 4 cotes il reste 269 alertes sur 1340, en exigeant aussi
# 2 résultats il en reste 140. La fiche a l'air riche, le dépôt a quatre
# mois.
MIN_COTES = int(os.environ.get('MIN_COTES', '4'))
MIN_RES = int(os.environ.get('MIN_RES', '2'))

# Marge Pinnacle retirée avant de servir de référence (voir
# etude_cotes_maison.py : le verdict ne bouge pas entre 1,00 et 1,05).
MARGE = float(os.environ.get('MARGE_PIN', '1.025'))


def reconstruire():
    """Les alertes dénouées, chaque variable recalculée à leur date.

    On avance par jour dans les deux historiques à la fois. Avant de
    mesurer une alerte du jour J on a injecté tout ce qui est antérieur à
    J et rien du jour même : aucune variable ne peut contenir le match
    qu'on cherche à juger.

    C'est la mécanique d'etude_forme_alertes.py et d'etude_ecart_mediane,
    pour la même raison — et la seule façon de ne pas refaire H14.
    """
    moves = [r for r in csv.DictReader(open(MOVES, encoding='utf-8'))
             if r.get('date')]
    res = bp.charger_resultats(json.load(open(SETRES, encoding='utf-8')),
                               moves)

    # Seuls les résultats dont l'uid porte une date servent : sans date,
    # impossible de dire s'ils sont antérieurs à l'alerte.
    R = sorted((uid[:10], bp.cle(h), bp.cle(a), v)
               for uid, (h, a, v) in res.items()
               if re.match(r'^\d{4}-\d{2}-\d{2}', uid))
    moves.sort(key=lambda r: (r['date'], r.get('uid') or ''))

    cotes, cadv = defaultdict(list), defaultdict(list)
    bilan = defaultdict(lambda: [0, 0])      # [joués, gagnés]
    set1 = defaultdict(lambda: [0, 0])
    L, ir, i = [], 0, 0

    while i < len(moves):
        j = i
        while j < len(moves) and moves[j]['date'] == moves[i]['date']:
            j += 1
        d = moves[i]['date']

        while ir < len(R) and R[ir][0] < d:
            _, kh, ka, v = R[ir]
            for k, cote in ((kh, 'home'), (ka, 'away')):
                if not k:
                    continue
                if v.get('match'):
                    bilan[k][0] += 1
                    bilan[k][1] += (v['match'] == cote)
                if v.get('set1'):
                    set1[k][0] += 1
                    set1[k][1] += (v['set1'] == cote)
            ir += 1

        for r in moves[i:j]:
            if r.get('steame_gagne') not in ('oui', 'non'):
                continue
            po, pc = bp.num(r.get('pin_open')), bp.num(r.get('pin_close'))
            en = bp.num(r.get('entry'))
            if not (po and pc and pc > 1 and en):
                continue
            ks, ko = bp.cle(r.get('steame')), bp.cle(r.get('opp'))
            y = 1.0 if r['steame_gagne'] == 'oui' else 0.0
            L.append({
                'd': d, 'po': po, 'en': en, 'y': y,
                'pm': min(.995, max(.005, (1 / pc) / MARGE)),
                'pnl': bp.num(r.get('pnl')),
                'cs': list(cotes[ks]), 'co': list(cotes[ko]),
                'as': list(cadv[ks]), 'ao': list(cadv[ko]),
                'bs': tuple(bilan[ks]), 'bo': tuple(bilan[ko]),
                'ss': tuple(set1[ks]), 'so': tuple(set1[ko]),
            })

        for r in moves[i:j]:
            po = bp.num(r.get('pin_open'))
            if not po:
                continue
            ks, ko = bp.cle(r.get('steame')), bp.cle(r.get('opp'))
            ci = 1 / max(0.02, 1 - 1 / po)
            if ks:
                cotes[ks].append(po)
                cadv[ks].append(ci)
            if ko:
                cotes[ko].append(ci)
                cadv[ko].append(po)
        i = j
    return L, len(R)


def variables(x, avec_resultats):
    """Les lignes de la fiche duo, en différentiels, ou None si trop court."""
    if len(x['cs']) < MIN_COTES or len(x['co']) < MIN_COTES:
        return None
    ms, mo = st.median(x['cs']), st.median(x['co'])
    a_s, a_o = st.median(x['as']), st.median(x['ao'])
    ci = 1 / max(0.02, 1 - 1 / x['po'])      # cote implicite de l'adversaire
    f = {
        # « Coté pour ce match » : les deux écarts de la ligne +17 / −18.
        'ecart_s': (1 / x['po'] - 1 / ms) * 100,
        'ecart_o': (1 / ci - 1 / mo) * 100,
        # « Classement marché » : qui le marché cote le mieux d'habitude.
        'd_med': (1 / ms - 1 / mo) * 100,
        # « Cote de ses adversaires » : qui affronte le plus dur d'habitude.
        'd_adv': (1 / a_s - 1 / a_o) * 100,
        # « Favori à l'ouverture ».
        'd_fav': 100 * (sum(1 for c in x['cs'] if c < 2) / len(x['cs'])
                        - sum(1 for c in x['co'] if c < 2) / len(x['co'])),
    }
    if avec_resultats:
        if min(x['bs'][0], x['bo'][0], x['ss'][0], x['so'][0]) < MIN_RES:
            return None
        f['d_bilan'] = 100 * (x['bs'][1] / x['bs'][0] - x['bo'][1] / x['bo'][0])
        f['d_set1'] = 100 * (x['ss'][1] / x['ss'][0] - x['so'][1] / x['so'][0])
    return f


def jeu(L, avec_resultats):
    D = []
    for x in L:
        f = variables(x, avec_resultats)
        if f is None:
            continue
        D.append({'d': x['d'], 'y': x['y'], 'pm': x['pm'], 'x': f,
                  'off': math.log(x['pm'] / (1 - x['pm'])), 'pnl': x['pnl']})
    D.sort(key=lambda z: z['d'])
    return D


def ajuster(D, noms, it=4000, lr=.08):
    """Régression logistique AVEC LE PRIX DU MARCHÉ EN DÉCALAGE.

    Les coefficients ne peuvent gagner que ce que le marché a laissé.
    Variables centrées-réduites pour que les coefficients se comparent.
    """
    n, k = len(D), len(noms)
    mu = [st.mean([z['x'][m] for z in D]) for m in noms]
    sd = [st.stdev([z['x'][m] for z in D]) or 1 for m in noms]
    X = [[(z['x'][m] - mu[i]) / sd[i] for i, m in enumerate(noms)] for z in D]
    b = [0.0] * (k + 1)
    for _ in range(it):
        g = [0.0] * (k + 1)
        for i, z in enumerate(D):
            e = z['off'] + b[0] + sum(b[j + 1] * X[i][j] for j in range(k))
            r = 1 / (1 + math.exp(-max(-30, min(30, e)))) - z['y']
            g[0] += r
            for j in range(k):
                g[j + 1] += r * X[i][j]
        b = [bb - lr * gg / n for bb, gg in zip(b, g)]

    def pred(z):
        xs = [(z['x'][m] - mu[i]) / sd[i] for i, m in enumerate(noms)]
        e = z['off'] + b[0] + sum(b[j + 1] * xs[j] for j in range(k))
        return 1 / (1 + math.exp(-max(-30, min(30, e))))
    return b, pred


def brier(D, f):
    return st.mean([(f(z) - z['y']) ** 2 for z in D])


def analyse(D, lib):
    noms = list(D[0]['x'].keys())
    print('\n' + '=' * 72)
    print(f'{lib} — n={len(D)}, {len(noms)} variables, '
          f'{D[0]["d"]} -> {D[-1]["d"]}')
    print('=' * 72)

    print('\n  CHAQUE VARIABLE SEULE, contre le résidu de clôture')
    for m in noms:
        a = [z['x'][m] for z in D]
        r = [z['y'] - z['pm'] for z in D]
        ma, mr = st.mean(a), st.mean(r)
        sa, sr = st.stdev(a), st.stdev(r)
        c = sum((p - ma) * (q - mr) for p, q in zip(a, r)) / (len(a) - 1) / (sa * sr)
        t = c * math.sqrt((len(a) - 2) / max(1e-9, 1 - c * c))
        print(f'    {m:9} {c:+.4f}   t={t:+5.2f}'
              + ('   <- |t| > 2' if abs(t) > 2 else ''))

    b, pred = ajuster(D, noms)
    bm, bi = brier(D, lambda z: z['pm']), brier(D, pred)
    print(f'\n  EN ÉCHANTILLON   marché {bm:.4f}   + fiche {bi:.4f}   '
          f'gain {bm-bi:+.4f}')
    print('    coefficients : ' + '  '.join(
        f'{m}={b[i+1]:+.2f}' for i, m in enumerate(noms)))

    # Hors échantillon dans le temps : ce que ça aurait donné en le jouant.
    mid = len(D) // 2
    A, B = D[:mid], D[mid:]
    _, p2 = ajuster(A, noms)
    print(f'\n  HORS ÉCHANTILLON (appris sur la 1re moitié, testé sur la 2e,'
          f' n={len(B)})')
    print(f'    marché {brier(B, lambda z: z["pm"]):.4f}   '
          f'+ fiche {brier(B, p2):.4f}')

    # Validation croisée : même chose, mais tout l'échantillon sert de test.
    random.seed(3)
    idx = list(range(len(D)))
    random.shuffle(idx)
    be = bmm = 0.0
    for f in range(5):
        te = [D[i] for jj, i in enumerate(idx) if jj % 5 == f]
        tr = [D[i] for jj, i in enumerate(idx) if jj % 5 != f]
        _, pf = ajuster(tr, noms)
        be += sum((pf(z) - z['y']) ** 2 for z in te)
        bmm += sum((z['pm'] - z['y']) ** 2 for z in te)
    print(f'\n  VALIDATION CROISÉE 5 blocs')
    print(f'    marché {bmm/len(D):.4f}   + fiche {be/len(D):.4f}   '
          + ('LA FICHE AIDE' if be < bmm else 'LA FICHE DÉGRADE'))

    # Le témoin qui tranche : on casse le lien variables / résultats en
    # mélangeant les variables entre les lignes. Le marché et les résultats
    # restent intacts, donc le décalage reste juste : il ne reste à
    # apprendre QUE du bruit. Si le gain en échantillon y survit, c'est
    # qu'il ne venait pas des données.
    xs = [z['x'] for z in D]
    random.seed(5)
    gains = []
    for _ in range(12):
        random.shuffle(xs)
        E = [dict(z, x=xx) for z, xx in zip(D, xs)]
        _, pe = ajuster(E, noms)
        gains.append(brier(E, lambda z: z['pm']) - brier(E, pe))
    print(f'\n  TÉMOIN — variables mélangées, donc rien à trouver')
    print(f'    gain en échantillon : {st.mean(gains):+.4f}   '
          f'[{min(gains):+.4f} ; {max(gains):+.4f}]  sur 12 tirages')
    print(f'    gain réel           : {bm-bi:+.4f}'
          + ('   <- DANS LE BRUIT' if bm - bi <= max(gains) else ''))
    return bm - bi, (bmm - be) / len(D)


def main():
    for f in (MOVES, SETRES):
        if not os.path.exists(f):
            print(f'{f} introuvable — lancer depuis la racine du dépôt.')
            return 1

    L, n_res = reconstruire()
    print(f'{MOVES} : {len(L)} alertes dénouées')
    print(f'{SETRES} : {n_res} résultats datés exploitables')
    print('\nCOUVERTURE — la contrainte qui décide de tout')
    for mc in (3, 4, 6):
        n0 = sum(1 for x in L
                 if len(x['cs']) >= mc and len(x['co']) >= mc)
        n2 = sum(1 for x in L
                 if len(x['cs']) >= mc and len(x['co']) >= mc
                 and min(x['bs'][0], x['bo'][0],
                         x['ss'][0], x['so'][0]) >= MIN_RES)
        print(f'  {mc} cotes des deux côtés : {n0:4}      '
              f'+ {MIN_RES} résultats des deux côtés : {n2:4}')

    A = jeu(L, False)
    B = jeu(L, True)
    if len(A) < 60:
        print('\nÉchantillon trop faible — toute lecture serait du bruit.')
        return 0

    analyse(A, 'BLOC A — les cinq lignes tirées des cotes')
    if len(B) >= 60:
        analyse(B, 'BLOC B — les mêmes, plus bilans et premiers sets')

    print('\n' + '=' * 72)
    print('CE QUE ÇA DIT')
    print('=' * 72)
    print("""
  Le modèle fait mieux que le marché EN ÉCHANTILLON et moins bien en
  validation croisée. L'écart entre les deux est la définition du
  surajustement, et le témoin le confirme : en mélangeant les variables,
  donc en ne laissant rien à apprendre, la même procédure produit un gain
  en échantillon du même ordre.

  Les coefficients changent aussi de signe entre le bloc A et le bloc B :
  d_med passe de −0,26 à +0,35, d_adv de −0,47 à +0,38. Un coefficient
  qui s'inverse quand l'échantillon change n'estime rien.

  La cause n'est pas le modèle, c'est la matière. Cinq des sept lignes
  sont des fonctions des cotes Pinnacle : leur demander de battre la
  clôture Pinnacle, c'est demander au marché de se contredire avec ses
  propres chiffres. Les deux qui apportent autre chose — matchs gagnés,
  premiers sets gagnés — reposent sur quatre mois de résultats, soit
  deux à cinq matchs par joueur.

  POUR QUE LA QUESTION DEVIENNE JOUABLE, dans l'ordre :

  1. De l'information qui ne vienne pas des cotes. L'historique Sackmann
     donnerait des années de matchs par joueur là où on en a des mois,
     et avec les surfaces — que backtest_tennis.csv ne donne pas
     correctement (Roland-Garros y figure en dur ET en terre).

  2. De la profondeur des DEUX côtés. Exiger 4 cotes de chacun fait
     tomber 1340 alertes à 269 ; c'est là que l'échantillon se perd, pas
     dans le nombre d'alertes.

  3. Un journal écrit avant le match. Sans lui, chaque relance de ce
     script réapprend sur les mêmes lignes, et le surajustement revient
     par la porte qu'on vient de fermer.
""")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
