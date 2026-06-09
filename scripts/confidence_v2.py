#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
confidence_v2.py — Score de confiance refondé : probabilité CALIBRÉE (Venn-Abers)
+ intervalle d'incertitude, validé contre la clôture sharp dévigée.

Pipeline :
  1. Données = (probA_modele, resultat) des lignes résolues du backtest
     (probA_modele = proba brute du modèle pour le favori ; resultat 1/0).
  2. Calibration Venn-Abers (IVAP) = deux régressions isotoniques (PAV maison,
     aucune dépendance). Sortie : proba calibrée p = p1/(1-p0+p1) et intervalle
     [p0, p1] dont la LARGEUR est le score de confiance (étroit = sûr).
  3. Validation WALK-FORWARD : pour chaque match, on calibre sur le passé seul,
     puis Brier / log-loss / ECE comparés à la clôture Pinnacle dévigée (la vérité).
  4. Export confidence_calib.json (grille score -> p0,p1) que l'OUTIL lit pour
     afficher la confiance à chaque match, SANS recalculer.

Honnêteté : ce score dit à quel point CROIRE la proba, pas s'il y a de la valeur.
"""
import csv, json, os, math, statistics as st

BACKTEST = os.environ.get('BACKTEST_FILE', 'backtest_tennis.csv')
OUT_JSON = os.environ.get('OUT', 'confidence_calib.json')
MIN_CAL = int(os.environ.get('MIN_CAL', '20'))     # taille mini de calibration en WF
GRID = [i / 200 for i in range(201)]               # grille 0..1 pas 0.005


# ── PAV : régression isotonique non-décroissante (pur Python) ──
def isotonic(y):
    val, wt, cnt = [], [], []
    for v in y:
        w, c = 1.0, 1
        while val and val[-1] > v:
            pv, pw, pc = val.pop(), wt.pop(), cnt.pop()
            v = (v * w + pv * pw) / (w + pw); w += pw; c += pc
        val.append(v); wt.append(w); cnt.append(c)
    out = []
    for v, c in zip(val, cnt):
        out += [v] * c
    return out


def ivap_point(scores, labels, s):
    """Inductive Venn-Abers : renvoie (p0, p1) pour un score test s."""
    p = {}
    for yl in (0, 1):
        items = [(sc, lb, 0) for sc, lb in zip(scores, labels)] + [(s, yl, 1)]
        items.sort(key=lambda t: (t[0], t[2]))
        fit = isotonic([it[1] for it in items])
        ti = next(i for i, it in enumerate(items) if it[2] == 1)
        p[yl] = fit[ti]
    return p[0], p[1]


def va_point(p0, p1):
    return p1 / (1 - p0 + p1) if (1 - p0 + p1) > 0 else (p0 + p1) / 2


def f(x):
    try:
        x = str(x).strip(); return float(x) if x not in ('', 'nan', 'None') else None
    except Exception:
        return None


def devig(oa, ob):
    if not oa or not ob:
        return None
    pa, pb = 1 / oa, 1 / ob
    return pa / (pa + pb)


def brier(preds, ys):
    return st.mean((p - y) ** 2 for p, y in zip(preds, ys))


def logloss(preds, ys):
    e = 1e-6
    return -st.mean(y * math.log(min(max(p, e), 1 - e)) + (1 - y) * math.log(min(max(1 - p, e), 1 - e))
                    for p, y in zip(preds, ys))


def ece(preds, ys, bins=10):
    N = len(preds); tot = 0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, p in enumerate(preds) if (lo <= p < hi or (b == bins - 1 and p == 1))]
        if not idx:
            continue
        conf = st.mean(preds[i] for i in idx); acc = st.mean(ys[i] for i in idx)
        tot += len(idx) / N * abs(conf - acc)
    return tot


def main():
    rows = list(csv.DictReader(open(BACKTEST, encoding='utf-8', errors='replace'), delimiter=';'))
    data = []
    for r in rows:
        res = (r.get('resultat') or '').strip()
        pa = f(r.get('probA_modele'))
        if res in ('0', '1') and pa is not None:
            data.append({'date': r.get('date_match', ''), 'raw': max(0.0, min(1.0, pa)),
                         'y': int(res == '1'), 'close': devig(f(r.get('psA')), f(r.get('psB')))})
    data.sort(key=lambda d: d['date'])
    n = len(data)
    print(f"matchs résolus avec proba modèle : {n}")
    if n < MIN_CAL + 5:
        print(f"⚠️ trop peu pour calibrer ({n}). On exporte quand même la grille sur tout.")

    # ── Walk-forward : calibrer sur le passé, prédire le présent ──
    raw_p, cal_p, clo_p, ys = [], [], [], []
    for i in range(n):
        if i < MIN_CAL:
            continue
        cal = data[:i]
        p0, p1 = ivap_point([d['raw'] for d in cal], [d['y'] for d in cal], data[i]['raw'])
        cal_p.append(va_point(p0, p1)); raw_p.append(data[i]['raw']); ys.append(data[i]['y'])
        clo_p.append(data[i]['close'] if data[i]['close'] is not None else data[i]['raw'])

    out = ["## Score de confiance v2 — Venn-Abers (walk-forward)", ""]
    if cal_p:
        m = len(cal_p)
        out += [
            f"validés en walk-forward : {m}",
            "",
            f"{'métrique':10s} {'modèle brut':>12s} {'calibré':>10s} {'clôture sharp':>14s}",
            f"{'Brier':10s} {brier(raw_p,ys):>12.4f} {brier(cal_p,ys):>10.4f} {brier(clo_p,ys):>14.4f}",
            f"{'log-loss':10s} {logloss(raw_p,ys):>12.4f} {logloss(cal_p,ys):>10.4f} {logloss(clo_p,ys):>14.4f}",
            f"{'ECE':10s} {ece(raw_p,ys):>12.4f} {ece(cal_p,ys):>10.4f} {ece(clo_p,ys):>14.4f}",
            "",
            "Lecture : 'calibré' doit baisser l'ECE et le Brier vs 'brut', et se "
            "rapprocher de 'clôture sharp' (la vérité) sans la dépasser.",
        ]
    else:
        out.append("Pas assez de données pour une validation walk-forward.")

    # ── Calibrateur FINAL sur toutes les données -> grille exportée ──
    sc = [d['raw'] for d in data]; lb = [d['y'] for d in data]
    grid = []
    for s in GRID:
        p0, p1 = ivap_point(sc, lb, s)
        grid.append({'s': round(s, 3), 'p0': round(p0, 4), 'p1': round(p1, 4),
                     'p': round(va_point(p0, p1), 4)})
    payload = {
        'method': 'venn-abers-ivap', 'n_calibration': n,
        'fitted_on': data[-1]['date'] if data else None,
        'tiers': {'haute': 0.06, 'moyenne': 0.12},   # largeur intervalle: <0.06 haute, <0.12 moyenne, sinon faible
        'grid': grid,
    }
    json.dump(payload, open(OUT_JSON, 'w', encoding='utf-8'), ensure_ascii=False)
    out += ["", f"✅ {OUT_JSON} écrit ({len(grid)} points de grille, n_calib={n})."]

    report = "\n".join(out)
    print("\n" + report)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8').write(report + "\n")


if __name__ == '__main__':
    main()
