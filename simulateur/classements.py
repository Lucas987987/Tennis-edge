#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
classements.py — le classement ATP/WTA de chaque joueur À LA DATE d'un match (23/10/2026).

Sources, toujours le dernier classement connu AVANT le match (jamais d'information future) :
  — archive Sackmann : classements hebdomadaires 2020 → 8 juin 2026 (atp/wta_rankings_20s.csv, _current.csv,
    noms par atp/wta_players.csv) ;
  — TennisApi : une photo par jour depuis le 23/10/2026 (feuilles/classements/, scripts/classements_tennisapi.py).
Pourquoi : la plus grosse erreur du modèle reste le joueur peu connu (moins de 30 matchs : il gagne 31 % de ses
matchs face à un joueur rodé). Son classement dit d'où il vient : un 140e qui arrive en Challenger n'est pas un
900e sorti des ITF.
"""
import bisect
import csv
import datetime as dt
import glob
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo as E  # noqa: E402

DEPUIS = 20250101          # les classements plus anciens ne servent pas (les matchs jugés datent de 2026)
RANG_PIVOT = 150.0         # au-dessus : plus fort que la moyenne des nouveaux venus ; en dessous : plus faible


def _fichier(dossier, nom):
    for p in glob.glob(os.path.join(dossier, '**', nom), recursive=True):
        return p
    return None


class Classements:
    def __init__(self):
        self.h = {}            # clé -> [(date ordinale, rang)] triés
        self.pts = {}          # 30/10/2026 : clé -> [(date ordinale, points)] triés
        self.courbe = {}       # 30/10/2026 : circuit ('ATP'/'WTA') -> {rang: points} du dernier classement complet (archive)
        self.photo = {}        # 30/10/2026 : circuit -> (date ordinale, {rang: points}) de la dernière photo TennisApi
        self._courbe_dates = {}

    def ajouter(self, cle, jour, rang, points=None):
        self.h.setdefault(cle, []).append((jour.toordinal(), int(rang)))
        try:
            if points is not None and str(points).strip() != '':
                self.pts.setdefault(cle, []).append((jour.toordinal(), int(float(points))))
        except (TypeError, ValueError):
            pass

    def finir(self):
        for L in self.h.values():
            L.sort()
        for L in self.pts.values():
            L.sort()
        return self

    def points_depuis_rang(self, circuit, rang):
        """30/10/2026 — points ESTIMÉS d'un joueur dont on ne connaît que le rang (au-delà du top 500 des photos
        TennisApi) : la courbe rang → points du dernier classement complet de l'archive, remise à l'échelle du jour par
        le rapport des points au 500e rang (photo du jour / archive). None sans courbe."""
        cb = self.courbe.get('WTA' if circuit == 'WTA' else 'ATP')
        if not cb or not rang:
            return None
        r = min(cb, key=lambda k: abs(k - int(rang)))
        if abs(r - int(rang)) > 50:
            return None
        echelle = 1.0
        ph = (self.photo.get('WTA' if circuit == 'WTA' else 'ATP') or (None, {}))[1]
        ref = max((k for k in ph if k <= 500 and ph[k]), default=None)
        if ref and cb.get(ref):
            echelle = ph[ref] / cb[ref]
        return max(0, int(round(cb[r] * echelle)))

    def points_au(self, cle, quand):
        """30/10/2026 — derniers points ATP/WTA connus STRICTEMENT avant le jour du match (None si inconnus)."""
        L = self.pts.get(cle)
        if not L:
            return None
        d = (quand.date() if isinstance(quand, dt.datetime) else quand).toordinal()
        i = bisect.bisect_left(L, (d, -1)) - 1
        return L[i][1] if i >= 0 else None

    def rang_au(self, cle, quand):
        """Dernier rang connu STRICTEMENT avant le jour du match (None si jamais classé)."""
        L = self.h.get(cle)
        if not L:
            return None
        d = (quand.date() if isinstance(quand, dt.datetime) else quand).toordinal()
        i = bisect.bisect_left(L, (d, -1)) - 1
        return L[i][1] if i >= 0 else None


def charger(dossier_sackmann=None, racine=None):
    C = Classements()
    if dossier_sackmann:
        for circ in ('atp', 'wta'):
            pj = _fichier(dossier_sackmann, f'{circ}_players.csv')
            if not pj:
                continue
            noms = {}
            with open(pj, encoding='utf-8', errors='replace') as f:
                for r in csv.DictReader(f):
                    noms[r['player_id']] = E.cle(f"{r.get('name_first') or ''} {r.get('name_last') or ''}".strip())
            for nom in (f'{circ}_rankings_20s.csv', f'{circ}_rankings_current.csv'):
                p = _fichier(dossier_sackmann, nom)
                if not p:
                    continue
                with open(p, encoding='utf-8', errors='replace') as f:
                    for r in csv.DictReader(f):
                        try:
                            d = int(r['ranking_date'])
                        except (KeyError, ValueError):
                            continue
                        if d < DEPUIS or not noms.get(r.get('player')):
                            continue
                        try:                       # 30/10/2026 : courbe rang → points du dernier classement complet
                            C_c = circ.upper()
                            if d > C._courbe_dates.get(C_c, 0):
                                C._courbe_dates[C_c], C.courbe[C_c] = d, {}
                            if d == C._courbe_dates[C_c] and r.get('points'):
                                C.courbe[C_c][int(r['rank'])] = int(float(r['points']))
                        except (TypeError, ValueError):
                            pass
                        C.ajouter(noms[r['player']], dt.date(d // 10000, d // 100 % 100, d % 100), r['rank'], r.get('points'))
    if racine and not dossier_sackmann:                        # pronostics du jour : l'archive résumée (exporter)
        try:
            ex = json.load(open(os.path.join(racine, 'simulateur', 'classements_sackmann.json'), encoding='utf-8'))
            j0 = dt.date.fromisoformat(ex['date'])
            pts = ex.get('points') or {}
            for cle, rang in (ex.get('rangs') or {}).items():
                C.ajouter(cle, j0, rang, pts.get(cle))
            for circ_, L_ in (ex.get('courbe') or {}).items():
                C.courbe[circ_] = {int(k): int(v) for k, v in L_}
        except (OSError, ValueError, KeyError):
            pass
    if racine:
        for p in sorted(glob.glob(os.path.join(racine, 'feuilles', 'classements', '*.json'))):
            try:
                doc = json.load(open(p, encoding='utf-8'))
                jour = dt.date.fromisoformat(os.path.basename(p)[:10])
            except (OSError, ValueError):
                continue
            for circ in ('ATP', 'WTA'):
                for cle, v in (doc.get(circ) or {}).items():
                    C.ajouter(cle, jour, v[0], v[1] if len(v) > 1 else None)
                if doc.get(circ):                      # 30/10/2026 : la dernière photo sert à l'échelle des points estimés
                    C.photo[circ] = (jour.toordinal(), {v[0]: v[1] for v in doc[circ].values() if len(v) > 1 and v[1]})
    return C.finir()


def ecart_points(p1, p2):
    """30/10/2026 — (ln(points joueur 1 + 1) − ln(points joueur 2 + 1),) ; None si l'un des deux est inconnu."""
    if p1 is None or p2 is None:
        return None
    return (round(math.log(p1 + 1) - math.log(p2 + 1), 5),)


def niveau_inconnu(rang, n_matchs):
    """Pour un joueur peu connu seulement (poids nouveau(n) : 1 → 0 à 30 matchs) : log10(rang / 150), borné
    à ±1,5 ; > 0 = plus faible qu'un 150e, < 0 = plus fort. Sans classement : 0,5 (souvent un joueur des ITF)."""
    poids = max(0.0, 1.0 - (n_matchs or 0) / 30.0)
    if not poids:
        return 0.0
    v = 0.5 if not rang else max(-1.5, min(1.5, math.log10(rang / RANG_PIVOT)))
    return poids * v


def exporter(C, chemin):
    """Dernier rang connu de chaque joueur dans l'archive (pour les pronostics du jour, sans l'archive)."""
    if not C.h:
        return 0
    der = max(L[-1][0] for L in C.h.values())
    rangs = {cle: L[-1][1] for cle, L in C.h.items() if L[-1][0] >= der - 21}
    points = {cle: L[-1][1] for cle, L in C.pts.items() if cle in rangs and L[-1][0] >= der - 21}   # 30/10/2026
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump({'date': dt.date.fromordinal(der).isoformat(), 'rangs': rangs, 'points': points,
                   'courbe': {c: sorted(v.items()) for c, v in C.courbe.items()}}, f, separators=(',', ':'))
    return len(rangs)
