#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
polymarket_common.py — Chargement partagé par les études Polymarket.

Regroupe ici ce que les trois études (dévigage, confirmateur, divergence)
utilisent en commun, pour qu'une correction de méthode ne s'applique qu'à un
seul endroit. C'est la leçon de player_match, dont trois copies divergentes
traînaient dans le dépôt.

CONVENTIONS
  • Toute probabilité renvoyée est celle du HOME LOCAL (celui de
    matches_oddspapi.json / book_curves), jamais celle d'un outcome Polymarket.
  • Tout est PRÉ-MATCH : un point postérieur au coup d'envoi ferait entrer le
    résultat dans la mesure.
  • Les séries sont triées par horodatage.
"""
import os
import sys
import json
import glob
import gzip
import datetime
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov  # noqa: E402

PM_GLOB     = os.environ.get('PM_TICKS_GLOB', 'parts/pm_ticks_*.jsonl')
CURVES      = os.environ.get('CURVES', 'book_curves_live.jsonl')
MARKET_TYPE = os.environ.get('MARKET_TYPE', 'match')
SHARP       = os.environ.get('SHARP_BOOK', 'pinnacle')
RESULTS     = os.environ.get('SET_RESULTS', 'set_results.json')
MAX_SPREAD  = float(os.environ.get('MAX_SPREAD_PTS', '10')) / 100.0
EXCHANGES   = set(b.strip() for b in os.environ.get(
    'EXCHANGES', 'betfair-ex,betfair,matchbook,smarkets,betdaq').split(',') if b.strip())


def dt(x):
    try:
        return datetime.datetime.fromisoformat(
            str(x).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def _open(p):
    return gzip.open(p, 'rt', encoding='utf-8') if p.endswith('.gz') else open(p, encoding='utf-8')


def shin_ph(oh, oa):
    """Probabilité du home, marge retirée. Normalisation 2 voies."""
    try:
        ih, ia = 1.0 / float(oh), 1.0 / float(oa)
    except Exception:
        return None
    s = ih + ia
    return (ih / s) if s > 0 else None


def charger_pm():
    """{uid: [(t, p_home, spread)]} reconstruit à partir des DEUX jetons.

    Le jeton away donne une seconde estimation (1 - mid). En moyennant, on
    divise le bruit de carnet par racine de 2. Les points dont la fourchette
    dépasse MAX_SPREAD sont écartés : sur un carnet trop large, le milieu de
    fourchette n'est pas une probabilité, c'est une interpolation.
    """
    brut = collections.defaultdict(lambda: {'home': [], 'away': []})
    n = 0
    for p in sorted(set(glob.glob(PM_GLOB) + glob.glob(PM_GLOB + '.gz'))):
        try:
            f = _open(p)
        except Exception:
            continue
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            n += 1
            if r.get('market_type') != MARKET_TYPE:
                continue
            uid, side, t = r.get('local_uid'), r.get('local_side'), dt(r.get('ts'))
            if not uid or side not in ('home', 'away') or t is None:
                continue
            m = r.get('mid')
            if m is None:
                continue
            try:
                m = float(m)
            except Exception:
                continue
            if not (0.0 < m < 1.0):
                continue
            sp = r.get('spread')
            try:
                sp = float(sp) if sp is not None else None
            except Exception:
                sp = None
            if sp is not None and sp > MAX_SPREAD:
                continue
            brut[uid][side].append((t, m, sp))

    out = {}
    for uid, d in brut.items():
        ev = [(t, 'home', m, s) for t, m, s in d['home']]
        ev += [(t, 'away', m, s) for t, m, s in d['away']]
        ev.sort()
        serie, ch, ca, sh, sa = [], None, None, None, None
        for t, side, m, s in ev:
            if side == 'home':
                ch, sh = m, s
            else:
                ca, sa = m, s
            if ch is not None and ca is not None:
                sp = max(x for x in (sh, sa) if x is not None) if (sh or sa) else None
                serie.append((t, (ch + (1.0 - ca)) / 2.0, sp))
            elif ch is not None:
                serie.append((t, ch, sh))
        if len(serie) >= 2:
            out[uid] = serie
    print(f"Polymarket : {n} ticks · {len(out)} match(s) exploitables "
          f"(fourchette max {MAX_SPREAD*100:.0f} pts)")
    return out


def charger_books(uids, books=None):
    """{uid: {book: {'serie': [(t, p_home)], 'ct': commence}}} — PRÉ-MATCH."""
    out = collections.defaultdict(dict)
    for src in (CURVES, 'book_curves.jsonl'):
        try:
            lines = list(ov.open_curves(src, verbose=False))
        except Exception:
            continue
        for line in lines:
            try:
                r = json.loads(line)
            except Exception:
                continue
            uid, bk = r.get('uid'), r.get('book')
            if uid not in uids or not bk or bk in EXCHANGES:
                continue
            if books and bk not in books:
                continue
            if bk in out[uid]:
                continue
            ct = dt(r.get('commence_time'))
            if not ct:
                continue
            h = sorted((dt(q[0]), float(q[1])) for q in (r.get('home_curve') or [])
                       if dt(q[0]) and q[1] and float(q[1]) > 1)
            a = sorted((dt(q[0]), float(q[1])) for q in (r.get('away_curve') or [])
                       if dt(q[0]) and q[1] and float(q[1]) > 1)
            h = [x for x in h if x[0] < ct]
            a = [x for x in a if x[0] < ct]
            if len(h) < 2 or len(a) < 2:
                continue
            ad, serie, last = dict(a), [], None
            cotes = []
            for t, ph in h:
                last = ad.get(t, last)
                if last is None:
                    continue
                p = shin_ph(ph, last)
                if p is not None:
                    serie.append((t, p))
                    cotes.append((t, ph, last))
            if len(serie) >= 2:
                out[uid][bk] = {'serie': serie, 'cotes': cotes, 'ct': ct}
    return out


def charger_resultats():
    """{uid: 'home'|'away'} depuis set_results.json.

    Lu PAR UID, jamais par ordre de slug : la clé de ce fichier est un uid de
    l'ancienne convention, et l'ordre des noms qu'elle contient ne correspond
    PAS au home/away réel (52 % d'inversions, cf. results_bridge.py). Le champ
    'match' vaut bien 'home'/'away' au sens de l'enregistrement de courbe :
    vérifié à 0,8 % d'erreur sur 1036 matchs.
    """
    if not os.path.exists(RESULTS):
        return {}
    try:
        d = json.load(open(RESULTS, encoding='utf-8'))
    except Exception:
        return {}
    return {k: v['match'] for k, v in d.items()
            if isinstance(v, dict) and v.get('match') in ('home', 'away')}


def valeur_a(serie, t):
    """Dernière valeur connue à t (escalier). Aucune anticipation possible."""
    v = None
    for item in serie:
        if item[0] > t:
            break
        v = item[1]
    return v


def instants_communs(pm, serie_book, ct, pas_min=5.0):
    """Instants où les DEUX sources ont une valeur, avant le coup d'envoi."""
    if not pm or not serie_book:
        return []
    t0 = max(pm[0][0], serie_book[0][0])
    t1 = min(pm[-1][0], serie_book[-1][0], ct)
    out, t = [], t0
    while t <= t1:
        a, b = valeur_a(pm, t), valeur_a(serie_book, t)
        if a is not None and b is not None:
            out.append((t, a, b))
        t += datetime.timedelta(minutes=pas_min)
    return out
