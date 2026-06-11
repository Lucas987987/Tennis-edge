#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reference_points.py — Exploitation des points de reference de la capture.

PRE-ENREGISTREMENT (2026-06-11) : seuils fixes avant lecture des chiffres.

Quatre questions, sur closing_lines.json (+ resultats_oddspapi.json) :

  R1 DERIVE FINALE (mecanique, pas besoin de resultats) :
     combien la ligne bouge-t-elle encore entre T-25 (t25) et T-3 (t3) ?
     -> distribution de |delta proba devigee| ; si c'est minuscule, la pression
     de capture de derniere minute est superflue ; si c'est gros, chaque
     capture ratee coute.

  R2 CALIBRATION PAR SNAPSHOT (resultats requis) :
     Brier de la proba devigee du vainqueur a t25/t15/t7/t3, sur le SOUS-
     ENSEMBLE COMMUN (matchs ayant tous les snapshots compares) pour etre
     equitable. -> attendre t3 achete-t-il de la precision ?

  R3 MARGE PINNACLE DANS LE TEMPS (mecanique) :
     marge (1/h + 1/a - 1) moyenne par tranche d'anciennete du point
     (>24h, 24-6h, 6-1h, 60-25min, 25-0min). + marge a la cloture vs
     agitation du marche (range des cotes home / open), par tercile.

  R4 MICRO-MOVE FINAL (resultats requis) :
     entre t25 et t3, le cote dont la proba MONTE de >= 1 pt de % est
     "late-steamed". Gagne-t-il plus que sa proba t3 ne le dit ?
     (complement de l'angle A2 de move_anatomy : si tout bouge avant T-60,
     ce qui bouge ENCORE a la fin est peut-etre l'info la plus pure.)

Garde-fou n >= MIN_N (30) ; [DIR] en dessous. Provisoire settlement =
exploration. Lecture seule, AUCUNE API.

Sources : CLOSING=closing_lines.json  RESULTS=resultats_oddspapi.json
"""
import json, os, sys, statistics as st

CLOSING = os.environ.get('CLOSING', 'closing_lines.json')
RESULTS = os.environ.get('RESULTS', 'resultats_oddspapi.json')
MIN_N   = int(os.environ.get('MIN_N', '30'))
MICRO_THRESH = 1.0   # pts de % de proba devigee entre t25 et t3 (pre-enregistre)
MARGIN_BUCKETS = [(1440, 10**9, '>24h'), (360, 1440, '24-6h'), (60, 360, '6-1h'),
                  (25, 60, '60-25min'), (0, 25, '25-0min')]
SNAPS = ('t25', 't15', 't7', 't3')


def devig_p(home, away):
    """Proba devigee du cote HOME."""
    try:
        a, b = 1.0 / float(home), 1.0 / float(away)
        return a / (a + b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def margin(home, away):
    try:
        return 1.0 / float(home) + 1.0 / float(away) - 1.0
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def pct(x, signe=False):
    if x is None:
        return '   -'
    return f"{x:+.1%}" if signe else f"{x:.1%}"


def tag(n):
    return '' if n >= MIN_N else ' [DIR]'


def section(t):
    print(f"\n── {t} " + '─' * max(0, 62 - len(t)))


def main():
    if not os.path.exists(CLOSING):
        print(f"❌ {CLOSING} manquant"); sys.exit(1)
    with open(CLOSING, encoding='utf-8') as f:
        closing = json.load(f)
    results = {}
    if os.path.exists(RESULTS):
        with open(RESULTS, encoding='utf-8') as f:
            results = json.load(f)

    entries = []
    for uid, e in closing.items():
        if not isinstance(e, dict):
            continue
        snaps = {}
        for lab in SNAPS:
            s = e.get(f'pinnacle_{lab}')
            if s and s.get('home') and s.get('away'):
                snaps[lab] = s
        r = results.get(str(e.get('fixture_id') or ''))
        winner = r.get('winner') if (r and not r.get('void')) else None
        entries.append({'uid': uid, 'e': e, 'snaps': snaps, 'winner': winner,
                        'home': e.get('home'), 'away': e.get('away')})

    n_with_result = sum(1 for x in entries if x['winner'])
    print(f"=== reference_points — {len(entries)} matchs dans {CLOSING}, "
          f"{n_with_result} avec resultat ===")
    print(f"(exploration pre-enregistree 2026-06-11 — [DIR] = n<{MIN_N})")

    # R1 — derive finale t25 -> t3 (mecanique) -------------------------------
    section("R1 DERIVE FINALE — mouvement de proba entre T-25 et T-3")
    deltas = []
    for x in entries:
        s25, s3 = x['snaps'].get('t25'), x['snaps'].get('t3')
        if not s25 or not s3:
            continue
        p25 = devig_p(s25['home'], s25['away'])
        p3 = devig_p(s3['home'], s3['away'])
        if p25 is None or p3 is None:
            continue
        deltas.append(abs(p3 - p25))
    if deltas:
        n = len(deltas)
        big = sum(1 for d in deltas if d >= 0.01)
        print(f"n={n} matchs avec t25 ET t3{tag(n)}")
        print(f"|delta p| moyen {st.mean(deltas):.2%} | mediane {st.median(deltas):.2%}"
              f" | max {max(deltas):.2%}")
        print(f"matchs ou la ligne bouge encore >=1pt entre T-25 et T-3 : {big}/{n} ({big/n:.0%})")
    else:
        print("aucun match avec t25 ET t3 — rien a mesurer.")

    # R2 — calibration par snapshot (sous-ensemble commun) --------------------
    section("R2 CALIBRATION — Brier de la proba du vainqueur par snapshot")
    common = [x for x in entries if x['winner']
              and all(lab in x['snaps'] for lab in SNAPS)]
    if common:
        n = len(common)
        print(f"sous-ensemble commun (4 snapshots + resultat) : n={n}{tag(n)}")
        for lab in SNAPS:
            briers = []
            for x in common:
                s = x['snaps'][lab]
                p_home = devig_p(s['home'], s['away'])
                if p_home is None:
                    continue
                y = 1.0 if x['winner'] == 'home' else 0.0
                briers.append((y - p_home) ** 2)
            if briers:
                print(f"  {lab:<4} Brier {st.mean(briers):.4f} (n={len(briers)})")
        print("  lecture : Brier qui BAISSE de t25 a t3 = les dernieres minutes")
        print("  affinent le prix ; plat = t25 suffit deja.")
    else:
        print("aucun match avec les 4 snapshots + resultat.")

    # R3 — marge Pinnacle dans le temps (mecanique) ----------------------------
    section("R3 MARGE PINNACLE — par anciennete du point (history)")
    buckets = {lab: [] for _, _, lab in MARGIN_BUCKETS}
    closes_m, ranges = [], []
    for x in entries:
        hist = [p for p in (x['e'].get('history') or [])
                if p.get('mins_before') is not None and p['mins_before'] >= 0
                and p.get('home') and p.get('away')]
        for p in hist:
            mg = margin(p['home'], p['away'])
            if mg is None:
                continue
            for lo, hi, lab in MARGIN_BUCKETS:
                if lo <= p['mins_before'] < hi:
                    buckets[lab].append(mg); break
        if len(hist) >= 3:
            mg_close = margin(hist[-1]['home'], hist[-1]['away'])
            prices = [p['home'] for p in hist]
            rng = (max(prices) - min(prices)) / prices[0] if prices[0] else None
            if mg_close is not None and rng is not None:
                closes_m.append(mg_close); ranges.append(rng)
    for lo, hi, lab in MARGIN_BUCKETS:
        b = buckets[lab]
        if b:
            print(f"  {lab:<9} n_pts={len(b):<5} marge moyenne {st.mean(b):.2%}")
    if len(closes_m) >= 6:
        paired = sorted(zip(closes_m, ranges))
        k = len(paired) // 3 or 1
        print("  marge a la cloture vs agitation des cotes (terciles de marge) :")
        for lab, grp in zip(('serree', 'moyenne', 'large'),
                            (paired[:k], paired[k:2*k], paired[2*k:])):
            if grp:
                print(f"    {lab:<8} marge {st.mean(g[0] for g in grp):.2%}"
                      f" -> range cotes {st.mean(g[1] for g in grp):.1%}"
                      f" (n={len(grp)}){tag(len(grp))}")

    # R4 — micro-move final vs resultat ----------------------------------------
    section(f"R4 MICRO-MOVE T-25 -> T-3 — late-steam >= {MICRO_THRESH:.0f}pt vs resultat")
    rows = []
    for x in entries:
        if not x['winner']:
            continue
        s25, s3 = x['snaps'].get('t25'), x['snaps'].get('t3')
        if not s25 or not s3:
            continue
        p25 = devig_p(s25['home'], s25['away'])
        p3 = devig_p(s3['home'], s3['away'])
        if p25 is None or p3 is None:
            continue
        d = p3 - p25   # >0 : home late-steamed ; <0 : away late-steamed
        if abs(d) < MICRO_THRESH / 100:
            side = None
        else:
            side = 'home' if d > 0 else 'away'
        rows.append({'side': side,
                     'p3_side': p3 if d > 0 else (1 - p3),
                     'won': None if side is None else (1 if x['winner'] == side else 0)})
    steamed = [r for r in rows if r['side']]
    calm = [r for r in rows if r['side'] is None]
    print(f"matchs t25+t3+resultat : {len(rows)} | late-steam : {len(steamed)} | stables : {len(calm)}")
    if steamed:
        n = len(steamed)
        wr = sum(r['won'] for r in steamed) / n
        pc = st.mean(r['p3_side'] for r in steamed)
        print(f"  late-steamed : gagne {pct(wr)} vs proba t3 {pct(pc)}"
              f" (residu {wr - pc:+.1%}, n={n}){tag(n)}")
        print("  residu ~0 = le prix t3 integre deja le micro-move ; residu >0 net et")
        print("  persistant = l'info de derniere minute n'est pas totalement pricee.")

    print("\nRappel : plusieurs questions sur les memes matchs => cases 'interessantes'")
    print("par hasard attendues. Seule la persistance quand n grandit compte.")


if __name__ == '__main__':
    main()
