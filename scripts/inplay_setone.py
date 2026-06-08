#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inplay_setone.py — LE test d'edge in-play : quand un favori perd le 1er set,
le marché LIVE surcote-t-il sa remontada ?

Pour chaque favori (défini par sa cote d'OUVERTURE) qui a PERDU le 1er set :
  - prix live post-set-1 ≈ PIC de sa cote en début d'in-play (son pire moment,
    juste après avoir lâché le set) -> dévigué -> proba implicite LIVE ;
  - réalisé = a-t-il gagné le match (0/1, lu dans resultats.json via le score) ;
  - par tranche de cote d'ouverture : n, implicite live moyen, taux réalisé
    (IC95 Wilson), et l'écart 'réalisé - implicite live'.

LECTURE : écart < 0 = le live SURCOTE la remontada (implicite live > réalisé)
=> valeur potentielle à COUCHER le favori / BACKER l'outsider en live.
Fiable seulement si n >= MIN_N (défaut 30) ET l'implicite live sort de l'IC du réalisé.

⚠ v1 : le « post-set-1 » est approximé par le PIC de cote (pas le timing exact ;
le timing propre viendra des marchés de set, à capturer plus tard). Descriptif,
quantité in-play : pas de pari sans exécution live (mur connu en France).

ENTRÉE : book_curves.jsonl + resultats.json (+ resultats_fast.json).
USAGE   : python scripts/inplay_setone.py
          python scripts/inplay_setone.py book_curves.jsonl
ENV     : IPS_PEAK_WINDOW_MIN [75]  IPS_MIN_INPLAY_PTS [3]  IPS_MIN_N [30]
          IPS_RESULTS [resultats.json]  IPS_RESULTS_FAST [resultats_fast.json]
"""
import os, sys, json, glob, math, unicodedata
from datetime import datetime, timezone

PEAK_WIN = float(os.environ.get('IPS_PEAK_WINDOW_MIN', '75'))
MIN_PTS  = int(os.environ.get('IPS_MIN_INPLAY_PTS', '3'))
MIN_N    = int(os.environ.get('IPS_MIN_N', '30'))
RES      = os.environ.get('IPS_RESULTS', 'resultats.json')
RES_FAST = os.environ.get('IPS_RESULTS_FAST', 'resultats_fast.json')
BUCKETS  = [(1.01, 1.30), (1.30, 1.50), (1.50, 1.70), (1.70, 2.00)]
SET1_MIN = float(os.environ.get('IPS_SET1END_MIN', '20'))   # offset plausible fin set 1
SET1_MAX = float(os.environ.get('IPS_SET1END_MAX', '90'))


# --------------------------------------------------------------------------- #
def dt(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
        return d.astimezone(timezone.utc).replace(tzinfo=None) if d.tzinfo else d
    except Exception:
        return None


def toks(name):
    s = unicodedata.normalize('NFKD', str(name)).encode('ascii', 'ignore').decode().lower()
    return {t for t in ''.join(c if c.isalpha() else ' ' for c in s).split() if len(t) >= 3}


def overlap(a, b):
    return bool(a & b)


def parse_set1(score):
    """Premier set d'une chaîne 'a-b ...' (perspective vainqueur). -> (wg, lg) | None."""
    if not isinstance(score, str):
        return None
    for tok in score.replace(',', ' ').split():
        t = tok.split('(')[0]
        if '-' in t:
            a, _, b = t.partition('-')
            try:
                return int(a), int(b)
            except ValueError:
                return None
    return None


# --------------------------------------------------------------------------- #
def load_results():
    """Fusion Sackmann (prioritaire) + fast. Chaque entrée : tokens des 2 joueurs,
    winner_code (1=home,2=away), et home_won_set1 (déduit du score)."""
    out = []
    seen = []
    for path, official in ((RES, True), (RES_FAST, False)):
        if not glob.glob(path):
            continue
        try:
            data = json.load(open(path, encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            continue
        for r in data.get('results', []):
            sc = parse_set1(r.get('score'))
            wc = r.get('winner_code')
            if sc is None or wc not in (1, 2):
                continue
            ht, at = toks(r.get('home_team', '')), toks(r.get('away_team', ''))
            if not ht or not at:
                continue
            key = frozenset(ht | at)
            if official:
                seen.append(key)
            elif key in seen:
                continue                                  # le fast ne double pas l'officiel
            wg, lg = sc
            winner_won_s1 = wg > lg
            home_won_s1 = winner_won_s1 if wc == 1 else (not winner_won_s1)
            out.append({'ht': ht, 'at': at, 'wc': wc, 'home_won_s1': home_won_s1})
    return out


def match_result(ch, ca, results):
    """Renvoie (result, orientation) ; orientation 'direct' si curve.home~res.home."""
    for r in results:
        if overlap(ch, r['ht']) and overlap(ca, r['at']):
            return r, 'direct'
        if overlap(ch, r['at']) and overlap(ca, r['ht']):
            return r, 'swap'
    return None, None


def opening_price(curve):
    pts = sorted((dt(p[0]), p[1]) for p in curve if isinstance(p, (list, tuple)) and len(p) >= 2 and dt(p[0]))
    return pts[0][1] if pts else None


def peak_after(curve, commence, window_min):
    """Pic de cote in-play (max) dans la fenêtre, + son timestamp."""
    inplay = sorted((dt(p[0]), p[1]) for p in curve
                    if isinstance(p, (list, tuple)) and len(p) >= 2 and dt(p[0]) and dt(p[0]) > commence)
    if len(inplay) < MIN_PTS:
        return None, None, len(inplay)
    win = [(t, pr) for t, pr in inplay if (t - commence).total_seconds() / 60.0 <= window_min]
    win = win or inplay
    t_peak, p_peak = max(win, key=lambda x: x[1])
    return p_peak, t_peak, len(inplay)


def price_at(curve, ts):
    """Dernière cote connue à ou avant ts (sinon la plus proche après)."""
    pts = sorted((dt(p[0]), p[1]) for p in curve if isinstance(p, (list, tuple)) and len(p) >= 2 and dt(p[0]))
    before = [pr for t, pr in pts if t <= ts]
    if before:
        return before[-1]
    return pts[0][1] if pts else None


def price_at_or_after(curve, ts):
    """Première cote à ou après ts (le prix juste après la fin du set 1)."""
    pts = sorted((dt(p[0]), p[1]) for p in curve if isinstance(p, (list, tuple)) and len(p) >= 2 and dt(p[0]))
    after = [pr for t, pr in pts if t >= ts]
    if after:
        return after[0]
    return pts[-1][1] if pts else None


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


# --------------------------------------------------------------------------- #
def main():
    cpath = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else 'book_curves.jsonl'
    if not glob.glob(cpath):
        sys.exit(f"Introuvable : {cpath}")
    results = load_results()

    diag = {'records': 0, 'matched': 0, 'fav_lost_s1': 0, 'usable': 0, 'no_inplay': 0}
    rows = []
    with open(cpath, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            diag['records'] += 1
            hc, ac = rec.get('home_curve') or [], rec.get('away_curve') or []
            commence = dt(rec.get('commence_time', ''))
            if not hc or not ac or commence is None:
                continue
            ho, ao = opening_price(hc), opening_price(ac)
            if not ho or not ao:
                continue
            fav_curve = 'home' if ho < ao else 'away'      # favori par cote d'ouverture

            res, orient = match_result(toks(rec.get('home', '')), toks(rec.get('away', '')), results)
            if not res:
                continue
            diag['matched'] += 1

            # côté du favori dans le référentiel résultat (home/away)
            fav_res = fav_curve if orient == 'direct' else ('away' if fav_curve == 'home' else 'home')
            fav_won_s1 = res['home_won_s1'] if fav_res == 'home' else (not res['home_won_s1'])
            if fav_won_s1:
                continue                                    # on ne garde que les favoris battus au set 1
            diag['fav_lost_s1'] += 1

            fav_curve_pts = hc if fav_curve == 'home' else ac
            opp_curve_pts = ac if fav_curve == 'home' else hc

            # timing : set1_end exact si dispo et plausible, sinon proxy du pic
            s2 = rec.get('set2_open') or {}
            set1_end = dt(s2.get('set1_end'))
            method = None
            if set1_end and SET1_MIN <= (set1_end - commence).total_seconds() / 60.0 <= SET1_MAX:
                fav_price = price_at_or_after(fav_curve_pts, set1_end)
                opp = price_at_or_after(opp_curve_pts, set1_end)
                method = 'exact'
            else:
                fav_price, t_peak, _ = peak_after(fav_curve_pts, commence, PEAK_WIN)
                opp = price_at(opp_curve_pts, t_peak) if t_peak else None
                method = 'pic'
            if not fav_price or not opp or opp <= 1 or fav_price <= 1:
                diag['no_inplay'] += 1
                continue
            implied_live = (1 / fav_price) / ((1 / fav_price) + (1 / opp))
            fav_won_match = (res['wc'] == 1 and fav_res == 'home') or (res['wc'] == 2 and fav_res == 'away')
            fav_open = min(ho, ao)
            diag['usable'] += 1
            diag[method] = diag.get(method, 0) + 1
            rows.append({'open': fav_open, 'implied_live': implied_live,
                         'won': 1 if fav_won_match else 0, 'method': method})

    # ---- rapport ----
    print("=" * 76)
    print("CALIBRATION IN-PLAY — favori battu au set 1 : le live surcote-t-il la remontada ?")
    print("=" * 76)
    print(f"enregistrements: {diag['records']} | joints à un résultat: {diag['matched']} | "
          f"favori battu au set 1: {diag['fav_lost_s1']} | exploitables: {diag['usable']}")
    print(f"  timing : {diag.get('exact', 0)} via set1_end EXACT, {diag.get('pic', 0)} via proxy PIC")
    if not rows:
        print("\nAucune observation exploitable (volume trop faible ou jointure de noms vide).")
        print("Rien d'anormal à ce stade : laisse la capture in-play s'accumuler.")
        return

    def block(label, sub):
        n = len(sub)
        if n == 0:
            print(f"  {label:14s}     —"); return
        k = sum(r['won'] for r in sub)
        real = k / n
        impl = sum(r['implied_live'] for r in sub) / n
        lo, hi = wilson(k, n)
        gap = real - impl
        flag = "" if n >= MIN_N else f"  (n<{MIN_N})"
        verdict = ""
        if n >= MIN_N:
            if impl > hi:
                verdict = "  <- live SURCOTE (impl. hors IC)"
            elif impl < lo:
                verdict = "  <- live SOUS-COTE"
        print(f"  {label:14s} {n:4d}   impl.live {impl*100:5.1f}%   "
              f"réalisé {real*100:5.1f}% [{lo*100:4.1f};{hi*100:4.1f}]   "
              f"écart {gap*100:+5.1f}{verdict}{flag}")

    print(f"\n  {'tranche cote':14s} {'n':>4s}    {'live (post-s1)':>14s}   {'réalisé':>22s}   écart")
    print("  " + "-" * 72)
    block("TOUTES", rows)
    print("  " + "-" * 72)
    for lo_b, hi_b in BUCKETS:
        block(f"{lo_b:.2f}-{hi_b:.2f}", [r for r in rows if lo_b <= r['open'] < hi_b])

    print(f"\n(n<{MIN_N}) = trop peu pour conclure. écart<0 = live surcote la remontada "
          "(valeur potentielle à backer l'outsider en live).")
    print("Timing : 'EXACT' = prix au 1er point après set1_end (marchés de set) ; "
          "'PIC' = fallback (pire moment) si set1_end absent/implausible.")
    print("⚠ Quantité in-play, descriptive — exécution live = mur connu (France).")


# --------------------------------------------------------------------------- #
def selftest():
    import random
    random.seed(5)

    def al(n):                                      # 0->a,1->b,... base 26, tokens uniques
        s = ""; n += 1
        while n:
            n, r = divmod(n - 1, 26); s = chr(97 + r) + s
        return s

    recs, results = [], []
    REAL = 0.30                                     # 30% des favoris battus au set 1 gagnent
    for i in range(60):
        home, away = f"Homo{al(i)}", f"Dako{al(i)}"   # tokens distincts par match
        fav_wins = random.random() < REAL
        ct = "2026-06-06T18:00:00Z"
        # favori = home ; pré-match ~1.55 ; point post-set-1 à 18:46 (~2.4) ; opp ~1.55
        hc = [["2026-06-06T17:00:00Z", 1.55], ["2026-06-06T17:55:00Z", 1.54],
              ["2026-06-06T18:25:00Z", 2.1], ["2026-06-06T18:46:00Z", 2.4],
              ["2026-06-06T19:30:00Z", 1.6 if fav_wins else 5.0]]
        ac = [["2026-06-06T17:00:00Z", 2.45], ["2026-06-06T18:46:00Z", 1.55]]
        recs.append({"uid": f"m{i}", "book": "bwin", "commence_time": ct,
                     "home": home, "away": away, "home_curve": hc, "away_curve": ac,
                     # set1_end à +45 min (plausible) -> chemin EXACT
                     "set2_open": {"12542": "2026-06-06T18:45:00Z", "12624": "2026-06-06T18:45:00Z",
                                   "set1_end": "2026-06-06T18:45:00Z"}})
        if fav_wins:                                # home gagne, a perdu le set 1
            wc, score = 1, "4-6 6-3 6-4"
        else:                                       # away gagne, a gagné le set 1
            wc, score = 2, "6-4 6-3"
        results.append({"home_team": home, "away_team": away, "winner_code": wc, "score": score})
    open("/home/claude/book_curves.jsonl", "w").write("\n".join(json.dumps(r) for r in recs))
    json.dump({"results": results}, open("/home/claude/resultats.json", "w"))
    open("/home/claude/resultats_fast.json", "w").write('{"results":[]}')
    sys.argv = ['x', '/home/claude/book_curves.jsonl']
    main()


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest()
    else:
        main()
