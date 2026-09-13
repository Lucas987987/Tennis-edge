#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""canal_clv_diagnostic.py — LECTURE SEULE. Ne modifie aucun fichier.

Le registre `canal_clv_detail.csv` a été gelé avec la cascade de sources
d'avant le 13/09/2026, qui retenait le premier résultat trouvé plutôt que le
point pré-match le plus tardif. Une fenêtre `live` tronquée pouvait donc
écraser une courbe complète, et la ligne était gelée définitivement sur une
valeur fausse.

Ce script rejoue chaque ligne du registre avec la cascade corrigée et dit,
pour chacune, si la valeur gelée est confirmée ou tronquée. Il n'écrit rien :
la décision de réécrire ou non un historique publié est éditoriale, pas
technique.

Env : LEDGER, CURVES, EPS (tolérance en cote, défaut 0.005)
"""
import collections
import csv
import datetime
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov            # noqa: E402
import json                          # noqa: E402

LEDGER = os.environ.get('LEDGER', 'canal_clv_detail.csv')
CURVES = [c.strip() for c in os.environ.get(
    'CURVES', 'book_curves_live.jsonl,book_curves.jsonl').split(',') if c.strip()]
EPS = float(os.environ.get('EPS', '0.005'))


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(
            str(s).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def load_closes():
    """Dernier point pré-match, source la plus TARDIVE (cascade corrigée)."""
    closes = {}
    for src in CURVES:
        try:
            lignes = ov.open_curves(src, verbose=False)
        except Exception:
            continue
        for line in lignes:
            line = line.strip() if isinstance(line, str) else line
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            ct = _dt(r.get('commence_time'))
            if not ct:
                continue
            home = r.get('home_team') or r.get('home') or ''
            away = r.get('away_team') or r.get('away') or ''
            for key, name in (('home_curve', home), ('away_curve', away)):
                pts = [(_dt(p[0]), p[1]) for p in (r.get(key) or [])
                       if _dt(p[0]) and p[1] and p[1] > 1]
                pts = sorted(p for p in pts if p[0] < ct)
                if pts and name:
                    k = (r.get('uid'), r.get('book'), name)
                    if k not in closes or pts[-1][0] > closes[k][1]:
                        closes[k] = (pts[-1][1], pts[-1][0], len(pts))
    return closes


def main():
    if not os.path.exists(LEDGER):
        print(f"{LEDGER} introuvable"); return 1
    rows = list(csv.DictReader(open(LEDGER, encoding='utf-8-sig')))
    closes = load_closes()
    print(f"registre : {len(rows)} lignes · courbes indexées : {len(closes)}\n")

    cat = collections.Counter()
    ecarts, clv_gel, clv_vrai = [], [], []
    detail_tronques = []
    for r in rows:
        try:
            prix = float(r['prix_signale']); cl_gel = float(r['cloture'])
        except Exception:
            cat['illisible'] += 1
            continue
        got = closes.get((r['uid'], r['book'], r['joueur']))
        if not got:
            cat['courbe introuvable'] += 1
            continue
        cl_vrai, _, n_pts = got
        gel0 = abs(prix - cl_gel) < 1e-9
        if abs(cl_vrai - cl_gel) <= EPS:
            cat['prix figé confirmé' if gel0 else 'valeur confirmée'] += 1
        else:
            cat['TRONQUÉE' if gel0 else 'tronquée (non nulle)'] += 1
            g = (prix / cl_gel - 1) * 100
            v = (prix / cl_vrai - 1) * 100
            ecarts.append(v - g)
            detail_tronques.append((r['date'], r['joueur'], r['book'],
                                    prix, cl_gel, cl_vrai, g, v, n_pts))
        clv_gel.append((prix / cl_gel - 1) * 100)
        clv_vrai.append((prix / cl_vrai - 1) * 100)

    print("RÉPARTITION")
    for k, v in cat.most_common():
        print(f"  {v:4d}  {k}")

    if ecarts:
        print(f"\nIMPACT sur les {len(ecarts)} lignes tronquées")
        print(f"  écart médian (vrai - gelé) : {st.median(ecarts):+.2f} pts de CLV")
        print(f"  écart max                  : {max(ecarts):+.2f} pts")
    if clv_gel:
        pg = 100 * sum(1 for x in clv_gel if x > 0) / len(clv_gel)
        pv = 100 * sum(1 for x in clv_vrai if x > 0) / len(clv_vrai)
        print(f"\nTAUX DE REFERMETURE sur les {len(clv_gel)} lignes recalculables")
        print(f"  tel que publié : {pg:.1f}%")
        print(f"  recalculé      : {pv:.1f}%")
        print(f"  médiane CLV    : {st.median(clv_gel):+.2f}% -> "
              f"{st.median(clv_vrai):+.2f}%")

    if detail_tronques:
        print(f"\nLIGNES TRONQUÉES (20 premières)")
        print(f"  {'date':16} {'book':12} {'signalé':>8} {'gelé':>8} "
              f"{'vrai':>8} {'CLV gelé':>9} {'CLV vrai':>9}  joueur")
        for d in sorted(detail_tronques)[:20]:
            print(f"  {d[0]:16} {d[2]:12} {d[3]:8.2f} {d[4]:8.2f} "
                  f"{d[5]:8.2f} {d[6]:+8.1f}% {d[7]:+8.1f}%  {d[1]}")

    print("\nAUCUN FICHIER MODIFIÉ.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
