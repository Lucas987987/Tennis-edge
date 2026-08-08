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



# ── Suivi de l'hypothèse OUT-OF-SAMPLE "calibration 2,20-3,50" ────────────────
# Figée le 03/08/2026 après analyse : sur juin-août 2026 (n=925 matchs), les
# côtés clôturant 2,20-3,50 (Pinnacle, devig Shin) gagnaient +5,8 pts de plus
# que leur proba (z≈+2,7), miroir -5,1 sur les favoris 1,20-1,80. Hypothèses
# concurrentes : biais réel vs été à surprises vs artefact de fouille. Cette
# section suit le résidu mois par mois SUR LES NOUVELLES DONNÉES UNIQUEMENT :
# s'il retombe à ~0, c'était du bruit ; s'il persiste, on en reparle.
FREEZE_DATE = '2026-08-04'
FREEZE_DATE_MARGIN = '2026-08-09'   # hypothèse 'variation de marge' gelée le 08/08   # les matchs AVANT cette date ont servi à formuler l'hypothèse

def _shin_ph(oh, oa):
    ih, ia = 1/oh, 1/oa; ssum = ih + ia
    if ssum <= 1: return ih/ssum
    z = 0.02
    for _ in range(50):
        ph = (math.sqrt(z*z + 4*(1-z)*ih*ih/ssum) - z) / (2*(1-z))
        pa = (math.sqrt(z*z + 4*(1-z)*ia*ia/ssum) - z) / (2*(1-z))
        t = ph + pa
        if abs(t-1) < 1e-9: break
        z = min(max(z + (t-1), 0.0), 0.3)
    return ph/(ph+pa)

def calibration_watch():
    import datetime as _dtm
    def _d(x):
        try: return _dtm.datetime.fromisoformat(str(x).replace('Z','').replace('+00:00',''))
        except Exception: return None
    try:
        sr = json.load(open('set_results.json', encoding='utf-8'))
    except Exception:
        return
    sides = []
    seen = set()
    for src in ('book_curves.jsonl', 'book_curves_live.jsonl'):
        if not os.path.exists(src): continue
        for line in open(src, encoding='utf-8'):
            line = line.strip()
            if not line: continue
            try: c = json.loads(line)
            except Exception: continue
            if c.get('book') != 'pinnacle' or c.get('uid') in seen: continue
            ct = _d(c.get('commence_time'))
            if not ct or ct < _dtm.datetime.fromisoformat(FREEZE_DATE): continue   # OUT-OF-SAMPLE only
            res = (sr.get(c['uid']) or {}).get('match')
            if res not in ('home', 'away'): continue
            def _pre(seq):
                pts = [(_d(p[0]), p[1]) for p in (seq or []) if _d(p[0]) and p[1]]
                return sorted(x for x in pts if x[0] < ct)
            h, a = _pre(c.get('home_curve')), _pre(c.get('away_curve'))
            if len(h) < 3 or len(a) < 3: continue
            oh, oa = h[-1][1], a[-1][1]
            if min(oh, oa) <= 1: continue
            seen.add(c['uid'])
            ph = _shin_ph(oh, oa); hw = (res == 'home')
            sides.append((oh, ph, hw)); sides.append((oa, 1-ph, not hw))
    band = [(o, p, w) for o, p, w in sides if 2.20 <= o < 3.50]
    print(f"\n{'='*60}\nSUIVI HYPOTHÈSE — calibration cotes 2,20-3,50 (out-of-sample depuis {FREEZE_DATE})")
    if len(band) < 30:
        print(f"  n={len(band)} côtés — trop tôt pour juger (seuil 30). Référence gelée : +5,8 pts.")
        return
    wr = sum(1 for *_ , w in band if w) / len(band)
    ex = st.mean(p for _, p, _ in band)
    se = (wr*(1-wr)/len(band))**0.5
    verdict = "PERSISTE (à surveiller)" if (wr-ex) - 1.96*se > 0 else ("retombé -> bruit probable" if abs(wr-ex) < se else "indéterminé")
    print(f"  n={len(band)} | réel {100*wr:.1f}% vs attendu Shin {100*ex:.1f}% | résidu {100*(wr-ex):+.1f} pts (±{196*se:.0f}) -> {verdict}")
    print(f"  (référence in-sample juin-août: +5,8 pts ; si le résidu retombe ~0, c'était un été à surprises)")

def hour_watch():
    """Suivi OUT-OF-SAMPLE de l'hypothèse 'heure du match'. Constat in-sample
    (07/08/2026, n=729, sur tous les matchs jusqu'à FREEZE_DATE) : le côté
    steamé (celui vers qui Pinnacle se raccourcit) gagne plus souvent quand le
    match est tard dans la journée (Spearman heure~résultat = +0,204, le seul
    facteur testé -ampleur/durée/jour/tournoi- à dépasser le seuil de
    significativité). Hypothèse à un seul test parmi plusieurs -> à confirmer
    strictement out-of-sample avant d'y accorder du crédit (cf. calibration
    2,20-3,50 : même précaution)."""
    import datetime as _dtm
    def _d(x):
        try: return _dtm.datetime.fromisoformat(str(x).replace('Z','').replace('+00:00',''))
        except Exception: return None
    try:
        sr = json.load(open('set_results.json', encoding='utf-8'))
    except Exception:
        return
    rows, seen = [], set()
    for src in ('book_curves.jsonl', 'book_curves_live.jsonl'):
        if not os.path.exists(src): continue
        for line in open(src, encoding='utf-8'):
            line = line.strip()
            if not line: continue
            try: c = json.loads(line)
            except Exception: continue
            if c.get('book') != 'pinnacle' or c.get('uid') in seen: continue
            ct = _d(c.get('commence_time'))
            if not ct or ct < _dtm.datetime.fromisoformat(FREEZE_DATE): continue   # OUT-OF-SAMPLE only
            res = (sr.get(c['uid']) or {}).get('match')
            if res not in ('home', 'away'): continue
            def _pre(seq):
                pts = [(_d(p[0]), p[1]) for p in (seq or []) if _d(p[0]) and p[1]]
                return sorted(x for x in pts if x[0] < ct)
            h, a = _pre(c.get('home_curve')), _pre(c.get('away_curve'))
            if len(h) < 3 or len(a) < 3: continue
            oh0, oa0 = h[0][1], a[0][1]
            oh1, oa1 = h[-1][1], a[-1][1]
            if min(oh0, oa0, oh1, oa1) <= 1: continue
            seen.add(c['uid'])
            p0, p1 = _shin_ph(oh0, oa0), _shin_ph(oh1, oa1)
            steam_h = p1 > p0
            won = (res == 'home') if steam_h else (res == 'away')
            pfair = p1 if steam_h else 1 - p1
            rows.append((ct.hour, won, pfair))
    print(f"\n{'='*60}\nSUIVI HYPOTHÈSE — heure du match (out-of-sample depuis {FREEZE_DATE})")
    if len(rows) < 30:
        print(f"  n={len(rows)} matchs — trop tôt pour juger (seuil 30). "
              f"Référence in-sample : rho=+0.20 (heure tardive -> steamé gagne plus).")
        return
    late = [(w, p) for h, w, p in rows if h >= 18]
    early = [(w, p) for h, w, p in rows if h < 18]
    for label, grp in (('tard (>=18h)', late), ('tôt (<18h)', early)):
        if len(grp) < 10:
            print(f"  {label:14} n={len(grp)} (trop petit)"); continue
        wr = sum(1 for w, _ in grp if w) / len(grp)
        ex = st.mean(p for _, p in grp)
        se = (wr*(1-wr)/len(grp))**0.5
        print(f"  {label:14} n={len(grp):3} | réel {100*wr:.1f}% vs attendu {100*ex:.1f}% "
              f"| résidu {100*(wr-ex):+.1f} pts (±{196*se:.0f})")
    print(f"  (in-sample : le steamé gagnait davantage tard -> ici on vérifie si l'écart tard/tôt se confirme)")


def margin_watch():
    """Suivi OUT-OF-SAMPLE de l'hypothèse 'variation de marge'. Constat in-sample
    (08/08/2026, n=37 écarts publiés) : quand la marge de l'opérateur signalé
    S'ÉLARGIT entre le signal et la clôture, l'écart s'est refermé dans 100% des
    cas (CLV médian +26,4%, n=7) contre 23% quand la marge reste stable
    (corrélation marge~CLV : r=+0,65).
    Lecture proposée : le book n'élargit pas symétriquement, il rabaisse le côté
    sur lequel il est exposé -> l'élargissement est la signature de la correction
    en cours, pas de la prudence.
    RÉSERVES : n=7 sur la cellule clé, et risque de circularité (la marge finale
    et le CLV sont tous deux mesurés à la clôture). D'où ce suivi strictement
    out-of-sample avant toute exploitation."""
    import datetime as _dtm
    def _d(x):
        try: return _dtm.datetime.fromisoformat(str(x).replace('Z','').replace('+00:00',''))
        except Exception: return None
    log = 'canal_public_log.jsonl'
    if not os.path.exists(log):
        return
    curves = {}
    for src in ('book_curves_live.jsonl', 'book_curves.jsonl'):
        if not os.path.exists(src): continue
        for line in open(src, encoding='utf-8'):
            line = line.strip()
            if not line: continue
            try: r = json.loads(line)
            except Exception: continue
            ct = _d(r.get('commence_time'))
            if not ct: continue
            def _pre(seq):
                pts = [(_d(p[0]), p[1]) for p in (seq or []) if _d(p[0]) and p[1] and p[1] > 1]
                return sorted(x for x in pts if x[0] < ct)
            h, a = _pre(r.get('home_curve')), _pre(r.get('away_curve'))
            if h and a:
                curves[(r.get('uid'), r.get('book'))] = (h, a,
                    r.get('home_team') or r.get('home'), ct)

    def _val(seq, t):
        v = None
        for tt, o in seq:
            if tt <= t: v = o
            else: break
        return v

    def _marge(h, a, t):
        oh, oa = _val(h, t), _val(a, t)
        return (1/oh + 1/oa) if (oh and oa and oh > 1 and oa > 1) else None

    groups = {'élargie': [], 'stable': [], 'resserrée': []}
    for line in open(log, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try: m = json.loads(line)
        except Exception: continue
        tsig = _d(m.get('t'))
        if not tsig or tsig < _dtm.datetime.fromisoformat(FREEZE_DATE_MARGIN):
            continue                                   # OUT-OF-SAMPLE only
        for entry in (m.get('retards') or []):
            try: book, prix = entry[0], float(entry[1])
            except Exception: continue
            key = (m.get('uid'), book)
            if key not in curves: continue
            h, a, home, ct = curves[key]
            joueur = (m.get('joueur') or '').strip()
            seq = h if (home and home.strip() == joueur) else a
            if not seq: continue
            close = seq[-1][1]
            ms, mc = _marge(h, a, tsig), _marge(h, a, ct)
            if not close or ms is None or mc is None: continue
            clv = (prix/close - 1) * 100
            d = (mc - ms) * 100
            key2 = 'élargie' if d > 0.5 else ('resserrée' if d < -0.5 else 'stable')
            groups[key2].append(clv)

    n_tot = sum(len(v) for v in groups.values())
    print("\n" + "=" * 60)
    print(f"SUIVI HYPOTHÈSE — variation de marge (out-of-sample depuis {FREEZE_DATE_MARGIN})")
    if n_tot < 30:
        print(f"  n={n_tot} écarts — trop tôt pour juger (seuil 30). "
              f"Référence in-sample : marge élargie -> 100% refermés (n=7), stable -> 23%.")
        return
    for lab in ('élargie', 'stable', 'resserrée'):
        g = groups[lab]
        if len(g) < 5:
            print(f"  marge {lab:10} n={len(g):3} (trop petit)"); continue
        pos = 100 * sum(1 for x in g if x > 0) / len(g)
        print(f"  marge {lab:10} n={len(g):3} | CLV médian {st.median(g):+6.1f}% | refermés {pos:3.0f}%")
    print("  (si 'élargie' ne se distingue plus de 'stable', l'effet était du bruit)")


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
    calibration_watch()
    hour_watch()
    margin_watch()


if __name__ == '__main__':
    main()
