#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
feuilles.py — lecture des feuilles de match collectées (feuilles/AAAA-MM-JJ.jsonl.gz,
scripts/feuilles_match.py, source TennisApi) au même format que donnees.charger()
(archive Sackmann), pour prolonger les profils de service après juin 2026 et
comparer chaque match simulé à sa vraie feuille. 22/10/2026.

Correspondance des statistiques (période « ALL » = match entier) :
  firstServeAccuracy        1res balles dans le court / points de service
  firstServePointsAccuracy  points gagnés derrière la 1re / 1res balles dans le court
  secondServePointsAccuracy points gagnés derrière la 2e / points joués en 2e balle
  aces, doubleFaults, breakPointsSaved (sauvées / subies), serviceGamesTotal
"""
import datetime as dt
import glob
import gzip
import json
import os
import re

import donnees
import elo as E

CIRCUITS = {'atp': 'ATP', 'wta': 'WTA', 'challenger': 'CH', 'itf men': 'ITFH', 'itf women': 'ITF'}


def circuit_de(categorie):
    c = re.sub(r'\s+', ' ', str(categorie or '').strip().lower())
    if 'wta' in c and '125' in c:
        return 'WTA'
    return CIRCUITS.get(c, 'ATP')


def surface_de(texte):
    t = str(texte or '').lower()
    if 'clay' in t:
        return 'Clay'
    if 'grass' in t:
        return 'Grass'
    return 'Hard'


def _v(st, k, i):
    x = (st.get(k) or [None] * 4)[i]
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def detail(st, cote):
    """Tuple donnees.DETAIL (svpt, in1, w1, w2, ace, df, bpf, bps, sg) d'un joueur ; None si incohérent.
    cote : 0 = home, 2 = away (index des valeurs dans les stats compactes)."""
    in1, svpt = _v(st, 'firstServeAccuracy', cote), _v(st, 'firstServeAccuracy', cote + 1)
    w1 = _v(st, 'firstServePointsAccuracy', cote)
    w2 = _v(st, 'secondServePointsAccuracy', cote)
    ace, df = _v(st, 'aces', cote), _v(st, 'doubleFaults', cote)
    bps, bpf = _v(st, 'breakPointsSaved', cote), _v(st, 'breakPointsSaved', cote + 1)
    sg = _v(st, 'serviceGamesTotal', cote)
    v = (svpt, in1, w1, w2, ace, df, bpf, bps, sg)
    if None in v[:6] or svpt < 20 or not 0 < in1 < svpt or not 0 <= w1 <= in1 or not 0 <= w2 <= svpt - in1:
        return None
    if not 0 <= ace <= w1 or not 0 <= df <= svpt - in1 - w2:
        return None
    bpf, bps, sg = (bpf or 0), (bps or 0), (sg or 0)
    if bps > bpf:
        return None
    return (svpt, in1, w1, w2, ace, df, bpf, bps, sg)


def lire(racine, depuis=None, jusqu_au=None):
    """Toutes les fiches brutes (dicts) des partitions, filtrées par jour."""
    out = []
    for p in sorted(glob.glob(os.path.join(racine, 'feuilles', '*.jsonl.gz'))):
        jour = os.path.basename(p)[:10]
        if (depuis and jour < depuis) or (jusqu_au and jour > jusqu_au):
            continue
        try:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                out.extend(json.loads(l) for l in f if l.strip())
        except (OSError, ValueError):
            continue
    return out


def en_match(r):
    """Fiche -> match au format donnees.charger() (gagnant/perdant = clés E.cle), ou None."""
    if r.get('vainqueur') not in (1, 2) or not r.get('jour'):
        return None
    st = (r.get('stats') or {}).get('ALL') or {}
    dh, da = detail(st, 0), detail(st, 2)
    g, p = (r['home'], r['away']) if r['vainqueur'] == 1 else (r['away'], r['home'])
    sg, sp = (r['score_home'], r['score_away']) if r['vainqueur'] == 1 else (r['score_away'], r['score_home'])
    sets = list(zip(sg.get('sets') or [], sp.get('sets') or []))
    jour = dt.date.fromisoformat(r['jour'])
    det = None
    if dh and da:
        det = {'w': dh, 'l': da} if r['vainqueur'] == 1 else {'w': da, 'l': dh}
    complet = str((r.get('statut') or {}).get('texte') or '').lower() in ('ended', 'finished', 'terminé')
    return {'date': jour, 'fin': jour, 'circuit': circuit_de(r.get('categorie')), 'surface': surface_de(r.get('surface')),
            'bo': r.get('meilleur_des') or (5 if len(sets) > 3 else 3),
            'gagnant': E.cle(g.get('nom')), 'perdant': E.cle(p.get('nom')), 'nom_g': g.get('nom') or '', 'nom_p': p.get('nom') or '',
            'stats': ({'w': (det['w'][0], det['w'][2] + det['w'][3]), 'l': (det['l'][0], det['l'][2] + det['l'][3])} if det else None),
            'sets': sets, 'complet': complet, 'detail': det, 'tournoi': r.get('tournoi') or '',
            'tour': donnees.ORDRE_TOURS.get(str(r.get('tour') or '').upper(), 6), 'niveau': '', 'num': 0,
            'source': 'tennisapi', 'id': r.get('id')}


def charger(racine, depuis=None, jusqu_au=None):
    """Matchs (format donnees.charger) des feuilles collectées, triés par date."""
    out = [m for m in (en_match(r) for r in lire(racine, depuis, jusqu_au)) if m]
    out.sort(key=lambda m: (m['date'], m['id'] or 0))
    return out


# ------------------------------------------------------------------ retrouver un de nos matchs
def _mots(n):
    return {w for w in donnees.norm(n) if len(w) >= 3}


class Index:
    """Retrouve la fiche d'un match (jour ± 1, deux joueurs) : clé complète des noms, sinon un mot
    commun (≥ 3 lettres) avec chacun des deux joueurs — « Fils A. » retrouve « Arthur Fils »."""

    def __init__(self, fiches):
        self.k, self.j = {}, {}
        for r in fiches:
            if not r.get('jour'):
                continue
            h, a = r['home'].get('nom'), r['away'].get('nom')
            self.k.setdefault((r['jour'], frozenset((E.cle(h), E.cle(a)))), []).append(r)
            self.j.setdefault(r['jour'], []).append(r)

    @staticmethod
    def _meme(nom, r_nom):
        return E.cle(nom) == E.cle(r_nom) or bool(_mots(nom) & _mots(r_nom))

    def trouver(self, jour, home, away):
        """(fiche, inverse) — inverse=True si la fiche a home et away échangés ; (None, False) sinon."""
        d0 = dt.date.fromisoformat(str(jour)[:10])
        jours = [(d0 + dt.timedelta(days=k)).isoformat() for k in (0, -1, 1)]
        for d in jours:
            c = self.k.get((d, frozenset((E.cle(home), E.cle(away))))) or []
            if len(c) == 1:
                return c[0], E.cle(c[0]['home'].get('nom')) != E.cle(home)
        for d in jours:
            c = []
            for r in self.j.get(d, []):
                rh, ra = r['home'].get('nom'), r['away'].get('nom')
                if self._meme(home, rh) and self._meme(away, ra):
                    c.append((r, False))
                elif self._meme(home, ra) and self._meme(away, rh):
                    c.append((r, True))
            if len(c) == 1:
                return c[0]
        return None, False


def feuille_reelle(r, inverse=False):
    """Feuille lisible (mêmes clés que match_simule.feuille_derivee) pour home puis away, ou None."""
    st = (r.get('stats') or {}).get('ALL') or {}
    dh, da = detail(st, 0), detail(st, 2)
    if not dh or not da:
        return None
    jh = sum(r['score_home'].get('sets') or [])
    ja = sum(r['score_away'].get('sets') or [])

    def f(d, o, jeux):
        sv, in1, w1, w2, ace, df, bpf, bps, sg = d
        return {'aces': ace, 'doubles_fautes': df, 'premiere_pct': 100 * in1 / sv, 'gagnes_1re_pct': 100 * w1 / in1,
                'gagnes_2e_pct': 100 * w2 / (sv - in1), 'balles_break_obtenues': o[6], 'breaks': o[6] - o[7], 'jeux': jeux}
    out = [f(dh, da, jh), f(da, dh, ja)]
    return (out[::-1] if inverse else out), jh + ja
