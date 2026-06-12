#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
move_anatomy.py — Anatomie des mouvements de cote (6 angles, UNE passe).

PRE-ENREGISTREMENT (2026-06-11) : les seuils ci-dessous sont fixes AVANT
d'avoir regarde les chiffres. Toute modification a posteriori pour "faire
ressortir" un effet = data dredging. 6 angles x plusieurs cases = des faux
positifs GARANTIS a petit n : seule une case qui reste stable quand n grandit
(et survit a un walk-forward) meritera une etude dediee.

Angles :
  A1 FORME    : saut brutal (>=60% du move dans une fenetre de 30 min) vs derive lente.
  A2 TIMING   : part du move deja faite a T-60 (early >=70%, late <=30%).
  A3 GROS MOVE -> MATCH COURT/ABANDON : straight sets & Retired/Walkover par tranche.
  A4 RETOURNEMENT : fakeout si amplitude >= max(2x|move|, 3%) (aller-retour).
  A5 CROSSOVER : le favori d'ouverture n'est plus le favori de cloture.
  A6 VOLATILITE : calibration de la cloture (Brier, residu) par tercile d'amplitude.

Cote "steamed" = celui dont la cote a raccourci (move_pct le plus negatif).
Tranches de move (A1-A4) : 0-2% stable / 2-5% modere / >5% gros.
Garde-fou n>=MIN_N(30) par case ; en-dessous : [DIR] = directionnel, pas de conclusion.
Donnees provisoires settlement : exploration uniquement.

Sources (lecture seule, AUCUNE API) :
  CLV_FILE=clv_history.jsonl   RESULTS=resultats_oddspapi.json
"""
import json, os, sys, datetime

CLV_FILE = os.environ.get('CLV_FILE', 'clv_history.jsonl')
RESULTS  = os.environ.get('RESULTS', 'resultats_oddspapi.json')
MIN_N    = int(os.environ.get('MIN_N', '30'))
SPLIT_DATE = os.environ.get('SPLIT_DATE', '2026-06-12')   # frontiere out-of-sample

# ---- seuils PRE-ENREGISTRES (ne pas retoucher apres lecture des resultats) ----
JUMP_WINDOW_MIN   = 30    # fenetre du "saut"
JUMP_SHARE        = 0.60  # part du move total concentree dans la fenetre
MOVE_MIN_PCT      = 3.0   # |move| minimal pour parler de forme/timing/fakeout
EARLY_DONE        = 0.70  # part du move faite a T-60 -> "early"
LATE_DONE         = 0.30  # -> "late"
FAKEOUT_AMP_RATIO = 2.0   # amplitude >= ratio x |move| -> fakeout
FAKEOUT_AMP_MIN   = 3.0   # ... et amplitude >= 3%
BUCKETS = [(0.0, 2.0, '0-2% stable'), (2.0, 5.0, '2-5% modere'), (5.0, 999.0, '>5% gros')]
ABANDON_STATUSES = {'Retired', 'Walkover', 'Abandoned'}


def parse_dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def devig(o_self, o_other):
    try:
        a, b = 1.0 / float(o_self), 1.0 / float(o_other)
        return a / (a + b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def curve_features(curve_raw, start, open_p, close_p):
    """Forme + timing sur la courbe PRE-match du cote steamed.
    Renvoie {'shape': 'saut'/'derive'/None, 'done_t60': float|None}."""
    out = {'shape': None, 'done_t60': None}
    if not curve_raw or open_p is None or close_p is None:
        return out
    pts = []
    for t, p in curve_raw:
        dt = parse_dt(t)
        if dt is None:
            continue
        if start is None or dt <= start:
            pts.append((dt, float(p)))
    if len(pts) < 3:
        return out
    pts.sort(key=lambda x: x[0])
    total = close_p - open_p
    if abs(total) / open_p * 100 < MOVE_MIN_PCT:
        return out  # move trop petit : pas de forme/timing
    # A1 forme : plus grande variation NETTE dans une fenetre glissante de 30 min
    best = 0.0
    j = 0
    for i in range(len(pts)):
        while pts[i][0] - pts[j][0] > datetime.timedelta(minutes=JUMP_WINDOW_MIN):
            j += 1
        delta = pts[i][1] - pts[j][1]
        if delta * total > 0:  # meme sens que le move global
            best = max(best, abs(delta))
    out['shape'] = 'saut' if best >= JUMP_SHARE * abs(total) else 'derive'
    # A2 timing : part du move deja faite a T-60
    if start is not None:
        t60 = start - datetime.timedelta(minutes=60)
        before = [p for dt, p in pts if dt <= t60]
        if before:
            done = (before[-1] - open_p) / total if total else None
            if done is not None:
                out['done_t60'] = max(0.0, min(1.5, done))
    return out


def load_rows():
    if not os.path.exists(CLV_FILE) or not os.path.exists(RESULTS):
        print(f"❌ fichier manquant ({CLV_FILE} / {RESULTS})"); sys.exit(1)
    with open(RESULTS, encoding='utf-8') as f:
        results = json.load(f)
    rows, seen = [], set()
    with open(CLV_FILE, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            fid = str(e.get('fixture_id') or '')
            if not fid or fid in seen:
                continue
            seen.add(fid)
            r = results.get(fid)
            if not r:
                continue   # pas encore de resultat
            hm, am = e.get('home_metrics') or {}, e.get('away_metrics') or {}
            if hm.get('move_pct') is None or am.get('move_pct') is None:
                continue
            cand = [('home', hm, am, e.get('home_curve')),
                    ('away', am, hm, e.get('away_curve'))]
            side, ms, mo, curve = min(cand, key=lambda c: c[1]['move_pct'])
            p_close = devig(ms.get('close'), mo.get('close'))
            p_open  = devig(ms.get('open'), mo.get('open'))
            if p_close is None:
                continue
            start = parse_dt(e.get('commence_time'))
            feats = curve_features(curve, start, ms.get('open'), ms.get('close'))
            void = bool(r.get('void'))
            abandon = void and (r.get('status_name') in ABANDON_STATUSES)
            row = {
                'fid': fid, 'ct': str(e.get('commence_time') or '')[:10],
                'home': e.get('home'), 'away': e.get('away'),
                'steam_side': side,
                'steam_move': abs(min(ms['move_pct'], 0.0)),
                'amp': ms.get('amplitude_pct'),
                'p_close': p_close, 'p_open': p_open,
                'shape': feats['shape'], 'done_t60': feats['done_t60'],
                'void': void, 'abandon': abandon,
                'won_match': None, 'won_set1': None, 'straight': None,
                'crossover': (p_open is not None
                              and (p_open - 0.5) * (p_close - 0.5) < 0),
            }
            if not void and r.get('winner'):
                row['won_match'] = 1 if r['winner'] == side else 0
                s1 = r.get('set1')
                row['won_set1'] = (1 if s1 == side else 0) if s1 in ('home', 'away') else None
                p1, p2 = r.get('p1_sets'), r.get('p2_sets')
                if p1 is not None and p2 is not None:
                    row['straight'] = 1 if min(p1, p2) == 0 else 0
            rows.append(row)
    return rows


def bucket_of(mv):
    for lo, hi, label in BUCKETS:
        if lo <= mv < hi:
            return label
    return BUCKETS[-1][2]


def pct(x):
    return f"{x:.1%}" if x is not None else '   -'


def rate(rows, key):
    vals = [r[key] for r in rows if r[key] is not None]
    return (sum(vals) / len(vals), len(vals)) if vals else (None, 0)


def tag(n):
    return '' if n >= MIN_N else ' [DIR]'


def section(title):
    print(f"\n── {title} " + '─' * max(0, 60 - len(title)))


def main():
    rows = load_rows()
    decided = [r for r in rows if r['won_match'] is not None]
    print(f"=== move_anatomy — {len(rows)} matchs joints ({len(decided)} decides, "
          f"{sum(1 for r in rows if r['void'])} void) ===")
    print(f"(exploration pre-enregistree 2026-06-11 — provisoire settlement, [DIR] = n<{MIN_N})")
    if not rows:
        return
    n_curves = sum(1 for r in rows if r['shape'] is not None or r['done_t60'] is not None)
    print(f"courbes exploitables (move>={MOVE_MIN_PCT}%) : {n_curves}")

    # A1 FORME ---------------------------------------------------------------
    section("A1 FORME — saut (<=30min) vs derive lente (matchs avec move>=3%)")
    for shape in ('saut', 'derive'):
        g = [r for r in decided if r['shape'] == shape]
        if not g:
            print(f"{shape:<8} n=0"); continue
        wm, n = rate(g, 'won_match'); s1, n1 = rate(g, 'won_set1')
        pc = sum(r['p_close'] for r in g) / len(g)
        print(f"{shape:<8} n={n:<3} match {pct(wm)} vs close {pct(pc)} (residu {wm-pc:+.1%})"
              f" | set1 {pct(s1)} (n={n1}){tag(n)}")

    # A2 TIMING --------------------------------------------------------------
    section("A2 TIMING — part du move faite a T-60 (early>=70%, late<=30%)")
    for lab, cond in (('early', lambda d: d >= EARLY_DONE),
                      ('progressif', lambda d: LATE_DONE < d < EARLY_DONE),
                      ('late', lambda d: d <= LATE_DONE)):
        g = [r for r in decided if r['done_t60'] is not None and cond(r['done_t60'])]
        if not g:
            print(f"{lab:<10} n=0"); continue
        wm, n = rate(g, 'won_match'); s1, n1 = rate(g, 'won_set1')
        pc = sum(r['p_close'] for r in g) / len(g)
        print(f"{lab:<10} n={n:<3} match {pct(wm)} vs close {pct(pc)} (residu {wm-pc:+.1%})"
              f" | set1 {pct(s1)} (n={n1}){tag(n)}")

    # A3 MATCH COURT / ABANDON ------------------------------------------------
    section("A3 GROS MOVE -> MATCH COURT / ABANDON (par tranche de move)")
    for lo, hi, label in BUCKETS:
        g_all = [r for r in rows if bucket_of(r['steam_move']) == label]
        g_dec = [r for r in g_all if r['won_match'] is not None]
        if not g_all:
            continue
        st, n_st = rate(g_dec, 'straight')
        n_ab = sum(1 for r in g_all if r['abandon'])
        ab = n_ab / len(g_all)
        print(f"{label:<12} n={len(g_all):<3} straight-sets {pct(st)} (n={n_st})"
              f" | abandons {pct(ab)} ({n_ab}/{len(g_all)}){tag(len(g_all))}")

    # A4 RETOURNEMENT ----------------------------------------------------------
    section("A4 RETOURNEMENT — fakeout (amplitude>=2x|move| et >=3%) vs move net")
    for lab, cond in (('fakeout', lambda r: r['amp'] is not None
                       and r['amp'] >= max(FAKEOUT_AMP_RATIO * r['steam_move'], FAKEOUT_AMP_MIN)),
                      ('move net', lambda r: r['steam_move'] >= MOVE_MIN_PCT
                       and (r['amp'] is None or r['amp'] < FAKEOUT_AMP_RATIO * r['steam_move']))):
        g = [r for r in decided if cond(r)]
        if not g:
            print(f"{lab:<9} n=0"); continue
        wm, n = rate(g, 'won_match'); s1, n1 = rate(g, 'won_set1')
        pc = sum(r['p_close'] for r in g) / len(g)
        print(f"{lab:<9} n={n:<3} match {pct(wm)} vs close {pct(pc)} (residu {wm-pc:+.1%})"
              f" | set1 {pct(s1)} (n={n1}){tag(n)}")

    # A5 CROSSOVER --------------------------------------------------------------
    section("A5 CROSSOVER — le favori change entre ouverture et cloture")
    g = [r for r in rows if r['crossover']]
    g_dec = [r for r in g if r['won_match'] is not None]
    print(f"crossovers : {len(g)} / {len(rows)} matchs")
    for r in g:
        res = {1: 'steamed GAGNE', 0: 'steamed perd'}.get(r['won_match'], 'void/en attente')
        s1 = {1: 'set1 oui', 0: 'set1 non'}.get(r['won_set1'], 'set1 ?')
        print(f"  {r['home']} vs {r['away']} | move {r['steam_move']:.1f}% "
              f"p_open {pct(r['p_open'])} -> p_close {pct(r['p_close'])} | {res}, {s1}")
    if g_dec:
        wm, n = rate(g_dec, 'won_match')
        pc = sum(r['p_close'] for r in g_dec) / len(g_dec)
        print(f"  => bilan : match {pct(wm)} vs close {pct(pc)} (n={n}){tag(n)}")

    # A6 VOLATILITE -> CALIBRATION ------------------------------------------------
    section("A6 VOLATILITE — calibration de la cloture par tercile d'amplitude")
    with_amp = sorted([r for r in decided if r['amp'] is not None], key=lambda r: r['amp'])
    if with_amp:
        k = len(with_amp) // 3 or 1
        terciles = [with_amp[:k], with_amp[k:2*k], with_amp[2*k:]]
        for lab, g in zip(('calme', 'moyen', 'agite'), terciles):
            if not g:
                continue
            n = len(g)
            amp_rng = f"{g[0]['amp']:.1f}-{g[-1]['amp']:.1f}%"
            brier = sum((r['won_match'] - r['p_close']) ** 2 for r in g) / n
            wm = sum(r['won_match'] for r in g) / n
            pc = sum(r['p_close'] for r in g) / n
            print(f"{lab:<6} (amp {amp_rng:>11}) n={n:<3} Brier {brier:.3f}"
                  f" | realise {pct(wm)} vs close {pct(pc)} (residu {wm-pc:+.1%}){tag(n)}")

    # ── OUT-OF-SAMPLE : la SEULE case pre-enregistree comme hypothese (gros move) ──
    section(f"OOS — gros move (>5%) sur les matchs >= {SPLIT_DATE} uniquement")
    fresh = [r for r in decided if r['ct'] >= SPLIT_DATE and bucket_of(r['steam_move']) == BUCKETS[-1][2]]
    if fresh:
        n = len(fresh)
        wm = sum(r['won_match'] for r in fresh) / n
        pc = sum(r['p_close'] for r in fresh) / n
        print(f"n={n} | match {wm:.1%} vs close {pc:.1%} (residu {wm - pc:+.1%}){tag(n)}")
        print(f"(in-sample de reference au {SPLIT_DATE} : residu +14.9% sur n=36)")
    else:
        print("aucun match frais dans cette tranche pour l'instant — patience.")

    print("\nRappel : 6 angles testes en parallele => des cases 'interessantes' par hasard")
    print("sont attendues. Ne retenir que ce qui persiste quand n grandit (Sackmann + RG).")


if __name__ == '__main__':
    main()
