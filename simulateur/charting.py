#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
charting.py — le « comment » du jeu, d'après le Match Charting Project (22/10/2026, point 7).

Le Match Charting Project (Jeff Sackmann et ses bénévoles, CC BY-NC-SA 4.0) relève point par
point ~1 300 matchs par an, surtout du haut du classement. On en tire, pour chaque joueur et
à une date donnée (matchs relevés AVANT cette date seulement) :
  — premier_coup : part de ses points de service gagnés en 3 frappes ou moins (service +
    coup suivant), au-delà de la moyenne du circuit ;
  — retour : part de ses retours remis en jeu, au-delà de la moyenne ;
  — echanges : part des points de ses matchs qui durent 7 frappes ou plus, au-delà de la moyenne.
Chaque valeur est ramenée vers 0 par un prior (K points) : un joueur peu relevé reste neutre.
Utilisé par facteurs.py (groupe « charting »), jugé avec la même règle que les autres facteurs.

Fichiers lus (dossier du dépôt cloné) : charting-{m,w}-matches.csv,
charting-{m,w}-stats-ServeBasics.csv, -ReturnOutcomes.csv, -Rally.csv.
"""
import bisect
import collections
import csv
import datetime as dt
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo as E  # noqa: E402

K_SERVICE, K_RETOUR, K_ECHANGES = 300.0, 300.0, 600.0
FICHIERS = ('matches', 'stats-ServeBasics', 'stats-ReturnOutcomes', 'stats-Rally')


def _lire(chemin):
    try:
        with open(chemin, encoding='utf-8', errors='replace', newline='') as f:
            yield from csv.DictReader(f)
    except OSError:
        return


def _i(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def charger(dossier, cle=E.cle):
    """{joueur: [(date, srv_pts, srv_courts, ret_pts, ret_en_jeu, pts_match, pts_longs)]} trié par date."""
    out = collections.defaultdict(list)
    if not dossier or not os.path.isdir(dossier):
        return {}
    for sexe in ('m', 'w'):
        base = lambda n: os.path.join(dossier, f"charting-{sexe}-{n}.csv")
        dates, joueurs = {}, {}
        for r in _lire(base('matches')):
            try:
                dates[r['match_id']] = dt.datetime.strptime(r['Date'][:8], '%Y%m%d').date()
                joueurs[r['match_id']] = (r['Player 1'], r['Player 2'])
            except (KeyError, ValueError):
                continue
        srv, ret, ral = collections.defaultdict(dict), collections.defaultdict(dict), collections.defaultdict(lambda: [0, 0])
        for r in _lire(base('stats-ServeBasics')):
            if r.get('row') == 'Total':
                srv[r['match_id']][r['player']] = (_i(r.get('pts')), _i(r.get('pts_won_lte_3_shots')))
        for r in _lire(base('stats-ReturnOutcomes')):
            if r.get('row') == 'Total':
                ret[r['match_id']][r['player']] = (_i(r.get('pts')), _i(r.get('in_play')))
        for r in _lire(base('stats-Rally')):
            if r.get('row') in ('1-3', '4-6', '7-9', '10'):
                x = ral[r['match_id']]
                x[0] += _i(r.get('pts'))
                if r['row'] in ('7-9', '10'):
                    x[1] += _i(r.get('pts'))
        for mid, d in dates.items():
            pm, pl = ral.get(mid, (0, 0))
            for nom in joueurs[mid]:
                sp, sc = srv.get(mid, {}).get(nom, (0, 0))
                rp, ri = ret.get(mid, {}).get(nom, (0, 0))
                if sp or rp or pm:
                    out[cle(nom)].append((d, sp, sc, rp, ri, pm, pl))
    for L in out.values():
        L.sort()
    return dict(out)


class Charting:
    """Profils point-in-time ; profil(j, date) → (premier_coup, retour, echanges), écarts à la moyenne."""

    def __init__(self, donnees):
        self.D = donnees or {}
        self.dates = {j: [e[0] for e in L] for j, L in self.D.items()}
        self.cum = {}
        for j, L in self.D.items():
            c, acc = [], [0, 0, 0, 0, 0, 0]
            for e in L:
                acc = [a + b for a, b in zip(acc, e[1:])]
                c.append(tuple(acc))
            self.cum[j] = c
        tot = [0, 0, 0, 0, 0, 0]
        for c in self.cum.values():
            if c:
                tot = [a + b for a, b in zip(tot, c[-1])]
        self.moy = (tot[1] / tot[0] if tot[0] else 0.3, tot[3] / tot[2] if tot[2] else 0.7, tot[5] / tot[4] if tot[4] else 0.2)

    def profil(self, j, date):
        L = self.cum.get(j)
        if not L:
            return 0.0, 0.0, 0.0
        k = bisect.bisect_left(self.dates[j], date)          # matchs relevés strictement avant `date`
        if k == 0:
            return 0.0, 0.0, 0.0
        sp, sc, rp, ri, pm, pl = L[k - 1]
        m1, m2, m3 = self.moy
        return ((sc + K_SERVICE * m1) / (sp + K_SERVICE) - m1, (ri + K_RETOUR * m2) / (rp + K_RETOUR) - m2,
                (pl + K_ECHANGES * m3) / (pm + K_ECHANGES) - m3)

    def exporter(self, joueurs, date):
        out = {}
        for j in joueurs:
            p = self.profil(j, date)
            if any(abs(x) > 1e-4 for x in p):
                out[j] = [round(x, 4) for x in p]
        return out


class ChartingFige:
    """Profils déjà calculés (contexte du jour) : même interface."""

    def __init__(self, d):
        self.d = d or {}

    def profil(self, j, date=None):
        return tuple(self.d.get(j) or (0.0, 0.0, 0.0))


def variables(pj, pa):
    """Variables du point de vue du serveur j contre adv (profils (premier_coup, retour, echanges))."""
    return {'mcp_premier_coup_srv': 10 * pj[0], 'mcp_retour_adv': 10 * pa[1], 'mcp_duel': 100 * pj[0] * pa[1],
            'mcp_echanges': 10 * (pj[2] - pa[2])}
