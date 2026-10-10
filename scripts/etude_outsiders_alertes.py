#!/usr/bin/env python3
"""etude_outsiders_alertes.py — SUIVI PRÉ-ENREGISTRÉ : les alertes sur les
outsiders cotés 2,40 – 4,00.

    python scripts/etude_outsiders_alertes.py

LECTURE SEULE. N'écrit rien, ne sort pas sur le réseau. Relançable autant
de fois qu'on veut, et fait pour l'être : les règles du bas sont GELÉES,
seul l'échantillon grossit.

D'OÙ VIENT LA RÈGLE (recherche du 09/10/2026)
---------------------------------------------
Sur 1 323 alertes reliées à une fiche (13/06 -> 09/10), découpées par
tranche de cote Pinnacle de clôture du joueur signalé :

    cote 2,40 – 4,00   254 alertes   joueur au prix Pinnacle  +17,5 %
                                     IC95 [ 0 ; +36 ]   gagne 40 % pour 34 % juste
    même tranche, matchs SANS alerte                       −34 %

Puis par ampleur du mouvement (en points de probabilité), dans cette
même tranche de cote :

    moins de 2 pts     85 alertes   +44 %  IC [+11 ; +77]
                       par mois : 07 +111 % (6)  08 +44 % (37)
                                  09 +26 % (25)  10 +48 % (17)
    2 à 3 pts         102 alertes   +18 %
    3 à 5 pts          45 alertes   −14 %

POURQUOI CES CHIFFRES NE PROUVENT RIEN
--------------------------------------
Ils sortent d'une recherche qui a essayé des centaines de découpes (220
cases sur tous les matchs, 35 par groupe d'alertes, 6 tranches de cote,
6 tranches d'ampleur, leurs croisements). Sur autant d'essais, le hasard
seul en fait briller quelques-uns. La tranche 2,60 – 3,50 gagnait +40 % en
août et −8 % en septembre.

Les règles sont donc gelées AVANT de voir la suite, et ne seront jugées
que sur les alertes de matchs joués APRÈS la date de gel.

LES DEUX RÈGLES GELÉES
----------------------
  R1  alerte « courbes » (moves_detail_hist) ou « Mouvement de cote »
      (odds_alerts_log) sur un joueur coté 2,40 ≤ cote < 4,00 chez
      Pinnacle juste avant le coup d'envoi -> jouer ce joueur.
  R2  R1, et mouvement de MOINS de 2 points de probabilité.

  Prix : la dernière cote Pinnacle avant le coup d'envoi (courbes, coupe
  pré-match), mise 1. C'est un prix PRUDENT : il est pris après le
  mouvement. Recevoir l'alerte et jouer tout de suite donne en général
  un meilleur prix.

  Population : comme dans la recherche, le joueur doit avoir au moins
  MIN_COTES cotes Pinnacle antérieures (une fiche) — changer cela
  changerait la population étudiée.

  Un pari par (match, joueur), même si les deux sources ont alerté.

LES CIBLES
----------
L'écart-type d'un pari à cote ~3 est d'environ 1,4. Pour qu'un ROI réel
exclue zéro à 95 % :
    R1  effet attendu +15 %  ->  n ≈ (1,96 × 1,4 / 0,15)² ≈ 335
    R2  effet attendu +20 %  ->  n ≈ (1,96 × 1,4 / 0,20)² ≈ 190
Les effets attendus sont volontairement plus bas que ceux de la recherche :
un effet trouvé en cherchant est presque toujours surestimé.

R3 — AJOUTÉE LE 09/10/2026 À 18:22 (même gel)
--------------------------------------------
Source : odds_alerts_log.jsonl, TOUS les matchs (pas besoin de fiche).
Recherche : etude_mouvements_grille.py, grille cote × mouvement, 108 cases ;
3 gagnantes contre 0 à 2 pour le témoin (p ≈ 4 %).

  R3  le joueur qui se renforce est coté 1,60 ≤ cote < 2,00 au relevé
      (~30 min avant) et sa cote a baissé de 3 % à moins de 6 % depuis
      le premier relevé -> jouer L'AUTRE joueur, à sa cote Pinnacle de
      clôture.

  Recherche : 138 matchs, +23 % [+4 ; +43]
              06 +43 %  07 +46 %  08 +34 %  09 −1 %  10 −4 %
  ÉTEINTE DEPUIS SEPTEMBRE dans la recherche : c'est précisément ce que
  le suivi doit trancher.

  Cible : effet attendu +15 % (contre +23 % trouvé), écart-type ~1,1
  à cote ~2,2 -> n ≈ (1,96 × 1,1 / 0,15)² ≈ 210.

R4 — GELÉE LE 10/10/2026 À 14:00 (jugée sur les matchs APRÈS le 10/10)
-----------------------------------------------------------------------
Source : la recherche sur tennis-data (etude_meilleurs.py,
etude_contre_top_tranches.py), clôtures Pinnacle 2010-2026, 56 461 matchs.
Ne dépend PAS des alertes : tous les matchs du circuit principal.

  R4  match du circuit principal ATP/WTA (ni Challenger, ni WTA 125, ni
      ITF), favori coté 1,60 ≤ cote < 2,01 à la clôture Pinnacle ; si
      l'OUTSIDER a un % de victoires sur 365 jours entre le 75e et le 90e
      centile de son circuit (au moins 20 matchs) -> jouer l'outsider, à
      sa cote Pinnacle de clôture (en pratique 1,95 – 2,55).

  Recherche : 1 724 paris, +5,5 % [+0,3 ; +10,7], 13 années sur 17
  positives, ATP +5,6 % et WTA +5,2 %, hasard 0,1 % (1 000 tirages).
  MAIS trouvée parmi une trentaine de découpes, et le top 10 % ne fait
  rien (−1,2 %) : effet peut-être surestimé.

  Centile : r4_centile.py. Résultats = tennis-data (historique/
  tennis_data_resultats.csv.gz, à remettre à jour de temps en temps),
  puis nos propres résultats du circuit principal après sa dernière date.

  Cible : à cote ~2,2 l'écart-type est ~1,1. Même avec un effet de +5 %,
  il faudrait n ≈ (1,96 × 1,1 / 0,05)² ≈ 1 900 paris pour l'exclure de
  zéro — 15 ans au rythme d'environ 120 paris par an. La cible est donc
  fixée à 300 (2 à 3 ans) avec un but plus modeste : vérifier qu'elle ne
  s'effondre pas. À 300 : ROI négatif -> RÉFUTÉE ; positif mais IC qui
  touche zéro -> NON CONCLUANT (on ne joue pas, on continue de suivre).

VERDICT, une fois la cible atteinte
-----------------------------------
  VALIDÉE        IC95 du ROI entièrement au-dessus de zéro
  RÉFUTÉE        ROI négatif
  NON CONCLUANT  entre les deux : on ne joue pas
Avant la cible : aucun verdict, quelle que soit l'allure des chiffres.
"""

import datetime
import math
import os
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import player_form as pf                                    # noqa: E402
import etude_difficulte_tous as edt                         # noqa: E402
import etude_tous_angles as eta                             # noqa: E402
import etude_alertes_mouvement as eam                       # noqa: E402
import etude_mouvements_grille as emg                       # noqa: E402

# ── PRÉ-ENREGISTREMENT DU 09/10/2026 — NE PAS MODIFIER ──────────────────
GEL = datetime.date(2026, 10, 9)        # jugé : matchs joués APRÈS cette date
COTE_MIN, COTE_MAX = 2.40, 4.00
AMPLEUR_MAX_R2 = 2.0                    # points de probabilité
N_CIBLE_R1 = 335
N_CIBLE_R2 = 190
SOURCES = ('COURBES', 'MOUVEMENT')
# R3, gelée le 09/10/2026 18:22
R3_COTE_MIN, R3_COTE_MAX = 1.60, 2.00
R3_MOUV_MIN, R3_MOUV_MAX = 3.0, 6.0     # baisse de cote, en %
N_CIBLE_R3 = 210
# R4, gelée le 10/10/2026 14:00
GEL_R4 = datetime.date(2026, 10, 10)
R4_FAV_MIN, R4_FAV_MAX = 1.60, 2.01     # cote Pinnacle de clôture du FAVORI
R4_CENT_MIN, R4_CENT_MAX = 0.75, 0.90   # centile du % de victoires sur 365 j
N_CIBLE_R4 = 300
# ────────────────────────────────────────────────────────────────────────
R4_RESULTATS = 'historique/tennis_data_resultats.csv.gz'
PROFILS = 'players_profile.json'


def paris():
    rows = eta.construire(eta.charger_prix(),
                          edt.charger_resultats(pf.charger_matchs()))
    G = eam.relier(eam.alertes_ampleur(), rows)
    vus, P = set(), []
    for src in SOURCES:
        for x in G.get(src, []):
            cle = (x['j'], x['o'], x['d'])
            if cle in vus:
                # Les deux sources ont alerté : on garde la PLUS PETITE
                # ampleur, pour ne pas faire entrer un pari dans R2 par
                # la source qui l'arrange.
                for p in P:
                    if (p['j'], p['o'], p['d']) == cle:
                        p['amp'] = min(p['amp'], x['amp'])
                continue
            vus.add(cle)
            P.append(dict(x))
    return [p for p in P if COTE_MIN <= p['pin'] < COTE_MAX]


def paris_r3():
    """Le joueur d'en face de celui qui se renforce, au format de paris()."""
    out = []
    for x in emg.charger():
        if not (R3_COTE_MIN <= x['releve'] < R3_COTE_MAX
                and R3_MOUV_MIN <= x['mv'] < R3_MOUV_MAX):
            continue
        if not x['pin_o']:
            continue
        out.append({'d': x['d'], 'j': x['o'], 'o': x['j'],
                    'pin': x['pin_o'], 'y': not x['y'],
                    'p': 1 / x['pin_o'] / 1.03})   # juste approchée (marge ~3 %)
    return out


def paris_r4():
    """(paris, info). Un pari par match : l'outsider, au format de paris()."""
    import csv
    import gzip
    import json
    import r4_centile as rc
    if not os.path.exists(R4_RESULTATS):
        return [], f'{R4_RESULTATS} absent — R4 non calculée'
    td = []
    with gzip.open(R4_RESULTATS, 'rt', encoding='utf-8') as g:
        for r in csv.DictReader(g):
            td.append((datetime.date.fromisoformat(r['date']), r['circuit'],
                       r['vainqueur'], r['perdant']))
    fin_td = {c: max(m[0] for m in td if m[1] == c) for c in ('ATP', 'WTA')
              if any(m[1] == c for m in td)}

    # Nos clés de joueurs -> nom tennis-data (pour ne faire qu'UN joueur)
    vers_td = {}
    try:
        J = json.load(open(PROFILS, encoding='utf-8')).get('joueurs', {})
        relier = rc.relier_td({k: (v.get('nom') or k, v.get('circuit'), v.get('n_cotes') or 0)
                               for k, v in J.items()})
        cand = defaultdict(set)
        for _, c, w, l in td:
            for nom in (w, l):
                k = relier(nom, c.lower())
                if k:
                    cand[(c, k)].add(nom)
        vers_td = {ck: next(iter(s)) for ck, s in cand.items() if len(s) == 1}
    except (OSError, ValueError) as e:
        print(f'  R4 : {PROFILS} illisible ({e}), joueurs non reliés à tennis-data')

    def ident(c, k):
        return vers_td.get((c, k), 'nous:' + k)

    prix = eta.charger_prix()
    R = edt.charger_resultats(pf.charger_matchs())
    nos, cand_paris = [], []
    for (paire, jour), c in prix.items():
        r = [x for x in R.get(paire, []) if 0 <= (x[0] - jour).days <= edt.FENETRE_JOURS]
        if not r or len({x[1] for x in r}) > 1:
            continue
        circ = rc.circuit_principal(r[0][2])
        if not circ or len(c) != 2:
            continue
        vainqueur = r[0][1]
        j1, j2 = sorted(c)
        if jour > fin_td.get(circ, datetime.date.min):
            perdant = j2 if vainqueur == j1 else j1
            nos.append((jour, circ, ident(circ, vainqueur), ident(circ, perdant)))
        for j, o in ((j1, j2), (j2, j1)):
            if c[j]['p'] < .5 and R4_FAV_MIN <= c[o]['pin'] < R4_FAV_MAX:
                cand_paris.append({'d': jour, 'j': j, 'o': o, 'c': circ,
                                   'pin': c[j]['pin'], 'p': c[j]['p'],
                                   'y': vainqueur == j, 'id': ident(circ, j)})
    C = rc.centiles(td + nos, [(x['d'], x['c'], x['id']) for x in cand_paris])
    out = []
    for x in cand_paris:
        v = C.get((x['d'], x['c'], x['id']))
        if v and R4_CENT_MIN <= v[0] < R4_CENT_MAX:
            x['centile'], x['taux'] = v
            out.append(x)
    info = (f'résultats tennis-data jusqu\'au '
            + ', '.join(f'{c} {d:%d/%m}' for c, d in fin_td.items())
            + f', puis {len(nos)} de nos matchs ; {len(cand_paris)} outsiders '
            f'dans la tranche de cote, {sum(1 for x in cand_paris if C.get((x["d"], x["c"], x["id"])))} '
            f'avec un % sur 365 j, {len(out)} paris R4')
    return out, info


def bilan(g):
    v = [(x['pin'] - 1) if x['y'] else -1.0 for x in g]
    if len(v) < 2:
        return len(v), None, None, None
    m = st.mean(v)
    h = 1.96 * st.stdev(v) / math.sqrt(len(v))
    return len(v), m, m - h, m + h


def verdict(n, m, lo, hi, cible):
    if n < cible:
        return f'EN COURS — {n}/{cible} ({100*n/cible:.0f} %), aucun verdict avant la cible'
    if lo > 0:
        return 'VALIDÉE — IC95 entièrement au-dessus de zéro'
    if m < 0:
        return 'RÉFUTÉE — ROI négatif'
    return 'NON CONCLUANT — on ne joue pas'


def afficher(nom, g, cible):
    n, m, lo, hi = bilan(g)
    print(f'\n  {nom}')
    if not n:
        print('    aucun pari pour l\'instant')
        print(f'    {verdict(0, 0, 0, 0, cible)}')
        return
    gagne = sum(x['y'] for x in g) / n
    juste = st.mean(x['p'] for x in g)
    if m is not None:
        print(f'    n={n}   ROI {100*m:+.1f} %  IC95 [{100*lo:+.1f} ; {100*hi:+.1f}]')
    print(f'    gagne {100*gagne:.1f} % des matchs, la cote juste en donnait {100*juste:.1f} %')
    M = defaultdict(list)
    for x in g:
        M[x['d'].strftime('%Y-%m')].append(x)
    print('    par mois : ' + '   '.join(
        f'{k[5:]}: {100*st.mean([(x["pin"]-1) if x["y"] else -1 for x in M[k]]):+.0f} % ({len(M[k])})'
        for k in sorted(M)))
    print(f'    {verdict(n, m or 0, lo or 0, hi or 0, cible)}')


def main():
    P = paris()
    avant = [p for p in P if p['d'] <= GEL]
    apres = [p for p in P if p['d'] > GEL]
    print('=' * 78)
    print(f'SUIVI PRÉ-ENREGISTRÉ — gelé le {GEL}, jugé sur les matchs après cette date')
    print('=' * 78)
    print(f'  R1/R2 : alerte courbes ou « Mouvement de cote », joueur coté '
          f'{COTE_MIN:.2f}–{COTE_MAX:.2f}')
    print('  chez Pinnacle avant le match, joué au prix Pinnacle de clôture.')
    print('  R3 : journal des mouvements, voir l\'en-tête du script.')

    print('\n' + '-' * 78)
    print('LE VERDICT — matchs APRÈS le gel (les seuls qui comptent)')
    print('-' * 78)
    afficher('R1  toutes ampleurs', apres, N_CIBLE_R1)
    afficher(f'R2  mouvement < {AMPLEUR_MAX_R2:.0f} pts',
             [p for p in apres if p['amp'] < AMPLEUR_MAX_R2], N_CIBLE_R2)

    R3 = paris_r3()
    afficher(f'R3  cote {R3_COTE_MIN:.2f}–{R3_COTE_MAX:.2f} qui baisse de '
             f'{R3_MOUV_MIN:.0f} à {R3_MOUV_MAX:.0f} % -> jouer l\'AUTRE',
             [p for p in R3 if p['d'] > GEL], N_CIBLE_R3)

    R4, info4 = paris_r4()
    afficher(f'R4  outsider du 75-90e centile (% victoires 365 j), favori '
             f'{R4_FAV_MIN:.2f}–{R4_FAV_MAX - .01:.2f} (gel {GEL_R4:%d/%m})',
             [p for p in R4 if p['d'] > GEL_R4], N_CIBLE_R4)
    print(f'    ({info4})')

    print('\n' + '-' * 78)
    print('POUR MÉMOIRE — la période qui a servi à CHOISIR la règle (ne compte pas)')
    print('-' * 78)
    for nom, g in (('R1', avant),
                   ('R2', [p for p in avant if p['amp'] < AMPLEUR_MAX_R2]),
                   ('R3', [p for p in R3 if p['d'] <= GEL]),
                   ('R4', [p for p in R4 if p['d'] <= GEL_R4])):
        n, m, lo, hi = bilan(g)
        if m is not None:
            print(f'  {nom}  n={n}   ROI {100*m:+.1f} %  IC95 [{100*lo:+.1f} ; {100*hi:+.1f}]')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
