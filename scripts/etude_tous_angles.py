#!/usr/bin/env python3
"""etude_tous_angles.py — chaque paramètre de la fiche, chaque tranche, dans
les DEUX sens, au prix Pinnacle et au meilleur prix jouable.

    python scripts/etude_tous_angles.py

LECTURE SEULE. N'écrit rien, ne sort pas sur le réseau, relançable.

LA DEMANDE (Lucas, 09/10)
-------------------------
« Je ne te demande pas de battre Pinnacle, c'est de trouver un avantage,
une information. Analyse en jouant l'inverse. Sous tous les angles. »

Donc :
  — l'avantage se mesure en argent, au prix qu'on peut VRAIMENT prendre :
    le meilleur des books jouables depuis la France, pas seulement Pinnacle ;
  — chaque tranche de chaque paramètre est jouée des deux côtés : le joueur,
    et son adversaire (l'inverse) ;
  — et un TÉMOIN dit combien de « trouvailles » le hasard seul produit
    quand on regarde autant d'angles. Sans lui, regarder 200 cases garantit
    d'en trouver une dizaine qui « marchent ».

LES PARAMÈTRES, POINT-IN-TIME (matchs strictement antérieurs)
-------------------------------------------------------------
  classement      médiane de ses cotes justes (sa cote « classement marché »)
  cote_adv        médiane du classement de ses adversaires habituels
  cote_match      sa cote Pinnacle du jour
  ec              cote du jour contre son classement (pts, + = coté plus fort)
  ec_adv          adversaire du jour contre ses adversaires habituels
                  (pts, + = adversaire plus faible que d'habitude)
  statut          victoires − attendu dans le statut du jour (favori ou
                  outsider), divisé par (n + 10)
  bilan_fav       victoires − attendu en favori, divisé par (n + 10)
  bilan_out       idem en outsider
  forme           victoires − attendu sur ses 10 derniers matchs
  adv_statut      le « statut » de l'adversaire du jour
  diff_class      son classement moins celui de l'adversaire, contre la cote
                  du jour (le match est-il coté comme les deux classements
                  le laisseraient attendre ?)

LES PRIX
--------
  Pinnacle      dernière cote avant le coup d'envoi (courbes)
  meilleur      la meilleure dernière cote avant le coup d'envoi parmi les
                books jouables depuis la France, relevée dans l'heure qui
                précède — un prix vieux de six heures n'était peut-être
                plus là.
"""

import math
import os
import statistics as st
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import player_form as pf                                    # noqa: E402
import etude_difficulte_tous as edt                         # noqa: E402

MIN_COTES = int(os.environ.get('MIN_COTES', '4'))
RETRAIT = 10
TRANCHES = 5
JOUABLES = {'unibet', 'unibet.fr', 'bwin', 'betsson', 'bet365', 'bet365.fr',
            '888sport', 'betway', 'leovegas', 'winamax.fr', 'pmu', 'netbet',
            'williamhill', 'coolbet'}
FRAICHEUR_S = 3600


def charger_prix():
    """{(paire, date): {cle: {'pin': brut, 'p': juste, 'best': meilleur}}}"""
    pin, soft = {}, defaultdict(dict)
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
            book = (r.get('book') or '').lower()
            if book != pf.SHARP and book not in JOUABLES:
                continue
            ct = pf._dt(r.get('commence_time'))
            if not ct:
                continue
            ka = pf.cle_joueur(r.get('home_team') or r.get('home'))
            kb = pf.cle_joueur(r.get('away_team') or r.get('away'))
            if not ka or not kb or ka == kb:
                continue
            dern = []
            for cle_c in ('home_curve', 'away_curve'):
                pts = [(pf._dt(q[0]), q[1]) for q in (r.get(cle_c) or [])
                       if q and q[1] and pf._dt(q[0]) and pf._dt(q[0]) < ct]
                dern.append(pts[-1] if pts else None)
            if not dern[0] or not dern[1]:
                continue
            try:
                oh, oa = float(dern[0][1]), float(dern[1][1])
            except (TypeError, ValueError):
                continue
            if oh <= 1 or oa <= 1:
                continue
            k = (frozenset((ka, kb)), ct.date())
            if book == pf.SHARP:
                ih, ia = 1 / oh, 1 / oa
                pin[k] = {ka: (oh, ih / (ih + ia)), kb: (oa, ia / (ih + ia))}
            else:
                frais = min((ct - dern[0][0]).total_seconds(),
                            (ct - dern[1][0]).total_seconds()) <= FRAICHEUR_S
                if not frais:
                    continue
                for j, o in ((ka, oh), (kb, oa)):
                    if o > soft[k].get(j, 0):
                        soft[k][j] = o
    out = {}
    for k, c in pin.items():
        out[k] = {j: {'pin': o, 'p': p, 'best': soft.get(k, {}).get(j)}
                  for j, (o, p) in c.items()}
    return out


def construire(prix, R):
    par_jour = defaultdict(list)
    for (paire, d), c in prix.items():
        par_jour[d].append((paire, c))
    hist = defaultdict(list)            # ses probas justes
    hist_adv = defaultdict(list)        # classement de ses adversaires
    fav = defaultdict(lambda: [0, 0.0])
    out = defaultdict(lambda: [0, 0.0])
    recents = defaultdict(list)         # (y − p) des derniers matchs
    rows = []
    for jour in sorted(par_jour):
        resolus = []
        for paire, c in par_jour[jour]:
            r = [x for x in R.get(paire, [])
                 if 0 <= (x[0] - jour).days <= edt.FENETRE_JOURS]
            if not r or len({x[1] for x in r}) > 1:
                continue
            vainqueur = r[0][1]
            resolus.append((c, vainqueur))
            j1, j2 = sorted(c)
            for j, o in ((j1, j2), (j2, j1)):
                if len(hist[j]) < MIN_COTES:
                    continue
                p = c[j]['p']
                med = st.median(hist[j])
                med_o = st.median(hist[o]) if len(hist[o]) >= MIN_COTES else None
                n_f, s_f = fav[j]
                n_o, s_o = out[j]
                sj = (fav if p >= .5 else out)[j]
                so = (fav if (1 - p) >= .5 else out)[o]
                x = {
                    'd': jour, 'j': j, 'o': o, 'y': vainqueur == j,
                    'p': p, 'pin': c[j]['pin'], 'best': c[j]['best'],
                    'pin_o': c[o]['pin'], 'best_o': c[o]['best'],
                    'classement': 1 / med,
                    'cote_match': c[j]['pin'],
                    'ec': (p - med) * 100,
                    'statut': 100 * sj[1] / (sj[0] + RETRAIT),
                    'bilan_fav': 100 * s_f / (n_f + RETRAIT),
                    'bilan_out': 100 * s_o / (n_o + RETRAIT),
                    'forme': 100 * sum(recents[j][-10:]) / (len(recents[j][-10:]) + RETRAIT),
                    'adv_statut': 100 * so[1] / (so[0] + RETRAIT),
                    'cote_adv': (1 / st.median(hist_adv[j])
                                 if len(hist_adv[j]) >= MIN_COTES else None),
                    'ec_adv': ((st.median(hist_adv[j]) - med_o) * 100
                               if med_o is not None
                               and len(hist_adv[j]) >= MIN_COTES else None),
                    # Proba « attendue » d'après les deux classements seuls
                    # (rapport de forces), contre la proba du jour.
                    'diff_class': (None if med_o is None else
                                   (p - med / (med + med_o)) * 100),
                }
                rows.append(x)
        for c, vainqueur in resolus:
            j1, j2 = sorted(c)
            meds = {j: (st.median(hist[j]) if hist[j] else None) for j in (j1, j2)}
            for j, o in ((j1, j2), (j2, j1)):
                p = c[j]['p']
                y = 1.0 if vainqueur == j else 0.0
                t = fav if p >= .5 else out
                t[j][0] += 1
                t[j][1] += y - p
                recents[j].append(y - p)
                if meds[o] is not None:
                    hist_adv[j].append(meds[o])
            hist[j1].append(c[j1]['p'])
            hist[j2].append(c[j2]['p'])
    return rows


PARAMS = ['classement', 'cote_adv', 'cote_match', 'ec', 'ec_adv', 'statut',
          'bilan_fav', 'bilan_out', 'forme', 'adv_statut', 'diff_class']


def gains(g, cote_cle, cote_cle_o, inverse):
    v = []
    for x in g:
        if inverse:
            c, gagne = x[cote_cle_o], not x['y']
        else:
            c, gagne = x[cote_cle], x['y']
        if c is None:
            continue
        v.append((c - 1) if gagne else -1.0)
    return v


def roi(v):
    if len(v) < 20:
        return None
    m = st.mean(v)
    h = 1.96 * st.stdev(v) / math.sqrt(len(v))
    return m, m - h, m + h


def cases(rows, valeurs=None):
    """Toutes les cases (paramètre, tranche, sens, prix) -> (n, ROI, lo, hi)."""
    out = []
    for prm in PARAMS:
        g_all = [(x, (valeurs[prm][i] if valeurs else x[prm]))
                 for i, x in enumerate(rows)]
        g_all = [(x, v) for x, v in g_all if v is not None]
        if len(g_all) < 100:
            continue
        vs = sorted(v for _, v in g_all)
        bornes = [vs[int(len(vs) * k / TRANCHES)] for k in range(1, TRANCHES)]
        for t in range(TRANCHES):
            lo_ = bornes[t - 1] if t else -1e18
            hi_ = bornes[t] if t < TRANCHES - 1 else 1e18
            g = [x for x, v in g_all if lo_ <= v < hi_]
            for prix, (cc, co) in (('Pinnacle', ('pin', 'pin_o')),
                                   ('meilleur', ('best', 'best_o'))):
                for inv in (False, True):
                    r = roi(gains(g, cc, co, inv))
                    if r:
                        out.append((prm, t, lo_, hi_, prix, inv, len(g), *r))
    return out


def main():
    print('Chargement (courbes Pinnacle + books jouables, coupe pré-match)…')
    matchs = pf.charger_matchs()
    prix = charger_prix()
    R = edt.charger_resultats(matchs)
    rows = construire(prix, R)
    jours = sorted({x['d'] for x in rows})
    nb = sum(1 for x in rows if x['best'])
    print(f'  paris possibles : {len(rows)} ({len(rows)//2} matchs env.), '
          f'{jours[0]} -> {jours[-1]}')
    print(f'  dont avec un meilleur prix jouable relevé dans l\'heure : {nb}')

    print('\n' + '=' * 78)
    print('0. LES TÉMOINS — jouer tout le monde, sans filtre')
    print('=' * 78)
    for prix_, cc in (('Pinnacle', 'pin'), ('meilleur jouable', 'best')):
        v = gains(rows, cc, cc, False)
        m, lo, hi = roi(v)
        print(f'  {prix_:18} n={len(v):5}  ROI {100*m:+6.1f} % [{100*lo:+6.1f};{100*hi:+6.1f}]')
    bp = [x['best'] / x['pin'] - 1 for x in rows if x['best']]
    print(f'  meilleur jouable vs Pinnacle : médiane {100*st.median(bp):+.1f} %,'
          f' plus haut que Pinnacle dans {100*sum(1 for z in bp if z > 0)/len(bp):.0f} % des cas')

    C = cases(rows)
    sig = [c for c in C if c[8] > 0]
    print('\n' + '=' * 78)
    print(f'1. TOUTES LES CASES — {len(C)} essais '
          f'({len(PARAMS)} paramètres × {TRANCHES} tranches × 2 sens × 2 prix)')
    print('=' * 78)
    print(f'  cases GAGNANTES dont l\'IC exclut zéro : {len(sig)}')
    for prm, t, lo_, hi_, prix_, inv, n, m, lo, hi in sorted(sig, key=lambda c: -c[7]):
        sens = "ADVERSAIRE" if inv else "joueur"
        print(f'    {prm:11} tranche {t+1} [{lo_:+.2f};{hi_:+.2f}]  jouer {sens:10}'
              f' {prix_:9} n={n:4}  ROI {100*m:+6.1f} % [{100*lo:+6.1f};{100*hi:+6.1f}]')

    # TÉMOIN : même balayage, paramètres mélangés entre les paris.
    rng = np.random.default_rng(20261009)
    comptes = []
    for _ in range(100):
        val = {}
        for prm in PARAMS:
            v = [x[prm] for x in rows]
            val[prm] = [v[i] for i in rng.permutation(len(v))]
        comptes.append(sum(1 for c in cases(rows, val) if c[8] > 0))
    comptes.sort()
    rang = sum(1 for z in comptes if z >= len(sig)) / len(comptes)
    print(f'\n  TÉMOIN (paramètres mélangés, 100 tirages) : cases gagnantes '
          f'médiane {comptes[50]}, 95e centile {comptes[94]}')
    print(f'  part des tirages SANS INFORMATION qui en trouvent au moins '
          f'{len(sig)} : {100*rang:.0f} %')

    print('\n' + '=' * 78)
    print('2. LES MEILLEURES CASES TIENNENT-ELLES DANS LE TEMPS ?')
    print('=' * 78)
    mil = jours[len(jours) // 2]
    meilleures = sorted(C, key=lambda c: -c[7])[:12]
    for prm, t, lo_, hi_, prix_, inv, n, m, lo, hi in meilleures:
        cc, co = ('pin', 'pin_o') if prix_ == 'Pinnacle' else ('best', 'best_o')
        g = [x for x in rows if x[prm] is not None and lo_ <= x[prm] < hi_]
        a = roi(gains([x for x in g if x['d'] < mil], cc, co, inv))
        b = roi(gains([x for x in g if x['d'] >= mil], cc, co, inv))
        f = lambda r: '   n<20  ' if not r else f'{100*r[0]:+6.1f} %'
        sens = "ADV" if inv else "jou"
        print(f'  {prm:11} T{t+1} {sens} {prix_:9} total {100*m:+6.1f} %  '
              f'avant {mil}: {f(a)}   après: {f(b)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
