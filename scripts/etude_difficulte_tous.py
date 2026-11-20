#!/usr/bin/env python3
"""etude_difficulte_tous.py — la même question, sur TOUS les matchs.

    python scripts/etude_difficulte_tous.py

LECTURE SEULE. N'écrit rien, ne sort pas sur le réseau, relançable.

POURQUOI CE SECOND FICHIER
---------------------------
etude_difficulte.py mesure sur moves_detail_hist.csv : 465 alertes. Or
moves_detail_hist ne contient QUE des mouvements détectés. Un joueur y
figure parce que le marché a bougé vers lui. Toute population bâtie
là-dessus est choisie par le résultat qu'on veut étudier.

Deux conséquences, et la seconde est la pire :

  — l'échantillon est petit, donc les intervalles sont larges ;
  — il n'est pas représentatif, donc même un intervalle serré ne dirait
    rien des matchs en général.

Ce fichier refait la mesure sur l'univers complet : tous les matchs dont
on a relevé un prix Pinnacle pré-match, mouvement ou pas.

D'OÙ VIENNENT LES DONNÉES
--------------------------
De player_form.py, dont on réutilise les deux chargeurs plutôt que de les
réécrire :

  charger_matchs()  (date, joueur_A, joueur_B, A_gagne, sets_A, sets_B,
                    tournoi), triés — fusion de resultats_oddspapi.json et
                    de set_results.json, dédupliquée.

  cotes_sharp()     {(paire, date): (joueur, proba)} — la clôture Pinnacle
                    DÉVIGUÉE, lue dans les courbes book_curves.jsonl.

Le second est le plus important, et pas seulement pour les prix : il
applique la COUPE PRÉ-MATCH. Le dernier point d'une courbe est in-play et
encode déjà le déroulement de la rencontre. Ce piège a produit quatre faux
positifs dans ce dépôt, dont un Pinnacle mesuré à 95,5 % de précision.
Réécrire ce chargement ici, c'était le refaire une cinquième fois.

LES PRIX SERVENT DEUX FOIS, ET PAS AU MÊME ENDROIT
---------------------------------------------------
« Son ordinaire » se construit sur TOUS les prix relevés, y compris les
matchs dont on n'a pas le résultat : une médiane n'a pas besoin du
vainqueur. Le résidu, lui, ne se calcule que sur les matchs dénoués.
L'historique est donc plus profond que l'échantillon de mesure, ce qui est
exactement ce qu'on veut — une médiane sur peu d'observations est bruitée,
et ce bruit atténue tout.

UNE LIGNE PAR MATCH, PAS DEUX
------------------------------
Chaque match a deux joueurs, donc deux écarts et deux résidus. Mais les
deux résidus d'un même match sont opposés : les compter tous les deux
doublerait n sans ajouter d'information et resserrerait les intervalles
d'un facteur racine de 2, à tort.

On garde donc UN côté par match, choisi par l'ordre alphabétique des clés.
C'est arbitraire, et c'est le but : arbitraire veut dire indépendant du
résultat. Le choix par « le plus gros écart » aurait sélectionné sur la
variable étudiée.

CE QUE CE FICHIER PEUT MESURER ET QUE L'AUTRE NE POUVAIT PAS
--------------------------------------------------------------
La valeur des alertes elles-mêmes. Avec les deux populations côte à côte,
on peut enfin demander : sur un même écart de difficulté, le marché
se trompe-t-il davantage là où un mouvement a été détecté ? C'est la
validation du système que le biais de sélection interdisait jusqu'ici.
"""

import csv
import datetime
import json
import math
import os
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import player_form as pf          # noqa: E402 — on réutilise SES chargeurs

MOVES = os.environ.get('MOVES', 'moves_detail_hist.csv')
ODDS_RESULTS = os.environ.get('ODDSPAPI_RESULTS', 'resultats_oddspapi.json')

# Profondeur minimale de l'historique de prix pour qu'une médiane existe,
# du côté mesuré. Même valeur que MIN_COTES de build_profiles.py.
MIN_COTES = int(os.environ.get('MIN_COTES', '4'))

# Les trois découpages. Un seul serait un choix ; trois montrent si le
# résultat tient quand on déplace la frontière.
SEUILS = [5, 10, 15]


def ic(v):
    n = len(v)
    if n < 2:
        return 0.0, 0.0, 0.0
    m = st.mean(v)
    se = st.stdev(v) / math.sqrt(n)
    return m, m - 1.96 * se, m + 1.96 * se


def wilson(k, n):
    if not n:
        return 0.0, 0.0, 0.0
    p = k / n
    z = 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, c - h, c + h


def set_attendu(p_match):
    """La proba de set qui donne cette proba de match, à sets indépendants
    en deux manches gagnantes : s²(3−2s) = p.

    Sans ce repère, le taux brut de 1er set trompe : le match est un
    événement plus tranché qu'un set, donc les deux taux se rapprochent de
    50 % mécaniquement, sans que personne ne se relâche.
    """
    lo, hi = 0.0, 1.0
    for _ in range(60):
        s = (lo + hi) / 2
        if s * s * (3 - 2 * s) < p_match:
            lo = s
        else:
            hi = s
    return (lo + hi) / 2


# Fenêtre de rattachement d'un résultat à un prix. Mesuré le 09/10 sur les
# vraies courbes : resolved_at tombe le jour même du match dans 85 cas, le
# lendemain dans 749, et jusqu'à cinq jours après dans 124 (règlements
# « provisional » repris plus tard). Au-delà, une revanche entre les deux
# mêmes joueurs devient possible ; à cinq jours elle ne l'est pas.
FENETRE_JOURS = int(os.environ.get('FENETRE_JOURS', '5'))


def charger_resultats(matchs):
    """paire -> [(date, vainqueur)] — tous les résultats connus.

    POURQUOI PAS LA JOINTURE DE player_form.py
    ------------------------------------------
    player_form joint un prix et un résultat sur (paire, MÊME date). Mais le
    prix est daté par commence_time et le résultat par resolved_at. Mesuré :
    sur 2 801 matchs cotés, 738 n'étaient retrouvés qu'à la veille, et
    1 981 pas du tout. Pire, le même match peut exister deux fois dans
    charger_matchs() sous deux dates (Shimabukuro–Rodionov : joué le 07/06,
    réglé le 11/06), parce que la déduplication se fait sur la date.

    Ici on part du PRIX — une ligne par match coté, sans doublon possible —
    et on cherche son résultat dans les jours qui suivent. 2 532 matchs
    résolus sur 2 801, contre environ 1 500 par la jointure d'origine.
    """
    R = defaultdict(list)
    for d, a, b, a_gagne, sa, sb, tour in matchs:
        if d:
            R[frozenset((a, b))].append((d.date(), a if a_gagne else b, tour))
    return R


def charger_set1():
    """{(paire, date du match): vainqueur du 1er set}.

    Deux sources, dans l'ordre de fiabilité :
      1. set_results.json, rattaché par son uid à la courbe du match, qui
         donne la date de COUP D'ENVOI — la même que le prix ;
      2. resultats_oddspapi.json, daté par resolved_at, rattaché avec la
         même fenêtre que le vainqueur.
    """
    par_uid = {}
    for src in ('book_curves.jsonl', 'book_curves_live.jsonl'):
        try:
            for ligne in pf.ov.open_curves(src, verbose=False):
                try:
                    r = json.loads(ligne)
                except ValueError:
                    continue
                u = r.get('uid')
                if u and u not in par_uid:
                    par_uid[u] = (pf._dt(r.get('commence_time')),
                                  pf.cle_joueur(r.get('home_team') or r.get('home')),
                                  pf.cle_joueur(r.get('away_team') or r.get('away')))
        except Exception:
            continue

    exact, fenetre = {}, defaultdict(list)
    sr = os.environ.get('SET_RESULTS', 'set_results.json')
    if os.path.exists(sr):
        for u, v in json.load(open(sr, encoding='utf-8')).items():
            m = par_uid.get(u)
            if not m or not m[0] or not isinstance(v, dict):
                continue
            if v.get('set1') not in ('home', 'away'):
                continue
            d, h, a = m
            if h and a and h != a:
                exact[(frozenset((h, a)), d.date())] = h if v['set1'] == 'home' else a
    if os.path.exists(ODDS_RESULTS):
        for v in json.load(open(ODDS_RESULTS, encoding='utf-8')).values():
            if not isinstance(v, dict) or v.get('set1') not in ('home', 'away'):
                continue
            h, a = pf.cle_joueur(v.get('home')), pf.cle_joueur(v.get('away'))
            d = pf._dt(v.get('resolved_at'))
            if h and a and h != a and d:
                fenetre[frozenset((h, a))].append(
                    (d.date(), h if v['set1'] == 'home' else a))
    return exact, fenetre


def charger_alertes():
    """{(paire, date)} -> clé du joueur STEAMÉ.

    La date d'une alerte est celle du match ; on l'enregistre aussi à la
    veille et au lendemain pour absorber le même décalage de fuseau qui
    sépare commence_time de la date affichée.
    """
    out = {}
    if not os.path.exists(MOVES):
        return out
    for r in csv.DictReader(open(MOVES, encoding='utf-8')):
        a, b = pf.cle_joueur(r.get('steame')), pf.cle_joueur(r.get('opp'))
        if not a or not b or a == b or not r.get('date'):
            continue
        try:
            d = datetime.date.fromisoformat(r['date'])
        except ValueError:
            continue
        for k in (-1, 0, 1):
            out.setdefault((frozenset((a, b)), d + datetime.timedelta(days=k)), a)
    return out


def construire(ref, R, set1, alertes):
    """Une ligne par MATCH COTÉ et dénoué, médiane point-in-time.

    L'univers part des prix, pas des résultats : un match coté apparaît une
    fois et une seule. Son résultat est cherché dans les FENETRE_JOURS
    suivants ; s'il est ambigu (deux vainqueurs différents), le match est
    écarté plutôt que deviné.

    L'historique est injecté par DATE, après la mesure du jour : la médiane
    lue à la date d'un match ne contient que des matchs strictement
    antérieurs. C'est la mécanique d'etude_forme_alertes.py.
    """
    exact, fenetre = set1
    par_jour = defaultdict(list)
    for (paire, d), (joueur, p) in ref.items():
        duo = sorted(paire)
        if len(duo) != 2:
            continue
        autre = duo[0] if duo[1] == joueur else duo[1]
        par_jour[d].append((paire, joueur, p, autre))

    hist = defaultdict(list)        # ses propres prix
    hist_adv = defaultdict(list)    # les prix des adversaires qu'il a eus
    L = []
    sans_res = ambigus = 0
    for jour in sorted(par_jour):
        for paire, joueur, p, autre in par_jour[jour]:
            c = [r for r in R.get(paire, [])
                 if 0 <= (r[0] - jour).days <= FENETRE_JOURS]
            if not c:
                sans_res += 1
                continue
            if len({r[1] for r in c}) > 1:
                ambigus += 1
                continue
            vainqueur, tour = c[0][1], c[0][2]

            # Le côté mesuré : l'ordre alphabétique des clés. Arbitraire,
            # donc indépendant du résultat.
            cote, face = min(paire), max(paire)
            p_cote = p if joueur == cote else 1 - p
            if len(hist[cote]) < MIN_COTES:
                continue
            med = st.median(hist[cote])

            # L'ÉCART D'ADVERSAIRE : niveau habituel de mes adversaires
            # moins niveau habituel de celui d'en face. Positif = il est
            # plus faible que ceux que j'affronte d'habitude.
            ec_adv = None
            if (len(hist_adv[cote]) >= MIN_COTES
                    and len(hist[face]) >= MIN_COTES):
                ec_adv = (st.median(hist_adv[cote])
                          - st.median(hist[face])) * 100

            v1 = exact.get((paire, jour))
            if v1 is None:
                c1 = [r for r in fenetre.get(paire, [])
                      if 0 <= (r[0] - jour).days <= FENETRE_JOURS]
                if c1 and len({r[1] for r in c1}) == 1:
                    v1 = c1[0][1]

            steame = alertes.get((paire, jour))
            L.append({
                'd': jour,
                'tour': tour,
                'cote': cote,
                'y': 1.0 if vainqueur == cote else 0.0,
                's1': None if v1 is None else float(v1 == cote),
                'p': p_cote,
                'med': med,
                'ec': (p_cote - med) * 100,
                'ec_adv': ec_adv,
                'des': None if ec_adv is None
                else (p_cote - med) * 100 - ec_adv,
                'n_hist': len(hist[cote]),
                'alerte': steame is not None,
                # Pour les alertes : le résidu du côté STEAMÉ, mesuré
                # contre la clôture sharp des courbes.
                'res_steame': None if steame is None
                else ((1.0 if vainqueur == steame else 0.0)
                      - (p_cote if steame == cote else 1 - p_cote)),
            })
        for paire, joueur, p, autre in par_jour[jour]:
            hist[joueur].append(p)
            hist_adv[joueur].append(1 - p)
            hist[autre].append(1 - p)
            hist_adv[autre].append(p)
    return L, sans_res, ambigus


def groupes(L, seuil):
    B = defaultdict(list)
    for x in L:
        B['plus facile' if x['ec'] > seuil
          else 'plus dur' if x['ec'] < -seuil else 'normal'].append(x)
    return B


def table(L, seuil, titre):
    print(f'\n  {titre}')
    print(f'{"":15}{"n":>6}{"prix":>8}{"gagne":>8}{"annoncé":>9}'
          f'{"il fait mieux de":>30}')
    B = groupes(L, seuil)
    for b in ('plus facile', 'normal', 'plus dur'):
        g = B[b]
        if len(g) < 30:
            print(f'  {b:13}{len(g):6}   trop peu')
            continue
        p, _, _ = wilson(sum(x['y'] for x in g), len(g))
        ann = st.mean([x['p'] for x in g])
        m, lo, hi = ic([x['y'] - x['p'] for x in g])
        v = 'EXCLUT ZÉRO' if (lo > 0 or hi < 0) else ''
        print(f'  {b:13}{len(g):6}{1/max(.01, ann):8.2f}{100*p:7.1f}%'
              f'{100*ann:8.1f}%{100*m:+10.2f} [{100*lo:+6.2f};{100*hi:+6.2f}] {v}')
    return B


def main():
    print('Chargement via player_form.py (courbes, coupe pré-match incluse)…')
    try:
        matchs = pf.charger_matchs()
        ref = pf.cotes_sharp()
    except Exception as e:
        print(f'  ÉCHEC du chargement : {type(e).__name__} {e}')
        print('  Lancer depuis la racine du dépôt, où player_form.py tourne.')
        return 1

    R = charger_resultats(matchs)
    s1ref = charger_set1()
    alertes = charger_alertes()
    print(f'  matchs dénoués connus        : {len(matchs)}')
    print(f'  matchs avec un prix pré-match : {len(ref)}')
    # Les deux sources ne datent pas pareil : charger_matchs date sur
    # resolved_at, cotes_sharp sur commence_time. Un match réglé le
    # lendemain de son coup d'envoi ne se joint donc pas. C'est la
    # jointure de player_form.py, reprise telle quelle pour que les deux
    # fichiers mesurent la même population — mais elle explique une partie
    # de l'écart entre les deux comptes ci-dessus.
    print(f'  1ers sets (par uid / par fenêtre) : {len(s1ref[0])} / '
          f'{sum(len(v) for v in s1ref[1].values())}')
    print(f'  alertes connues               : '
          f'{len(set(alertes.values())) and len(alertes)//3}')

    L, sans_res, ambigus = construire(ref, R, s1ref, alertes)
    print(f'  prix sans résultat dans les {FENETRE_JOURS} jours : {sans_res}'
          f'   ambigus écartés : {ambigus}')
    if not L:
        print('\nAucun match mesurable — vérifier que les courbes sont lisibles.')
        return 0

    na = sum(1 for x in L if x['alerte'])
    print(f'\nMESURABLES (médiane >= {MIN_COTES} prix antérieurs) : {len(L)}')
    print(f'  période {min(x["d"] for x in L)} -> {max(x["d"] for x in L)}')
    print(f'  dont alertes : {na}   hors alertes : {len(L)-na}')
    print(f'  profondeur médiane de l\'historique : '
          f'{st.median([x["n_hist"] for x in L]):.0f} prix')
    e = sorted(x['ec'] for x in L)
    print(f'  écart : médiane {e[len(e)//2]:+.1f}, '
          f'décile {e[len(e)//10]:+.1f} à {e[9*len(e)//10]:+.1f} pts')
    sd = st.stdev([x['y'] - x['p'] for x in L])
    print(f'  IC95 du résidu à n={len(L)} : ±{196*sd/math.sqrt(len(L)):.2f} pts'
          f'   (±{196*sd/math.sqrt(465):.2f} à n=465, sur les alertes seules)')

    print('\n' + '=' * 78)
    print('1. TOUS LES MATCHS — plus facile, normal, plus dur')
    print('=' * 78)
    for s in SEUILS:
        table(L, s, f'seuil ±{s} points')

    print('\n  ÉCART ENTRE LES DEUX EXTRÊMES')
    for s in SEUILS:
        f = [x['y'] - x['p'] for x in L if x['ec'] > s]
        d = [x['y'] - x['p'] for x in L if x['ec'] < -s]
        if min(len(f), len(d)) < 30:
            continue
        m = st.mean(f) - st.mean(d)
        se = math.sqrt(st.stdev(f) ** 2 / len(f) + st.stdev(d) ** 2 / len(d))
        print(f'    ±{s:<3} n={len(f)}/{len(d)}   {100*m:+6.2f} pts   '
              f'IC95 [{100*(m-1.96*se):+6.2f} ; {100*(m+1.96*se):+6.2f}]   '
              f't={m/se:+.2f}')

    print('\n  TÉMOIN — le prix du match seul, sans la médiane')
    print('    (si le marché était mal calibré par niveau de prix, l\'écart')
    print('     le capterait sans rien dire de « son ordinaire »)')
    s = sorted(L, key=lambda x: x['p'])
    q = len(s) // 4
    for i in range(4):
        g = s[i*q:(i+1)*q if i < 3 else len(s)]
        m, lo, hi = ic([x['y'] - x['p'] for x in g])
        print(f'    prix {1/max(.01,g[-1]["p"]):5.2f}–{1/max(.01,g[0]["p"]):5.2f}'
              f'  n={len(g):5}  résidu {100*m:+6.2f} '
              f'[{100*lo:+6.2f};{100*hi:+6.2f}]')

    print('\n' + '=' * 78)
    print('2. LES ALERTES VALENT-ELLES MIEUX QUE LE TOUT-VENANT ?')
    print('=' * 78)
    print('  La question que le biais de sélection interdisait : à écart de')
    print('  difficulté comparable, le marché se trompe-t-il DAVANTAGE là où')
    print('  un mouvement a été détecté ?')
    A = [x for x in L if x['alerte']]
    N = [x for x in L if not x['alerte']]
    if min(len(A), len(N)) < 30:
        print(f'\n  n insuffisant ({len(A)} alertes, {len(N)} hors alertes).')
    else:
        print(f'\n{"":22}{"n":>6}{"résidu":>22}')
        for g, lib in ((A, 'alertes'), (N, 'hors alertes')):
            m, lo, hi = ic([x['y'] - x['p'] for x in g])
            print(f'  {lib:20}{len(g):6}{100*m:+10.2f} '
                  f'[{100*lo:+6.2f};{100*hi:+6.2f}]')
        m = (st.mean([x['y'] - x['p'] for x in A])
             - st.mean([x['y'] - x['p'] for x in N]))
        se = math.sqrt(st.stdev([x['y']-x['p'] for x in A]) ** 2 / len(A)
                       + st.stdev([x['y']-x['p'] for x in N]) ** 2 / len(N))
        print(f'  {"différence":20}{"":6}{100*m:+10.2f} '
              f'[{100*(m-1.96*se):+6.2f};{100*(m+1.96*se):+6.2f}]   '
              f't={m/se:+.2f}')
        print('\n  Le côté mesuré ci-dessus est ARBITRAIRE (ordre alphabétique) :')
        print('  son résidu doit valoir zéro si le marché est calibré, alerte ou')
        print('  pas. Ce qui juge le système, c\'est le côté STEAMÉ :')
        rs = [x['res_steame'] for x in A if x['res_steame'] is not None]
        if len(rs) >= 30:
            m, lo, hi = ic(rs)
            print(f'\n  {"côté steamé, alertes":24}{len(rs):6}{100*m:+10.2f} '
                  f'[{100*lo:+6.2f};{100*hi:+6.2f}]'
                  + ('   EXCLUT ZÉRO' if lo > 0 or hi < 0 else ''))
            print('  (contre la clôture sharp DÉVIGÉE des courbes, coupe')
            print('   pré-match incluse — pas le pin_close de moves_detail_hist)')
        for s in SEUILS[1:2]:
            print(f'\n  Les mêmes, par difficulté (seuil ±{s}) :')
            for g, lib in ((A, 'alertes'), (N, 'hors alertes')):
                G = groupes(g, s)
                bouts = []
                for b in ('plus facile', 'normal', 'plus dur'):
                    h = G.get(b, [])
                    if len(h) < 30:
                        bouts.append(f'{b} n={len(h)} —')
                        continue
                    m2, lo2, hi2 = ic([x['y'] - x['p'] for x in h])
                    bouts.append(f'{b} n={len(h)} {100*m2:+.2f} '
                                 f'[{100*lo2:+.1f};{100*hi2:+.1f}]')
                print(f'    {lib:14} ' + '   '.join(bouts))

    if any(x['s1'] is not None for x in L):
        print('\n' + '=' * 78)
        print('3. LE 1er SET, contre ce que l\'arithmétique du BO3 impose')
        print('=' * 78)
        print(f'\n{"":15}{"n":>6}{"match":>9}{"set1 obs":>11}'
              f'{"attendu":>10}{"écart":>9}')
        for s in SEUILS:
            G = groupes(L, s)
            print(f'  -- seuil ±{s} pts')
            for b in ('plus facile', 'normal', 'plus dur'):
                g = G[b]
                v = [x for x in g if x['s1'] is not None]
                if len(g) < 30 or len(v) < 30:
                    continue
                pm = st.mean([x['y'] for x in g])
                ps = st.mean([x['s1'] for x in v])
                att = set_attendu(pm)
                _, lo, hi = ic([x['s1'] for x in v])
                print(f'   {b:13}{len(v):6}{100*pm:8.1f}%{100*ps:10.1f}%'
                      f'{100*att:9.1f}%{100*(ps-att):+9.1f}'
                      + ('   hors IC' if att < lo or att > hi else ''))

    # ── 4. L'ÉCART D'ADVERSAIRE ─────────────────────────────────────────
    V = [x for x in L if x['ec_adv'] is not None]
    if len(V) >= 90:
        print('\n' + '=' * 78)
        print('4. L\'ÉCART D\'ADVERSAIRE — l\'autre façon de juger la difficulté')
        print('=' * 78)
        print("""
  Un match peut être « plus dur que son ordinaire » au PRIX et pourtant
  l'opposer à quelqu'un de plus faible que ses adversaires habituels.

      Mannarino      ordinaire 2,30   ses adversaires 1,77   coté 2,59
      son adversaire ordinaire 1,96   ses adversaires 2,04   coté 1,55

  Le prix dit « plus dur » à Mannarino (−4,9 pts). Mais son adversaire du
  jour vaut 1,96 quand il en affronte à 1,77 d'habitude : par l'identité
  de l'adversaire, le match est au contraire PLUS FACILE (+5,5 pts).

  Les deux lectures se contredisent de 10,3 points. C'est le DÉSACCORD, et
  il isole ce que le marché sait du joueur AUJOURD'HUI qui ne tient pas à
  l'adversaire : surface, forme, blessure, fatigue, public.

  Convention : écart d'adversaire POSITIF = adversaire plus faible que son
  ordinaire. Désaccord NÉGATIF = le prix est plus dur que l'adversaire
  seul ne le justifie.
""")
        print(f'  mesurable sur {len(V)} matchs sur {len(L)} '
              f'(il faut QUATRE historiques, pas deux)')
        e = sorted(x['ec_adv'] for x in V)
        print(f'  écart d\'adversaire : médiane {e[len(e)//2]:+.1f}, '
              f'décile {e[len(e)//10]:+.1f} à {e[9*len(e)//10]:+.1f} pts')

        for f, lib in (('ec_adv', 'écart d\'adversaire'),
                       ('des', 'désaccord')):
            s = sorted(V, key=lambda x: x[f])
            q = len(s) // 3
            print(f'\n  TERCILES — {lib}')
            for i in range(3):
                g = s[i*q:(i+1)*q if i < 2 else len(s)]
                p, _, _ = wilson(sum(x['y'] for x in g), len(g))
                m, lo, hi = ic([x['y'] - x['p'] for x in g])
                v = 'EXCLUT ZÉRO' if (lo > 0 or hi < 0) else ''
                print(f'    T{i+1} [{g[0][f]:+6.1f};{g[-1][f]:+6.1f}] '
                      f'n={len(g):5}  gagne {100*p:5.1f}%  '
                      f'résidu {100*m:+6.2f} [{100*lo:+6.2f};{100*hi:+6.2f}] {v}')

        print('\n  TÉMOIN — à prix du match constant')
        print('    (l\'écart d\'adversaire ne doit pas être qu\'un déguisement')
        print('     du niveau de prix ; mesuré sur les alertes : corrélation')
        print('     entre les deux +0,03, donc ce n\'en est pas un)')
        s = sorted(V, key=lambda x: x['p'])
        q = len(s) // 3
        for i in range(3):
            g = s[i*q:(i+1)*q if i < 2 else len(s)]
            a = [x['ec_adv'] for x in g]
            b = [x['y'] - x['p'] for x in g]
            n = len(a)
            ma, mb = st.mean(a), st.mean(b)
            sa, sb = st.stdev(a), st.stdev(b)
            c = sum((u - ma) * (w - mb) for u, w in zip(a, b)) / (n-1) / (sa*sb)
            t = c * math.sqrt((n - 2) / max(1e-9, 1 - c * c))
            print(f'    prix {1/max(.01,g[-1]["p"]):5.2f}–{1/max(.01,g[0]["p"]):5.2f}'
                  f'  n={n:5}  corr(écart adv, résidu) {c:+.4f}  t={t:+5.2f}')

        print('\n  LE FILTRE CANDIDAT — écarter les adversaires trop forts')
        tout, _, _ = ic([x['y'] - x['p'] for x in V])
        print(f'    sans filtre            n={len(V):5}  '
              f'résidu {100*tout:+6.2f}')
        for s_ in (-10, -20, -25):
            g = [x for x in V if x['ec_adv'] >= s_]
            if len(g) < 30:
                continue
            m, lo, hi = ic([x['y'] - x['p'] for x in g])
            print(f'    en écartant ec_adv < {s_:+4}  n={len(g):5} '
                  f'({100*len(g)/len(V):3.0f} %)  '
                  f'résidu {100*m:+6.2f} [{100*lo:+6.2f};{100*hi:+6.2f}]')

        print('\n  STABILITÉ DANS LE TEMPS')
        V.sort(key=lambda x: x['d'])
        mid = len(V) // 2
        for g, lib in ((V[:mid], '1re moitié'), (V[mid:], '2e moitié')):
            a = [x['ec_adv'] for x in g]
            b = [x['y'] - x['p'] for x in g]
            n = len(a)
            ma, mb = st.mean(a), st.mean(b)
            sa, sb = st.stdev(a), st.stdev(b)
            c = sum((u - ma) * (w - mb) for u, w in zip(a, b)) / (n-1) / (sa*sb)
            t = c * math.sqrt((n - 2) / max(1e-9, 1 - c * c))
            print(f'    {lib:12} {g[0]["d"]} -> {g[-1]["d"]}  n={n:5}  '
                  f'corr {c:+.4f}  t={t:+5.2f}')

    print("""
================================================================================
COMMENT LIRE CE FICHIER À CÔTÉ D'etude_difficulte.py
================================================================================

  Les deux mesurent la même chose, sur deux populations. Si les chiffres
  se ressemblent, le biais de sélection ne déformait pas la conclusion et
  c'est celui-ci qu'il faut citer, parce que son n est plus grand. S'ils
  divergent, c'est CE fichier qui a raison : l'autre décrit les matchs sur
  lesquels le marché avait déjà bougé.

  Et ce fichier seul peut répondre à la question du bloc 2. Sur les
  alertes seules elle était impossible à poser : comparer les alertes à
  elles-mêmes ne compare rien.
""")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
