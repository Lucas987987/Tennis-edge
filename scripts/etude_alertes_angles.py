#!/usr/bin/env python3
"""etude_alertes_angles.py — les paramètres de la fiche, sur les seuls matchs
ALERTÉS : toutes alertes confondues, puis hypothèse par hypothèse.

    python scripts/etude_alertes_angles.py

LECTURE SEULE. N'écrit rien, ne sort pas sur le réseau, relançable.

LA DEMANDE (Lucas, 09/10)
-------------------------
« Exceptionnellement, analyse seulement sur les données des alertes reçues,
de manière globale et propre à chaque hypothèse. »

La question n'est plus « la fiche bat-elle le marché ? » mais : PARMI LES
ALERTES, les paramètres de la fiche séparent-ils les bonnes des mauvaises ?
Un filtre qui garderait les alertes rentables serait une information,
même si la fiche seule n'en porte aucune.

LES SOURCES D'ALERTES
---------------------
  hXX_signal_log.jsonl   H13, H15, H16, H16-B, H17, H18, ZONE : joueur
                         signalé, cote et book au moment du signal
  odds_alerts_log.jsonl  « Mouvement de cote » : le côté dont la cote a
                         baissé (mv < 0)
  moves_detail_hist.csv  mouvements des courbes : le joueur « steamé »

« TOUTES » = l'union, un pari par (match, joueur). « Reçues » = celles
marquées envoyées sur Telegram (les logs H) plus les deux autres sources.

LES PRIX
--------
  au signal     la cote du log au moment de l'alerte (logs H seulement) :
                c'est ce qu'on aurait pris en recevant l'alerte
  Pinnacle      dernière cote avant le coup d'envoi, pour toutes les sources
  INVERSE       l'adversaire du joueur signalé, à sa cote Pinnacle de clôture

LIRE AVEC PRUDENCE
------------------
Les hypothèses comptent de 8 à 176 alertes, et il faut en plus que le
joueur ait au moins MIN_COTES cotes antérieures pour avoir une fiche :
beaucoup d'alertes portent sur des joueurs de Challenger peu cotés. Sous
30 paris, une case n'est pas affichée. Le témoin (paramètres mélangés)
dit combien de cases « gagnantes » le hasard produit à lui seul.
"""

import csv
import datetime
import json
import math
import os
import statistics as st
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import player_form as pf                                    # noqa: E402
import etude_difficulte_tous as edt                         # noqa: E402
import etude_tous_angles as eta                             # noqa: E402

N_MIN = 30
HYPOS = ['h13', 'h15', 'h16', 'h16b', 'h17', 'h18', 'zone']


def charger_alertes():
    """[(source, paire, date, joueur, cote_signal|None, envoye)]"""
    A = []
    for h in HYPOS:
        f = f'{h}_signal_log.jsonl'
        if not os.path.exists(f):
            continue
        for l in open(f, encoding='utf-8'):
            try:
                r = json.loads(l)
            except Exception:
                continue
            j, o = pf.cle_joueur(r.get('joueur')), pf.cle_joueur(r.get('adversaire'))
            c = (r.get('commence') or '')[:10]
            if not j or not o or j == o or not c:
                continue
            try:
                d = datetime.date.fromisoformat(c)
                cote = float(r['cote']) if r.get('cote') else None
            except (ValueError, TypeError):
                continue
            A.append((h.upper(), frozenset((j, o)), d, j, cote,
                      bool(r.get('envoye'))))
    if os.path.exists('odds_alerts_log.jsonl'):
        for l in open('odds_alerts_log.jsonl', encoding='utf-8'):
            try:
                r = json.loads(l)
                mh, ma = float(r['mv_home_pct']), float(r['mv_away_pct'])
                d = datetime.date.fromisoformat(r['commence_time'][:10])
            except Exception:
                continue
            h_, a_ = pf.cle_joueur(r.get('home')), pf.cle_joueur(r.get('away'))
            if not h_ or not a_ or h_ == a_ or mh == ma:
                continue
            j = h_ if mh < ma else a_
            A.append(('MOUVEMENT', frozenset((h_, a_)), d, j, None, True))
    if os.path.exists(edt.MOVES):
        for r in csv.DictReader(open(edt.MOVES, encoding='utf-8')):
            j, o = pf.cle_joueur(r.get('steame')), pf.cle_joueur(r.get('opp'))
            try:
                d = datetime.date.fromisoformat(r['date'])
            except (ValueError, KeyError, TypeError):
                continue
            if j and o and j != o:
                A.append(('COURBES', frozenset((j, o)), d, j, None, True))
    return A


def relier(A, rows):
    """Attache chaque alerte à la ligne (match, joueur) de l'étude, à ±1 jour."""
    idx = {}
    for x in rows:
        idx[(frozenset((x['j'], x['o'])), x['d'], x['j'])] = x
    out = defaultdict(list)
    vus = defaultdict(set)
    for src, paire, d, j, cote, env in A:
        x = None
        for k in (0, -1, 1):
            x = idx.get((paire, d + datetime.timedelta(days=k), j))
            if x:
                break
        if not x:
            continue
        cle = (paire, x['d'], j)
        b = dict(x, signal=cote, envoye=env)
        for grp in (src, 'TOUTES') + (('REÇUES',) if env else ()):
            if cle in vus[grp]:
                continue
            vus[grp].add(cle)
            out[grp].append(b)
    return out


def gains(g, sens):
    v = []
    for x in g:
        if sens == 'signal':
            c, ok = x['signal'], x['y']
        elif sens == 'pin':
            c, ok = x['pin'], x['y']
        else:                       # inverse
            c, ok = x['pin_o'], not x['y']
        if c:
            v.append((c - 1) if ok else -1.0)
    return v


def roi(v):
    if len(v) < N_MIN:
        return None
    m = st.mean(v)
    h = 1.96 * st.stdev(v) / math.sqrt(len(v))
    return m, m - h, m + h


def fmt(r):
    if not r:
        return '        —          '
    m, lo, hi = r
    f = '*' if (lo > 0 or hi < 0) else ' '
    return f'{100*m:+6.1f}% [{100*lo:+5.0f};{100*hi:+4.0f}]{f}'


FILTRES = [
    ('cote du jour < classement (ec > +10)', lambda x: x['ec'] > 10),
    ('cote du jour ≈ classement', lambda x: -10 <= x['ec'] <= 10),
    ('cote du jour > classement (ec < −10)', lambda x: x['ec'] < -10),
    ('favori (Pinnacle)', lambda x: x['p'] >= .5),
    ('outsider (Pinnacle)', lambda x: x['p'] < .5),
    ('statut du jour : surperforme', lambda x: x['statut'] > 0),
    ('statut du jour : sous-performe', lambda x: x['statut'] <= 0),
    ('adversaire plus faible que d\'hab.', lambda x: x['ec_adv'] is not None and x['ec_adv'] > 5),
    ('adversaire plus fort que d\'hab.', lambda x: x['ec_adv'] is not None and x['ec_adv'] < -5),
    ('forme récente positive', lambda x: x['forme'] > 0),
    ('forme récente négative', lambda x: x['forme'] <= 0),
    ('adversaire surperforme (son statut)', lambda x: x['adv_statut'] > 0),
    ('adversaire sous-performe', lambda x: x['adv_statut'] <= 0),
]


def balayage(g, val=None):
    """Toutes les cases (filtre × sens) -> liste de (filtre, sens, n, roi)."""
    out = []
    for i, (nom, f) in enumerate(FILTRES):
        if val is None:
            s = [x for x in g if f(x)]
        else:
            s = [g[k] for k in val[i]]
        for sens in ('signal', 'pin', 'inverse'):
            r = roi(gains(s, sens))
            if r:
                out.append((nom, sens, len(s), r))
    return out


def bloc(nom, g, rng, temoin=True):
    jours = sorted({x['d'] for x in g})
    print('\n' + '=' * 78)
    print(f'{nom} — {len(g)} alertes avec une fiche ({jours[0]} -> {jours[-1]})')
    print('=' * 78)
    print(f'  {"":38} {"joueur, cote au signal":22} {"joueur, Pinnacle":22} {"INVERSE (adv.)":22}')
    print(f'  {"toutes":38}', *(fmt(roi(gains(g, s))) for s in ('signal', 'pin', 'inverse')))
    for fn, f in FILTRES:
        s = [x for x in g if f(x)]
        print(f'  {fn[:38]:38}', *(fmt(roi(gains(s, sens))) for sens in ('signal', 'pin', 'inverse')))
    C = balayage(g)
    sig = [c for c in C if c[3][1] > 0]
    print(f'  cases gagnantes (* = IC au-dessus de zéro) : {len(sig)} sur {len(C)}')
    if not temoin or not C:
        return
    # Témoin : mêmes tailles de sous-groupes, tirés au hasard dans le bloc.
    comptes = []
    for _ in range(200):
        val = []
        for _, f in FILTRES:
            k = sum(1 for x in g if f(x))
            val.append(list(rng.choice(len(g), size=k, replace=False)))
        comptes.append(sum(1 for c in balayage(g, val) if c[3][1] > 0))
    comptes.sort()
    rang = sum(1 for z in comptes if z >= len(sig)) / len(comptes)
    print(f'  TÉMOIN (sous-groupes tirés au hasard, 200 fois) : médiane '
          f'{comptes[100]}, 95e centile {comptes[189]} — part qui fait au '
          f'moins aussi bien : {100*rang:.0f} %')
    if sig:
        mil = jours[len(jours) // 2]
        print(f'  stabilité des cases gagnantes (avant / à partir du {mil}) :')
        for fn, sens, n, r in sig:
            f = dict(FILTRES)[fn]
            s = [x for x in g if f(x)]
            a = gains([x for x in s if x['d'] < mil], sens)
            b = gains([x for x in s if x['d'] >= mil], sens)
            ma = f'{100*st.mean(a):+6.1f}% (n={len(a)})' if len(a) > 1 else '—'
            mb = f'{100*st.mean(b):+6.1f}% (n={len(b)})' if len(b) > 1 else '—'
            print(f'    {fn[:36]:36} {sens:8} {ma:18} {mb}')


def main():
    print('Chargement (courbes, résultats, logs d\'alertes)…')
    matchs = pf.charger_matchs()
    rows = eta.construire(eta.charger_prix(), edt.charger_resultats(matchs))
    A = charger_alertes()
    G = relier(A, rows)
    brut = defaultdict(int)
    for a in A:
        brut[a[0]] += 1
    print('  alertes lues -> reliées à un match coté, dénoué, joueur avec fiche :')
    for k in sorted(brut):
        print(f'    {k:10} {brut[k]:5} -> {len(G.get(k, [])):5}')
    rng = np.random.default_rng(20261009)
    for nom in ['TOUTES', 'REÇUES', 'COURBES', 'MOUVEMENT'] + [h.upper() for h in HYPOS]:
        g = G.get(nom, [])
        if len(g) < N_MIN:
            print(f'\n{nom} : {len(g)} alertes reliées — moins de {N_MIN}, '
                  f'rien de mesurable.')
            continue
        bloc(nom, g, rng)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
