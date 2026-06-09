#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
soft_open_detector.py — Le SEUL angle qui respire encore : l'ouverture molle.

Sur chaque fixture où l'on a un book MOU (unibet) ET un book SHARP (bwin), on :
  1. calcule une OUVERTURE ROBUSTE pour le book mou (médiane des premiers ticks
     dans une fenêtre, JAMAIS un tick isolé — c'est ce qui tuait le signal en
     artefact) ;
  2. dévigue le book sharp (ouverture ET clôture) pour avoir une proba ÉQUITABLE ;
  3. flague un côté quand l'ouverture molle bat le fair sharp d'ouverture
     (mispricing connu à la décision) ;
  4. mesure la CLV RÉALISÉE de ce côté vs la clôture sharp équitable (le juge de paix).

Sortie :
  - soft_openings.jsonl : un enregistrement par flag (pour accumuler en forward) ;
  - résumé agrégé avec GARDE-FOU n>=30 : tant qu'on n'a pas 30 flags, AUCUNE
    conclusion. Moyenne + médiane + moyenne tronquée (les outliers gonflent la moyenne).

Ne mise rien. Ne touche aucun fichier en lecture seule. Lit book_curves.jsonl.

Config (env) :
  BOOK_CURVES   (def book_curves.jsonl)   SOFT_BOOK (def unibet)   SHARP_BOOK (def bwin)
  OPEN_WINDOW_MIN (def 90)  OPEN_MIN_POINTS (def 3)  OUT (def soft_openings.jsonl)
"""
import json, os, math, statistics as st
from datetime import datetime, timedelta

BOOK_CURVES = os.environ.get('BOOK_CURVES', 'book_curves.jsonl')
SOFT_BOOK   = os.environ.get('SOFT_BOOK', 'unibet')
SHARP_BOOK  = os.environ.get('SHARP_BOOK', 'bwin')
OPEN_WINDOW_MIN = int(os.environ.get('OPEN_WINDOW_MIN', '90'))
OPEN_MIN_POINTS = int(os.environ.get('OPEN_MIN_POINTS', '3'))
OUT = os.environ.get('OUT', 'soft_openings.jsonl')
N_MIN = 30  # seuil de conclusion (discipline)


def parse(t):
    t = str(t).replace('Z', '').replace('.000', '')
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(t[:26], fmt)
        except ValueError:
            pass
    return None


def prematch(curve, commence):
    pts = sorted((parse(t), p) for t, p in curve if p and parse(t))
    return [x for x in pts if (commence is None or x[0] <= commence)]


def robust_open(pts):
    """Ouverture robuste = médiane des points dans les OPEN_WINDOW_MIN premières
    minutes ; exige >= OPEN_MIN_POINTS, sinon None (on ne fait pas confiance à un
    tick isolé). Renvoie (prix, lead_h, n_pts_fenetre, instabilite_pct)."""
    if len(pts) < OPEN_MIN_POINTS:
        return None
    t0 = pts[0][0]
    win = [p for t, p in pts if t <= t0 + timedelta(minutes=OPEN_WINDOW_MIN)]
    if len(win) < OPEN_MIN_POINTS:
        return None
    med = st.median(win)
    instab = (max(win) - min(win)) / med * 100 if med else 0
    return med, instab


def devig(oh, oa):
    ph, pa = 1 / oh, 1 / oa
    s = ph + pa
    return ph / s, pa / s          # probas équitables (home, away)


def load_fixtures():
    fix = {}
    for line in open(BOOK_CURVES, encoding='utf-8'):
        if not line.strip():
            continue
        x = json.loads(line)
        com = parse(x.get('commence_time'))
        ph = prematch(x.get('home_curve') or [], com)
        pa = prematch(x.get('away_curve') or [], com)
        if len(ph) < 2 or len(pa) < 2:
            continue
        fix.setdefault(x['fixture_id'], {})[x.get('book')] = {
            'home_pts': ph, 'away_pts': pa, 'commence': com,
            'home': x.get('home'), 'away': x.get('away'),
            'tournament': x.get('tournament'), 'uid': x.get('uid'),
        }
    return fix


def main():
    if not os.path.exists(BOOK_CURVES):
        print(f"❌ {BOOK_CURVES} introuvable"); return
    fix = load_fixtures()
    pairs = [f for f in fix if SOFT_BOOK in fix[f] and SHARP_BOOK in fix[f]]
    print(f"fixtures avec {SOFT_BOOK}+{SHARP_BOOK} : {len(pairs)}")

    flags = []
    for f in pairs:
        soft, sharp = fix[f][SOFT_BOOK], fix[f][SHARP_BOOK]
        so_h = robust_open(soft['home_pts']); so_a = robust_open(soft['away_pts'])
        sp_oh = robust_open(sharp['home_pts']); sp_oa = robust_open(sharp['away_pts'])
        if not all((so_h, so_a, sp_oh, sp_oa)):
            continue
        # fair sharp à l'OUVERTURE (décision) et à la CLÔTURE (vérité)
        fho, fao = devig(sp_oh[0], sp_oa[0])
        fhc, fac = devig(sharp['home_pts'][-1][1], sharp['away_pts'][-1][1])
        lead_h = (soft['commence'] - soft['home_pts'][0][0]).total_seconds() / 3600 \
            if soft['commence'] else None
        for side, soft_open, instab, fair_open, fair_close in (
                ('home', so_h[0], so_h[1], fho, fhc),
                ('away', so_a[0], so_a[1], fao, fac)):
            edge_open = soft_open * fair_open - 1          # vs fair sharp ouverture
            if edge_open <= 0:
                continue                                    # pas plus généreux que le fair
            clv = soft_open * fair_close - 1                # CLV réalisée vs clôture équitable
            flags.append({
                'uid': soft['uid'], 'fixture_id': f, 'tournament': soft['tournament'],
                'player': soft['home'] if side == 'home' else soft['away'],
                'opponent': soft['away'] if side == 'home' else soft['home'],
                'side': side, 'soft_open_odds': round(soft_open, 3),
                'fair_open_odds': round(1 / fair_open, 3),
                'fair_close_odds': round(1 / fair_close, 3),
                'edge_open_pct': round(edge_open * 100, 2),
                'clv_pct': round(clv * 100, 2),
                'lead_h': round(lead_h, 1) if lead_h is not None else None,
                'open_instab_pct': round(instab, 1),
            })

    with open(OUT, 'w', encoding='utf-8') as fo:
        for r in flags:
            fo.write(json.dumps(r, ensure_ascii=False) + '\n')

    # ── Résumé ──
    def stats(vals):
        n = len(vals)
        if n == 0:
            return None
        m = st.mean(vals); med = st.median(vals)
        se = st.pstdev(vals) / math.sqrt(n) if n > 1 else 0
        pos = sum(1 for v in vals if v > 0) / n * 100
        trimmed = sorted(vals)[1:-1] if n >= 5 else vals      # tronque 1 de chaque bout
        tm = st.mean(trimmed) if trimmed else m
        return n, m, med, tm, pos, (m / se if se else 0)

    out = [f"## Détecteur d'ouverture molle ({SOFT_BOOK} vs {SHARP_BOOK})", ""]
    clv = [r['clv_pct'] for r in flags]
    out.append(f"Flags : {len(flags)} (sur {len(pairs)} fixtures)")
    s = stats(clv)
    if s:
        n, m, med, tm, pos, t = s
        out += [
            f"CLV réalisée vs clôture équitable :",
            f"  n={n}  moy={m:+.2f}%  **méd={med:+.2f}%**  moy_tronquée={tm:+.2f}%  %>0={pos:.0f}%  t≈{t:+.2f}",
            "",
        ]
        # par bande de seuil d'ouverture
        out.append("Par seuil d'edge à l'ouverture :")
        for lo, hi in ((0, 3), (3, 5), (5, 10), (10, 999)):
            sub = [r['clv_pct'] for r in flags if lo <= r['edge_open_pct'] < hi]
            if sub:
                out.append(f"  edge_open {lo}-{hi}% : n={len(sub):2d}  CLV méd={st.median(sub):+.2f}%")
        out.append("")
        if n < N_MIN:
            out.append(f"⚠️ n={n} < {N_MIN} : AUCUNE conclusion. On accumule. Ne rien parier.")
        else:
            verdict = "signal CLV POSITIF à creuser" if med > 0 and pos > 55 else "pas d'edge net"
            out.append(f"n>={N_MIN} atteint -> médiane {med:+.2f}%, {pos:.0f}% positifs : {verdict}.")
        out.append("\nRappel : médiane >> moyenne ici car quelques outliers gonflent la moyenne. "
                   "Et même réel, l'exécution reste un mur (limites d'ouverture, .fr régulé).")
    else:
        out.append("Aucun flag — rien à conclure.")

    report = "\n".join(out)
    print("\n" + report)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as g:
            g.write(report + "\n")
    print(f"\n✅ {OUT} : {len(flags)} flags écrits")


if __name__ == '__main__':
    main()
