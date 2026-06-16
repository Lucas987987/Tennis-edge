#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validation_report.py — Tableau de validation FORWARD du steam-following.

Lit les journaux paper_trades_*.jsonl et dit, avec des INTERVALLES DE CONFIANCE,
si l'edge est prouve ou pas (et combien de paris il reste a accumuler). C'est le
juge objectif : tant que les bornes basses n'excluent pas 0 (ROI) ou 50% (%CLV+),
l'edge n'est PAS confirme, quel que soit le point estime.

Pour chaque surface (match/set1/set2) et par book :
  - CLV vs cloture : mediane, moyenne, %positif + IC95 (Wilson)
  - ROI reel : moyenne/mise + IC95 | taux de reussite + IC95 (Wilson)
  - verdict CLV / ROI + taille d'echantillon estimee pour la significativite
  - tendance (cumul) premiers vs derniers paris

Env : JOURNALS (glob, def 'paper_trades_*.jsonl'). Aucune dependance externe.
"""
import os, glob, json, math, statistics as st

JOURNALS = os.environ.get('JOURNALS', 'paper_trades_*.jsonl')
Z = 1.96  # 95%


def wilson(k, n):
    """IC95 de Wilson pour une proportion (k succes sur n)."""
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return (p, max(0, c - h), min(1, c + h))


def mean_ci(xs):
    """IC95 de la moyenne (approx normale)."""
    n = len(xs)
    if n < 2:
        return (xs[0] if xs else 0.0, None, None, 0.0)
    m = st.mean(xs); s = st.pstdev(xs)
    half = Z * s / math.sqrt(n)
    return (m, m - half, m + half, s)


def n_needed(mean, s):
    """Taille d'echantillon estimee pour que l'IC95 de la moyenne exclue 0."""
    if not mean or s == 0:
        return None
    return int(math.ceil((Z * s / abs(mean)) ** 2))


def report_group(name, trades):
    settled = [t for t in trades if t.get('status') == 'SETTLED']
    opens = [t for t in trades if t.get('status') == 'OPEN']
    print(f"\n{'='*60}\n{name}  —  {len(settled)} denoues | {len(opens)} ouverts")
    if not settled:
        print("  (pas encore de pari denoue — rien a juger)"); return

    clv = [t['clv_book'] for t in settled if 'clv_book' in t]
    pnl = [t['pnl'] for t in settled if 'pnl' in t]
    won = [1 if t.get('won') else 0 for t in settled if 'won' in t]

    # CLV
    if clv:
        kpos = sum(1 for x in clv if x > 0)
        p, lo, hi = wilson(kpos, len(clv))
        verdict = ("✅ CONFIRME (>50%)" if lo > 0.50 else
                   "⚠ tendance +" if p > 0.50 else "❌ non positif")
        print(f"  CLV vs cloture : mediane {st.median(clv):+.1f}% | moyenne {st.mean(clv):+.1f}% "
              f"| %positif {p*100:.0f}% (IC95 {lo*100:.0f}-{hi*100:.0f}%)  -> {verdict}")
    # ROI
    if pnl:
        m, lo, hi, s = mean_ci(pnl)
        roi = m * 100
        if lo is None:
            print(f"  ROI reel       : {roi:+.1f}%/mise (n trop faible pour IC)")
        else:
            sig = "✅ PROFIT CONFIRME (IC>0)" if lo > 0 else \
                  ("⚠ tendance + (IC inclut 0)" if m > 0 else "❌ non profitable")
            print(f"  ROI reel       : {roi:+.1f}%/mise (IC95 {lo*100:+.1f}..{hi*100:+.1f}%)  -> {sig}")
            if lo <= 0 < m:
                nn = n_needed(m, s)
                if nn:
                    print(f"                   ~{nn} paris denoues estimes pour confirmer (actuel {len(pnl)})")
    # win rate
    if won:
        p, lo, hi = wilson(sum(won), len(won))
        print(f"  Reussite       : {p*100:.0f}% (IC95 {lo*100:.0f}-{hi*100:.0f}%, n={len(won)})")
    # par book
    books = sorted(set(t['book'] for t in settled if t.get('book')))
    if len(books) > 1:
        print("  -- par book --")
        for b in books:
            sub = [t for t in settled if t.get('book') == b]
            c = [t['clv_book'] for t in sub if 'clv_book' in t]
            pl = [t['pnl'] for t in sub if 'pnl' in t]
            cm = f"{st.median(c):+.1f}%" if c else "n/a"
            rm = f"{100*st.mean(pl):+.1f}%" if pl else "n/a"
            print(f"     {b:10} n={len(sub):3d} | CLV med {cm} | ROI {rm}")
    # tendance (cumul ROI : 1re moitie vs 2e)
    seq = [t['pnl'] for t in settled if 'pnl' in t]
    if len(seq) >= 6:
        half = len(seq) // 2
        r1, r2 = 100 * st.mean(seq[:half]), 100 * st.mean(seq[half:])
        fleche = "↗ s'ameliore" if r2 > r1 else "↘ se degrade" if r2 < r1 else "→ stable"
        print(f"  Tendance ROI   : 1re moitie {r1:+.1f}% -> 2e moitie {r2:+.1f}%  {fleche}")


def main():
    files = sorted(glob.glob(JOURNALS))
    if not files:
        print(f"Aucun journal trouve ({JOURNALS}). Le pipeline n'a pas encore ouvert/denoue de pari.")
        return
    print("TABLEAU DE VALIDATION FORWARD — steam-following")
    print("Regle : un edge n'est CONFIRME que si la borne basse de l'IC95 exclut 0 (ROI) / 50% (CLV+).")
    for f in files:
        name = os.path.basename(f).replace('paper_trades_', 'surface ').replace('.jsonl', '')
        trades = []
        for line in open(f, encoding='utf-8'):
            line = line.strip()
            if line:
                try: trades.append(json.loads(line))
                except Exception: pass
        report_group(name, trades)
    print(f"\n{'='*60}\nRappel : CLV+ = prix battu ; le ROI net subit encore marge + gubbing.")


if __name__ == '__main__':
    main()
