#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alert_continuation.py — Le move continue-t-il APRES le log T-35 ?

PRE-ENREGISTREMENT (2026-06-12) : seuils fixes avant lecture.

odds_movement logge chaque match (une fois) vers T-35 avec l'etat du move a cet
instant (o_*_first -> o_*_last). En croisant avec la cloture finale (clv_history),
on mesure ce qui se passe APRES : continuation, arret, ou retour.

C'est le test direct de "faut-il suivre le steam quand le systeme sonne" :
  - continuation >> retour, et magnitude post significative -> l'alerte arrive
    PENDANT le move (signal d'entree potentiel, a valider sur du frais) ;
  - move quasi fini au log -> l'alerte est un retroviseur (utile pour comprendre,
    pas pour agir).

Unite = un COTE de match dont |move au log| >= MOVE_MIN (3%).
  pre  = o_last - o_first (le move deja fait au moment du log)
  post = close - o_last   (ce qui reste apres le log)
  continuation si post va dans le meme sens que pre (|post| >= NOISE 0.5%) ;
  retour si sens oppose ; stable sinon.

Garde-fou n >= MIN_N (30). Mecanique (pas de resultats requis).
Sources : ALERTS_LOG=odds_alerts_log.jsonl  CLV_FILE=clv_history.jsonl
"""
import json, os, sys, statistics as st

ALERTS_LOG = os.environ.get('ALERTS_LOG', 'odds_alerts_log.jsonl')
CLV_FILE   = os.environ.get('CLV_FILE', 'clv_history.jsonl')
MIN_N      = int(os.environ.get('MIN_N', '30'))
MOVE_MIN   = 3.0    # % de move minimal AU LOG pour analyser le côté
NOISE      = 0.5    # % en-dessous duquel le post-move est "stable"


def load_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def main():
    logs = load_jsonl(ALERTS_LOG)
    clv = {}
    for e in load_jsonl(CLV_FILE):
        uid = e.get('uid')
        if uid:
            clv[uid] = e
    if not logs or not clv:
        print(f"❌ donnees manquantes ({ALERTS_LOG}: {len(logs)} | {CLV_FILE}: {len(clv)})")
        sys.exit(0)

    seen = set()
    rows = []
    for lg in logs:
        uid = lg.get('uid')
        if not uid or uid in seen:
            continue
        seen.add(uid)
        ce = clv.get(uid)
        if not ce:
            continue
        for side in ('home', 'away'):
            first = lg.get(f'o_{side}_first')
            last = lg.get(f'o_{side}_last')
            close = (ce.get(f'{side}_metrics') or {}).get('close')
            if not first or not last or not close:
                continue
            pre_pct = (last - first) / first * 100.0
            if abs(pre_pct) < MOVE_MIN:
                continue
            post_pct = (close - last) / last * 100.0
            if abs(post_pct) < NOISE:
                verdict = 'stable'
            elif post_pct * pre_pct > 0:
                verdict = 'continuation'
            else:
                verdict = 'retour'
            rows.append({'dir': 'steam' if pre_pct < 0 else 'drift',
                         'pre': pre_pct, 'post': post_pct, 'verdict': verdict,
                         'ratio': post_pct / pre_pct})

    n = len(rows)
    print(f"=== alert_continuation — {len(seen)} matchs logges, {n} cotes avec |move|>= {MOVE_MIN:.0f}% au log ===")
    print(f"(exploration pre-enregistree 2026-06-12 — mecanique, [DIR] = n<{MIN_N})\n")
    if not rows:
        print("rien a analyser."); return

    for d in ('steam', 'drift', None):
        g = rows if d is None else [r for r in rows if r['dir'] == d]
        lab = d or 'TOUS'
        if not g:
            continue
        nn = len(g)
        cont = sum(1 for r in g if r['verdict'] == 'continuation')
        ret = sum(1 for r in g if r['verdict'] == 'retour')
        stab = nn - cont - ret
        med_ratio = st.median(r['ratio'] for r in g)
        med_post = st.median(abs(r['post']) for r in g)
        tag = '' if nn >= MIN_N else ' [DIR]'
        print(f"{lab:<6} n={nn:<4} continuation {cont/nn:.0%} | stable {stab/nn:.0%} | retour {ret/nn:.0%}"
              f" | post median {med_post:.1f}% | post/pre median {med_ratio:+.0%}{tag}")

    print("\nLecture :")
    print(" - post/pre ~ 0 et stable majoritaire = le move est FINI quand le log tombe (T-35) :")
    print("   l'alerte decrit le passe, elle ne precede rien.")
    print(" - continuation >> retour avec post median consequent = l'info arrive encore apres")
    print("   T-35 -> seul cas qui justifierait (un jour, sur du frais) d'en faire un declencheur.")


if __name__ == '__main__':
    main()
