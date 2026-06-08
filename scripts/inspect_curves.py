#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inspect_curves.py — book_curves.jsonl contient-il des points IN-PLAY ?

Avant de construire la calibration in-play post-set-1, on vérifie si la capture
a gardé les points postérieurs au coup d'envoi (timestamp > commence_time), ou
si elle s'arrête au début du match. Ça décide la suite :
  - in-play présents -> on teste sur les données existantes (détection de pic).
  - absents          -> on patche fetch_book_curves pour les conserver.

USAGE : python scripts/inspect_curves.py [chemin/book_curves.jsonl]
"""
import sys, glob, json, statistics as st
from datetime import datetime


def parse(ts):
    try:
        return datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
    except Exception:
        return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'book_curves.jsonl'
    if not glob.glob(path):
        sys.exit(f"Fichier introuvable : {path}")

    n = with_inplay = 0
    inplay_counts, pre_counts, spans, ex = [], [], [], []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            n += 1
            ct = parse(r.get('commence_time', ''))
            if ct is None:
                continue
            pts = []
            for side in ('home_curve', 'away_curve'):
                for p in (r.get(side) or []):
                    if isinstance(p, (list, tuple)) and p:
                        t = parse(p[0])
                        if t:
                            pts.append(t)
            if not pts:
                continue
            inplay = [t for t in pts if t > ct]
            pre = [t for t in pts if t <= ct]
            pre_counts.append(len(pre))
            if inplay:
                with_inplay += 1
                inplay_counts.append(len(inplay))
                span = (max(inplay) - ct).total_seconds() / 60.0
                spans.append(span)
                if len(ex) < 4:
                    ex.append((r.get('home', '?'), r.get('away', '?'),
                               r.get('book', '?'), len(pre), len(inplay), round(span)))

    print("=" * 66)
    print("INSPECTION book_curves.jsonl — points in-play présents ?")
    print("=" * 66)
    print(f"enregistrements lus              : {n}")
    print(f"avec >=1 point in-play           : {with_inplay} "
          f"({100 * with_inplay / max(1, n):.0f}%)")
    if inplay_counts:
        print(f"points pré-match (médiane)       : {int(st.median(pre_counts)) if pre_counts else 0}")
        print(f"points in-play / match (médiane) : {int(st.median(inplay_counts))} "
              f"(max {max(inplay_counts)})")
        print(f"durée in-play couverte (médiane) : {st.median(spans):.0f} min "
              f"(max {max(spans):.0f} min)")
        print("\nexemples (home, away, book, pré, in-play, span_min) :")
        for e in ex:
            print("  ", e)
        print("\n-> Points in-play PRÉSENTS : on peut tester la calibration "
              "post-set-1 sur les données existantes (détection de pic).")
    else:
        print("\n-> AUCUN point in-play : la capture s'arrête au coup d'envoi.\n"
              "   Il faut patcher fetch_book_curves pour garder les points "
              "postérieurs au commence_time, puis laisser accumuler.")


if __name__ == '__main__':
    main()
