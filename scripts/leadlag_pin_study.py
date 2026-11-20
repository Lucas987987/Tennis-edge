#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""leadlag_pin_study.py — Les marchés de prédiction précèdent-ils Pinnacle ?

PISTE GELÉE LE 2026-08-25 — le protocole est figé AVANT que les données
suffisent (les collecteurs ont quelques jours). Protocole :
  - matchs communs ticks Polymarket <-> courbe Pinnacle (jointure noms+jour) ;
  - séries à la minute : proba implicite Pinnacle (1/oh dévigué proportionnel)
    et bid Polymarket du même côté ; différences première minute ;
  - corrélation croisée aux décalages -30..+30 min ; le décalage qui maximise
    |corr| par match ; verdict = médiane des décalages sur n>=30 matchs, IC
    par bootstrap simple.
  - Décalage NÉGATIF médian = Polymarket précède = signal en amont du steam.
Tant que n<30 : le script imprime l'avancement et se tait sur le fond.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datetime
import glob
import gzip
import json
import statistics as st
import pistes_common as pc
from decay_study import cle_match

MAX_FICHIERS = 12          # budget de lecture des ticks, du plus récent
LAGS = range(-30, 31, 3)


def _ouvrir(p):
    return gzip.open(p, 'rt', encoding='utf-8', errors='replace') \
        if p.endswith('.gz') else open(p, encoding='utf-8', errors='replace')


def series_pm():
    """{local_uid: [(ts, bid)]} depuis les partitions pm_ticks récentes."""
    out = {}
    fichiers = sorted(glob.glob('parts/pm_ticks_*.jsonl')
                      + glob.glob('parts/pm_ticks_*.jsonl.gz'))[-MAX_FICHIERS:]
    for f in fichiers:
        with _ouvrir(f) as fh:
            for l in fh:
                try:
                    t = json.loads(l)
                    if t.get('bid') and t.get('local_uid'):
                        out.setdefault(t['local_uid'], []).append(
                            (pc.ts_norm(t['ts']), float(t['bid'])))
                except (ValueError, KeyError):
                    continue
    return out


def grille_minute(points, debut, fin):
    """Échantillonne une série (ts, val) à la minute sur [debut, fin]."""
    points = sorted(points)
    out, i, cur = [], 0, None
    t = debut
    while t <= fin:
        ts = t.isoformat()[:19]
        while i < len(points) and points[i][0] <= ts:
            cur = points[i][1]
            i += 1
        out.append(cur)
        t += datetime.timedelta(minutes=1)
    return out


def correlation(a, b):
    xs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(xs) < 20:
        return None
    ax = [x for x, _ in xs]
    bx = [y for _, y in xs]
    ma, mb = st.mean(ax), st.mean(bx)
    num = sum((x - ma) * (y - mb) for x, y in xs)
    da = sum((x - ma) ** 2 for x in ax) ** 0.5
    db = sum((y - mb) ** 2 for y in bx) ** 0.5
    return num / (da * db) if da and db else None


def main():
    pc.entete('PISTE 2 — LEAD-LAG POLYMARKET vs PINNACLE')
    pm = series_pm()
    print(f'  {len(pm)} marchés Polymarket avec ticks (fenêtre récente)')
    pin = pc.courbes_par_uid('pinnacle')
    pin_par_cle = {}
    for r in pin.values():
        pin_par_cle[cle_match(r.get('home'), r.get('away'),
                              r.get('commence_time'))] = r
    lags_gagnants = []
    for local_uid, ticks in pm.items():
        # local_uid ~ slug : jointure par jetons de noms sur toutes les clés pin
        jetons = set(local_uid.lower().replace('-', ' ').replace('_', ' ').split())
        r = None
        for cle, cand in pin_par_cle.items():
            noms = set()
            for n in cle[0]:
                noms |= set(n.split())
            if len(noms & jetons) >= 3 and cle[1] in local_uid:
                r = cand
                break
            if len(noms & jetons) >= 4:
                r = cand
                break
        if not r:
            continue
        ct = pc.ts_norm(r.get('commence_time'))
        try:
            fin = datetime.datetime.fromisoformat(ct)
        except ValueError:
            continue
        debut = fin - datetime.timedelta(hours=6)
        s_pm = grille_minute(ticks, debut, fin)
        s_pin_pts = []
        for pt in r.get('home_curve') or []:
            try:
                oh = float(pt[1])
                if oh > 1:
                    s_pin_pts.append((pc.ts_norm(pt[0]), 1 / oh))
            except (TypeError, ValueError):
                continue
        s_pin = grille_minute(s_pin_pts, debut, fin)
        d_pm = [None if (a is None or b is None) else b - a
                for a, b in zip(s_pm, s_pm[1:])]
        d_pin = [None if (a is None or b is None) else b - a
                 for a, b in zip(s_pin, s_pin[1:])]
        best = None
        for lag in LAGS:
            if lag >= 0:
                c = correlation(d_pin[lag:], d_pm[:len(d_pm) - lag or None])
            else:
                c = correlation(d_pin[:lag], d_pm[-lag:])
            if c is not None and (best is None or abs(c) > abs(best[1])):
                best = (lag, c)
        if best and abs(best[1]) > 0.15:
            lags_gagnants.append(best[0])
    n = len(lags_gagnants)
    print(f'  {n} matchs appariés avec corrélation exploitable (|r|>0,15)')
    if n < 30:
        print('  TROP TÔT : verdict à n>=30 matchs — le protocole est gelé,')
        print('  la donnée s\'accumule toute seule. Relance hebdomadaire.')
        return
    med = st.median(lags_gagnants)
    print(f'  décalage médian du pic de corrélation : {med:+.0f} min')
    print('  (négatif = Polymarket PRÉCÈDE Pinnacle = signal en amont du steam)')


if __name__ == '__main__':
    main()
