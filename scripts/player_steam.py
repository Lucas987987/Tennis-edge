#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
player_steam.py — L'interet "sharp" pour un joueur PERSISTE-t-il d'un match a l'autre ?

PRE-ENREGISTREMENT (2026-06-12) : un joueur est "steamed" sur un match si SA
cote a raccourci de >= 3% (open->close). Question de recurrence :
  P(steamed au match k+1 | steamed au match k)  vs  taux de base P(steamed).
Si l'argent informe suit un joueur (forme cachee, retour de blessure), la
recurrence depasse la base — et le DEBUT d'une serie serait detectable.

Bonus : performance vs cloture des joueurs steamed 2 fois de suite (residu),
si resultats disponibles.

Garde-fou n >= MIN_N (30) sequences. Sources : CLV_FILE, RESULTS.
"""
import json, os, sys, statistics as st

CLV_FILE = os.environ.get('CLV_FILE', 'clv_history.jsonl')
RESULTS  = os.environ.get('RESULTS', 'resultats_oddspapi.json')
MIN_N    = int(os.environ.get('MIN_N', '30'))
MOVE_MIN = 3.0


def devig(o_self, o_other):
    try:
        a, b = 1.0 / float(o_self), 1.0 / float(o_other)
        return a / (a + b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def main():
    if not os.path.exists(CLV_FILE):
        print(f"❌ {CLV_FILE} manquant"); sys.exit(0)
    results = {}
    if os.path.exists(RESULTS):
        with open(RESULTS, encoding='utf-8') as f:
            results = json.load(f)

    apps = []   # (player, date, steamed, won, p_close)
    seen = set()
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
            date = str(e.get('commence_time') or '')
            r = results.get(fid) or {}
            hm, am = e.get('home_metrics') or {}, e.get('away_metrics') or {}
            for side, other, ms, mo in (('home', 'away', hm, am), ('away', 'home', am, hm)):
                name = e.get(side)
                mv = ms.get('move_pct')
                if not name or mv is None:
                    continue
                steamed = mv <= -MOVE_MIN
                won = None
                p_close = devig(ms.get('close'), mo.get('close'))
                if r.get('winner') and not r.get('void'):
                    won = 1 if r['winner'] == side else 0
                apps.append((name.strip(), date, steamed, won, p_close))

    by_player = {}
    for name, date, steamed, won, p_close in apps:
        by_player.setdefault(name, []).append((date, steamed, won, p_close))

    base = sum(1 for a in apps if a[2]) / len(apps) if apps else 0
    seqs = []        # transitions (steamed_k, steamed_k+1)
    after2 = []      # (won, p_close) des matchs ou le joueur est steamed 2e fois consecutive
    for name, lst in by_player.items():
        lst.sort(key=lambda x: x[0])
        for (d0, s0, _, _), (d1, s1, w1, p1) in zip(lst, lst[1:]):
            seqs.append((s0, s1))
            if s0 and s1 and w1 is not None and p1 is not None:
                after2.append((w1, p1))

    n_seq = len(seqs)
    n_after_steam = sum(1 for s0, _ in seqs if s0)
    rec = sum(1 for s0, s1 in seqs if s0 and s1) / n_after_steam if n_after_steam else None
    rec_base = sum(1 for s0, s1 in seqs if not s0 and s1) / max(1, n_seq - n_after_steam)

    print(f"=== player_steam — {len(apps)} apparitions, {len(by_player)} joueurs, "
          f"{n_seq} transitions match k->k+1 ===")
    print(f"(exploration pre-enregistree 2026-06-12 — [DIR] = n<{MIN_N})\n")
    print(f"taux de base 'steamed' : {base:.0%} des cotes")
    t = '' if n_after_steam >= MIN_N else ' [DIR]'
    if rec is not None:
        print(f"P(steamed k+1 | steamed k)     = {rec:.0%}  (n={n_after_steam}){t}")
    t2 = '' if (n_seq - n_after_steam) >= MIN_N else ' [DIR]'
    print(f"P(steamed k+1 | NON steamed k) = {rec_base:.0%}  (n={n_seq - n_after_steam}){t2}")
    if after2:
        wr = sum(w for w, _ in after2) / len(after2)
        pc = st.mean(p for _, p in after2)
        t3 = '' if len(after2) >= MIN_N else ' [DIR]'
        print(f"\njoueurs steamed 2 matchs de suite : realise {wr:.0%} vs close {pc:.0%}"
              f" (residu {wr - pc:+.1%}, n={len(after2)}){t3}")
    print("\nLecture : recurrence >> base = l'argent informe SUIT des joueurs ; un residu")
    print("positif sur les doubles-steams dirait que meme la cloture sous-ajuste ces series.")
    print("NB : couverture partielle (seuls NOS matchs suivis comptent comme 'apparitions').")


if __name__ == '__main__':
    main()
