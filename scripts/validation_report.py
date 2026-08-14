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
FREEZE_DATE_MARGIN = '2026-08-09'
FREEZE_DATE_ROUND  = '2026-08-10'
FREEZE_DATE_BIGMOVE = '2026-08-10'
FREEZE_DATE_EARLYOPEN = '2026-08-13'  # hypothèse 'book ouvert avant Pinnacle' gelée ce jour
FREEZE_DATE_REINFORCE = '2026-08-14'  # hypothèse 'renforcement de l'outsider d'ouverture' gelée ce jour
FREEZE_DATE_REACTIVE = '2026-08-14'  # hypothèse 'book rapide en anomalie > book lent chronique' gelée ce jour

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


def round_watch():
    """Suivi OUT-OF-SAMPLE de l'hypothèse 'phase de tournoi'. Constat in-sample
    (09/08/2026, n=84 écarts) : le CLV décroît quand le tournoi avance --
    premiers tours (>=16 matchs/jour) +16,0% et 100% refermés, contre
    demies/finale (<4 matchs/jour) +10,2% et 77% refermés. Gradient monotone.
    Lecture : les books tiennent mieux leurs prix sur les phases finales
    (plus de volume, plus d'attention) ; l'inattention du marché -- donc l'edge
    -- se concentre sur les premiers tours.
    Proxy du tour : nombre de matchs du MEME tournoi le MEME jour (32 matchs =
    premiers tours, 2 = demi-finales). Pas de champ 'round' dans l'API."""
    import datetime as _dtm
    from collections import defaultdict as _dd
    def _d(x):
        try: return _dtm.datetime.fromisoformat(str(x).replace('Z','').replace('+00:00',''))
        except Exception: return None
    log = 'canal_public_log.jsonl'
    if not os.path.exists(log):
        return
    # date + tournoi de chaque match, depuis les courbes
    meta, per_day = {}, _dd(set)
    for src in ('book_curves_live.jsonl', 'book_curves.jsonl'):
        if not os.path.exists(src): continue
        for line in open(src, encoding='utf-8'):
            line = line.strip()
            if not line: continue
            try: r = json.loads(line)
            except Exception: continue
            ct = _d(r.get('commence_time'))
            if not ct: continue
            uid = r.get('uid')
            meta[uid] = (r.get('tournament') or '', ct)
            per_day[(r.get('tournament') or '', ct.date())].add(uid)
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
                pts = [(_d(x[0]), x[1]) for x in (seq or []) if _d(x[0]) and x[1] and x[1] > 1]
                return sorted(q for q in pts if q[0] < ct)
            h, a = _pre(r.get('home_curve')), _pre(r.get('away_curve'))
            if h and a:
                curves[(r.get('uid'), r.get('book'))] = (h, a,
                    r.get('home_team') or r.get('home'))
    buckets = {'premiers tours': [], 'milieu': [], 'phases finales': []}
    for line in open(log, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try: m = json.loads(line)
        except Exception: continue
        t = _d(m.get('t'))
        if not t or t < _dtm.datetime.fromisoformat(FREEZE_DATE_ROUND):
            continue                                    # OUT-OF-SAMPLE only
        uid = m.get('uid')
        if uid not in meta: continue
        tour, ct = meta[uid]
        nday = len(per_day[(tour, ct.date())])
        lab = ('premiers tours' if nday >= 16 else
               ('milieu' if nday >= 4 else 'phases finales'))
        for entry in (m.get('retards') or []):
            try: book, prix = entry[0], float(entry[1])
            except Exception: continue
            key = (uid, book)
            if key not in curves: continue
            h, a, home = curves[key]
            joueur = (m.get('joueur') or '').strip()
            seq = h if (home and home.strip() == joueur) else a
            if not seq: continue
            close = seq[-1][1]
            if close:
                buckets[lab].append((prix/close - 1) * 100)
    n_tot = sum(len(v) for v in buckets.values())
    print("\n" + "=" * 60)
    print(f"SUIVI HYPOTHÈSE — phase de tournoi (out-of-sample depuis {FREEZE_DATE_ROUND})")
    if n_tot < 30:
        print(f"  n={n_tot} écarts — trop tôt pour juger (seuil 30). Référence in-sample : "
              f"premiers tours +16,0% / 100% refermés, phases finales +10,2% / 77%.")
        return
    for lab in ('premiers tours', 'milieu', 'phases finales'):
        g = buckets[lab]
        if len(g) < 5:
            print(f"  {lab:16} n={len(g):3} (trop petit)"); continue
        pos = 100 * sum(1 for x in g if x > 0) / len(g)
        print(f"  {lab:16} n={len(g):3} | CLV médian {st.median(g):+6.1f}% | refermés {pos:3.0f}%")
    print("  (si le gradient premiers tours > phases finales disparaît, l'effet était du bruit)")


def bigmove_watch():
    """Suivi OUT-OF-SAMPLE : un gros mouvement (>=15pts) SANS retard détecté au
    moment du signal a-t-il quand même de la valeur ? Constat in-sample
    (09/08/2026) : à ampleur égale 3-10pts, un retard détecté fait passer le
    CLV de +3,3% (sans) à +13,5% (avec) -- n=475. Sur les moves >=15pts,
    échantillon insuffisant pour trancher (n=0) : c'est précisément ce que ce
    suivi va combler avec les prochaines semaines de collecte.
    Cas déclencheur : Baez/Brooksby (04/08) -- move ~30pts, aucun retard
    détecté au moment du signal, donc non publiés sur le canal principal."""
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
                pts = [(_d(x[0]), x[1]) for x in (seq or []) if _d(x[0]) and x[1] and x[1] > 1]
                return sorted(q for q in pts if q[0] < ct)
            h, a = _pre(r.get('home_curve')), _pre(r.get('away_curve'))
            if h and a:
                curves[(r.get('uid'), r.get('book'))] = (h, a,
                    r.get('home_team') or r.get('home'))
    buckets = {'grand mouvement, sans retard': [], 'grand mouvement, avec retard': []}
    for line in open(log, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try: m = json.loads(line)
        except Exception: continue
        t = _d(m.get('t'))
        if not t or t < _dtm.datetime.fromisoformat(FREEZE_DATE_BIGMOVE):
            continue                                    # OUT-OF-SAMPLE only
        mag_pts = abs(m.get('cote_ref_avant', 1) and
                     (1/m['cote_ref_apres'] - 1/m['cote_ref_avant'])) * 100 if m.get('cote_ref_apres') else 0
        if mag_pts < 15:
            continue                                    # seuil 'gros mouvement'
        lags = m.get('retards') or []
        lab = 'grand mouvement, avec retard' if lags else 'grand mouvement, sans retard'
        joueur = (m.get('joueur') or '').strip()
        uid = m.get('uid')
        # CLV du meilleur prix dispo (même sans retard >=5%, on veut voir ce qu'il y avait)
        best_book, best_price = None, None
        for b, (h, a, home) in curves.items():
            if b[0] != uid: continue
            seq = h if (home and home.strip() == joueur) else a
            if not seq: continue
            pr = seq[-1][1] if b[1] != 'pinnacle' else None   # ignore pinnacle lui-même
        # on utilise directement les retards loggés s'il y en a, sinon on ne peut
        # pas juger le CLV (aucun prix mou capté) -> on compte juste la fréquence
        if lags:
            book, prix = lags[0][0], float(lags[0][1])
            key = (uid, book)
            if key in curves:
                h, a, home = curves[key]
                seq = h if (home and home.strip() == joueur) else a
                if seq and seq[-1][1]:
                    buckets[lab].append((prix / seq[-1][1] - 1) * 100)
        else:
            buckets[lab].append(None)   # pas de prix mou loggé : fréquence seulement

    n_tot = sum(len(v) for v in buckets.values())
    print("\n" + "=" * 60)
    print(f"SUIVI HYPOTHÈSE — gros mouvement sans retard détecté (depuis {FREEZE_DATE_BIGMOVE})")
    if n_tot < 15:
        print(f"  n={n_tot} gros mouvements (>=15pts) — trop tôt pour juger (seuil 15). "
              f"Cas déclencheur : Baez/Brooksby, 0 retard détecté malgré ~30pts de move.")
        return
    for lab in buckets:
        g = [x for x in buckets[lab] if x is not None]
        n_all = len(buckets[lab])
        if g:
            pos = 100 * sum(1 for x in g if x > 0) / len(g)
            print(f"  {lab:32} n={n_all:3} (CLV mesurable sur {len(g)}) | "
                  f"CLV médian {st.median(g):+6.1f}% | refermés {pos:3.0f}%")
        else:
            print(f"  {lab:32} n={n_all:3} (aucun prix mou loggé pour mesurer le CLV)")


def earlyopen_watch():
    """Suivi OUT-OF-SAMPLE de l'hypothèse 'book ouvert avant Pinnacle' (voir
    scripts/early_open_signal.py pour le contexte complet). Constat IN-SAMPLE
    (1042 matchs, formulé le 13/08) : au moment où Pinnacle publie son 1er
    prix, un book déjà ouvert depuis des heures avec un écart >=5% a un CLV
    médian de +8,6% et se referme dans 81% des cas (n=144) -- mais le ROI
    reste non concluant (IC95 [-32%,+4%]).
    Source : early_open_log.jsonl (écrit par early_open_signal.py), qui
    contient déjà le prix signalé + le book -- il suffit de retrouver la
    clôture réelle du même book dans les courbes pour mesurer le CLV réalisé,
    exactement comme canal_clv.py le fait pour les écarts du canal public."""
    import datetime as _dtm
    log = 'early_open_log.jsonl'
    if not os.path.exists(log):
        return
    def _d(x):
        try: return _dtm.datetime.fromisoformat(str(x).replace('Z', '').replace('+00:00', ''))
        except Exception: return None

    closes = {}
    for src in ('book_curves_live.jsonl', 'book_curves.jsonl'):
        if not os.path.exists(src): continue
        for line in open(src, encoding='utf-8'):
            line = line.strip()
            if not line: continue
            try: r = json.loads(line)
            except Exception: continue
            ct = _d(r.get('commence_time'))
            if not ct: continue
            home = r.get('home_team') or r.get('home') or ''
            away = r.get('away_team') or r.get('away') or ''
            for key, name in (('home_curve', home), ('away_curve', away)):
                pts = [(_d(t), o) for t, o in (r.get(key) or []) if _d(t) and o and o > 1]
                pts = sorted(p for p in pts if p[0] < ct)
                if pts and name:
                    closes[(r.get('uid'), r.get('book'), name)] = pts[-1][1]

    rows = []
    for line in open(log, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try: m = json.loads(line)
        except Exception: continue
        t = _d(m.get('t'))
        if not t or t < _dtm.datetime.fromisoformat(FREEZE_DATE_EARLYOPEN):
            continue                                    # OUT-OF-SAMPLE only
        joueur = m['home'] if m.get('side') == 'home' else m.get('away')
        cl = closes.get((m.get('uid'), m.get('book'), joueur))
        if cl:
            rows.append((m['price'] / cl - 1) * 100)

    print(f"\n{'='*60}")
    print(f"SUIVI HYPOTHÈSE — book ouvert avant Pinnacle (out-of-sample depuis {FREEZE_DATE_EARLYOPEN})")
    if len(rows) < 30:
        print(f"  n={len(rows)} signaux mesurables — trop tôt pour juger (seuil 30). "
              f"Référence in-sample : CLV médian +8,6%, 81% refermés (n=144).")
        return
    pos = 100 * sum(1 for x in rows if x > 0) / len(rows)
    print(f"  n={len(rows)} | CLV médian {st.median(rows):+.1f}% | refermés {pos:.0f}%")
    print("  (si ces chiffres tiennent près des références in-sample, l'hypothèse est confirmée ;")
    print("   s'ils s'effondrent vers 0%/50%, c'était du bruit -- comme la marge et l'heure du match)")


def reinforce_watch():
    """Suivi OUT-OF-SAMPLE de l'hypothèse 'renforcement de l'outsider
    d'ouverture'. Question testée : entre l'ouverture et la clôture Pinnacle,
    l'outsider d'ouverture a-t-il tendance à s'enfoncer encore, ou le marché
    corrige-t-il vers lui (l'écart d'ouverture était souvent trop large) ?

    Constat IN-SAMPLE (1040 matchs, formulé le 14/08) : sur les matchs avec
    mouvement net, l'outsider d'ouverture se RENFORCE (le marché corrige vers
    lui) dans 56,1% des cas -- z=-3,74, significatif -- avec un gradient net
    selon l'ampleur de l'écart d'ouverture : 49% (serré) -> 65% (écrasant).
    ATTENTION : ceci porte sur le MOUVEMENT DE PRIX, pas sur le résultat du
    match. Le ROI d'une stratégie 'miser l'outsider écrasant à l'ouverture'
    a été testé et est NON CONCLUANT (n=118, ROI -5,6% IC95[-48%,+37%]) --
    ce suivi ne sert donc qu'à confirmer/infirmer le mouvement de prix,
    jamais une recommandation de mise.

    Contrairement aux autres suivis (qui relisent les alertes publiées),
    celui-ci scanne TOUS les matchs (mouvement Pinnacle open->close),
    puisque la question porte sur le comportement général du marché, pas
    sur des écarts de retard spécifiques."""
    import datetime as _dtm
    def _d(x):
        try: return _dtm.datetime.fromisoformat(str(x).replace('Z', '').replace('+00:00', ''))
        except Exception: return None

    rows = []
    for src in ('book_curves_live.jsonl', 'book_curves.jsonl'):
        if not os.path.exists(src): continue
        games = {}
        for line in open(src, encoding='utf-8'):
            line = line.strip()
            if not line: continue
            try: r = json.loads(line)
            except Exception: continue
            ct = _d(r.get('commence_time'))
            if not ct or ct < _dtm.datetime.fromisoformat(FREEZE_DATE_REINFORCE):
                continue                                    # OUT-OF-SAMPLE only
            def pre(seq):
                pts = [(_d(p[0]), p[1]) for p in (seq or []) if _d(p[0]) and p[1] and p[1] > 1]
                return sorted(x for x in pts if x[0] < ct)
            h, a = pre(r.get('home_curve')), pre(r.get('away_curve'))
            if len(h) < 3 or len(a) < 3: continue
            g = games.setdefault(r['uid'], {})
            g[r['book']] = {'h': h, 'a': a}
        for uid, g in games.items():
            pin = g.get('pinnacle')
            if not pin: continue
            p_open = _shin_ph(pin['h'][0][1], pin['a'][0][1])
            p_close = _shin_ph(pin['h'][-1][1], pin['a'][-1][1])
            delta = p_close - p_open
            if abs(delta) < 0.005: continue                # quasi-stable, ignoré
            fav_open_home = p_open > 0.5
            reinforced = (delta > 0) if fav_open_home else (delta < 0)
            gap_open = abs(p_open - 0.5) * 200
            rows.append((reinforced, gap_open))

    print("\n" + "=" * 60)
    print(f"SUIVI HYPOTHÈSE — renforcement de l'outsider d'ouverture (depuis {FREEZE_DATE_REINFORCE})")
    if len(rows) < 30:
        print(f"  n={len(rows)} matchs — trop tôt pour juger (seuil 30). "
              f"Référence in-sample : 56,1% global, gradient 49%->65% selon l'écart d'ouverture.")
        return
    n_reinf = sum(1 for r, _ in rows if r)
    pct = 100 * n_reinf / len(rows)
    print(f"  n={len(rows)} | outsider d'ouverture renforcé : {pct:.1f}% (référence 56,1%)")
    for lo, hi, lab in ((0, 15, 'serré'), (15, 35, 'modéré'), (35, 60, 'net'), (60, 200, 'écrasant')):
        g = [r for r, gp in rows if lo <= gp < hi]
        if len(g) >= 15:
            p = 100 * sum(1 for x in g if x) / len(g)
            print(f"    {lab:10} n={len(g):4} | renforcé {p:.0f}%")
    print("  (si le gradient disparaît ou repasse sous 50% partout, c'était du bruit)")


def reactive_watch():
    """Suivi OUT-OF-SAMPLE de l'hypothèse 'book habituellement RAPIDE en
    anomalie > book habituellement LENT chronique'. Question testée : quand
    deux books affichent un écart ≥5%, celui qui est normalement réactif
    (score de fiabilité sous la médiane, voir book_reliability.py) referme-
    t-il mieux son écart que celui qui est structurellement lent ?

    Constat IN-SAMPLE (123 écarts, formulé le 14/08) : CONTRE-INTUITIF -- le
    book habituellement RAPIDE bat systématiquement le book habituellement
    LENT sur les 3 comparaisons testées (CLV +18,7% vs +9,1% à ampleur
    égale ; 92% vs 73% de refermeture). Hypothèse explicative : un book
    rapide qui montre un écart vit une vraie ANOMALIE ponctuelle (son
    système va "rattraper" son comportement habituel) ; un book lent qui
    montre un écart est peut-être juste dans son état normal (marge large
    en continu), donc rien ne le pousse à converger.
    RÉSERVE : direction cohérente sur 3 comparaisons indépendantes (pas une
    coïncidence isolée), mais échantillons individuels modestes (10 à 70).
    book_scores.json étant recalculé chaque nuit sur une fenêtre glissante
    de 45 jours, la médiane de référence évolue avec le temps -- c'est
    voulu, elle doit refléter l'état ACTUEL des books, pas un instantané figé."""
    import datetime as _dtm
    def _d(x):
        try: return _dtm.datetime.fromisoformat(str(x).replace('Z', '').replace('+00:00', ''))
        except Exception: return None
    log = 'canal_public_log.jsonl'
    scores_file = 'book_scores.json'
    if not os.path.exists(log) or not os.path.exists(scores_file):
        return
    try:
        with open(scores_file, encoding='utf-8') as f:
            scores = json.load(f).get('scores', {})
    except Exception:
        return
    reliab = {b: v.get('reliability_score', 0) for b, v in scores.items()}
    if len(reliab) < 4:
        return                                          # trop peu de books scorés pour un split médian utile
    med = st.median(reliab.values())

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
                curves[(r.get('uid'), r.get('book'))] = (h, a, r.get('home_team') or r.get('home'))

    groups = {'rapide (< médiane)': [], 'lent (>= médiane)': []}
    for line in open(log, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try: m = json.loads(line)
        except Exception: continue
        t = _d(m.get('t'))
        if not t or t < _dtm.datetime.fromisoformat(FREEZE_DATE_REACTIVE):
            continue                                    # OUT-OF-SAMPLE only
        joueur = (m.get('joueur') or '').strip()
        for entry in (m.get('retards') or []):
            try: book, prix = entry[0], float(entry[1])
            except Exception: continue
            if book not in reliab:
                continue                                # book pas encore scoré (trop peu d'historique)
            key = (m.get('uid'), book)
            if key not in curves: continue
            h, a, home = curves[key]
            seq = h if (home and home.strip() == joueur) else a
            if not seq: continue
            close = seq[-1][1]
            if not close: continue
            clv = (prix / close - 1) * 100
            lab = 'rapide (< médiane)' if reliab[book] < med else 'lent (>= médiane)'
            groups[lab].append(clv)

    n_tot = sum(len(v) for v in groups.values())
    print("\n" + "=" * 60)
    print(f"SUIVI HYPOTHÈSE — book rapide en anomalie vs book lent chronique (depuis {FREEZE_DATE_REACTIVE})")
    if n_tot < 30:
        print(f"  n={n_tot} écarts — trop tôt pour juger (seuil 30). Référence in-sample : "
              f"rapide +18,7%/92% refermés vs lent +9,1%/73% (à ampleur égale, 3-10pts).")
        return
    for lab in groups:
        g = groups[lab]
        if len(g) < 8:
            print(f"  {lab:20} n={len(g):3} (trop petit)"); continue
        pos = 100 * sum(1 for x in g if x > 0) / len(g)
        print(f"  {lab:20} n={len(g):3} | CLV médian {st.median(g):+6.1f}% | refermés {pos:3.0f}%")
    print("  (si 'rapide' ne bat plus 'lent', l'effet était du bruit malgré la cohérence in-sample)")


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
    round_watch()
    bigmove_watch()
    earlyopen_watch()
    reinforce_watch()
    reactive_watch()


if __name__ == '__main__':
    main()
