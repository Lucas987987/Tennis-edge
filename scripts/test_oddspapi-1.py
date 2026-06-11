#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEST v5 : smoke test de la chaîne (sports/fixtures/odds/historical) sur quelques
matchs tennis du jour. Confirme que la clé RapidAPI et les endpoints répondent."""
import os, sys
import oddspapi_v5 as ov


def test():
    if not ov.KEY:
        sys.exit("RAPIDAPI_KEY manquant.")
    fx = [f for f in ov.fixtures_today() if not ov.is_srl(f)]
    print(f"{len(fx)} fixtures tennis (hors SRL) aujourd'hui\n")
    n = 0
    for f in fx:
        if n >= 4:
            break
        fid = f.get('fixtureId')
        pr = f.get('participants', {})
        nm = f"{pr.get('participant1Name')} vs {pr.get('participant2Name')}"
        print(f"--- {nm} | {fid} ---")
        c = ov.historical_h2h_curve(fid, 'pinnacle')
        if not c['home']:
            print("  (pas d'historique pinnacle)\n"); continue
        h, a = c['home'], c['away']
        print(f"  ✅ home {len(h)} pts : ouv {h[0][1]} → clo {h[-1][1]}")
        if a:
            print(f"     away {len(a)} pts : ouv {a[0][1]} → clo {a[-1][1]}")
        print()
        n += 1
    print("Fin des essais.")


if __name__ == '__main__':
    test()
