#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inspect_set2.py — valide le champ set2_open ajouté à book_curves.jsonl.

Pour les enregistrements récents (qui ont set2_open), vérifie :
  - que set1_end est renseigné (les marchés de set 2 ont bien été vus) ;
  - que le décalage set1_end - commence est PLAUSIBLE pour une fin de set 1
    (~30-70 min) ;
  - que les deux marqueurs 12542 et 12624 COÏNCIDENT (auto-contrôle de
    l'identification) — un gros désaccord = identification à revoir.

USAGE : python scripts/inspect_set2.py [book_curves.jsonl]
"""
import sys, glob, json, statistics as st
from datetime import datetime, timezone


def parse(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
        return d.astimezone(timezone.utc).replace(tzinfo=None) if d.tzinfo else d
    except Exception:
        return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'book_curves.jsonl'
    if not glob.glob(path):
        sys.exit(f"Introuvable : {path}")

    n = with_field = with_end = 0
    offsets, disagree, ex = [], [], []
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
            s2 = r.get('set2_open')
            if not isinstance(s2, dict):
                continue
            with_field += 1
            ct = parse(r.get('commence_time'))
            end = parse(s2.get('set1_end'))
            m1, m2 = parse(s2.get('12542')), parse(s2.get('12624'))
            if end and ct:
                with_end += 1
                off = (end - ct).total_seconds() / 60.0
                offsets.append(off)
                d = abs((m1 - m2).total_seconds() / 60.0) if (m1 and m2) else None
                if d is not None:
                    disagree.append(d)
                if len(ex) < 6:
                    ex.append((r.get('book', '?'), r.get('home', '?')[:14], r.get('away', '?')[:14],
                               round(off), round(d, 1) if d is not None else '—'))

    print("=" * 70)
    print("INSPECTION set2_open — timing fin de set 1 & accord des marqueurs")
    print("=" * 70)
    print(f"enregistrements lus            : {n}")
    print(f"avec champ set2_open           : {with_field}")
    print(f"avec set1_end renseigné        : {with_end}")
    if offsets:
        plausibles = sum(1 for o in offsets if 25 <= o <= 75)
        print(f"décalage set1_end - commence   : médiane {st.median(offsets):.0f} min "
              f"(min {min(offsets):.0f}, max {max(offsets):.0f})")
        print(f"  dans la fenêtre plausible 25-75 min : {plausibles}/{len(offsets)} "
              f"({100*plausibles/len(offsets):.0f}%)")
        if disagree:
            within2 = sum(1 for d in disagree if d <= 2)
            print(f"accord 12542 vs 12624 (|écart|): médiane {st.median(disagree):.1f} min "
                  f"| ≤2 min : {within2}/{len(disagree)} ({100*within2/len(disagree):.0f}%)")
        print("\nexemples (book, home, away, offset_min, |12542-12624|_min) :")
        for e in ex:
            print("  ", e)
        # verdict
        med_off = st.median(offsets)
        med_dis = st.median(disagree) if disagree else None
        ok_off = 25 <= med_off <= 75
        ok_dis = (med_dis is not None and med_dis <= 3)
        print()
        if ok_off and ok_dis:
            print("-> OK : timing plausible ET marqueurs concordants. "
                  "L'identification tient -> on peut basculer inplay_setone sur le timing exact.")
        elif ok_off and not ok_dis:
            print("-> Timing plausible mais 12542/12624 divergent : garder un seul marqueur "
                  "(le plus stable) ; identification à affiner.")
        else:
            print("-> Offsets hors fenêtre attendue : l'un des IDs n'est probablement PAS le set 2. "
                  "On relancera l'identificateur avec plus de volume.")
    else:
        print("\n-> Aucun set1_end renseigné : soit les captures sont antérieures au patch, "
              "soit le book n'expose pas 12542/12624. Relance fetch_book_curves.")


if __name__ == '__main__':
    main()
