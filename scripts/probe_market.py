#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_market.py — Sonde la structure d'un marketId précis sur un match réel.

Objectif : trouver les outcomeId exacts du marché 121033 (Both Participants To
Win a Set). C'est un marché OUI/NON, pas Home/Away comme le vainqueur ou les
sets — il faut donc connaître ses vrais outcomeId avant de coder la capture
(deviner risquerait de confondre Oui et Non).

Usage : python scripts/probe_market.py [marketId]   (def 121033)
Coût : 2 requêtes API (fixtures/today + odds/main).
"""
import os, sys
import oddspapi_v5 as ov

MARKET_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 121033


def main():
    items = ov.fixtures_today() or []
    fids = [f.get('fixtureId') or f.get('id') for f in items if isinstance(f, dict)]
    fids = [f for f in fids if f][:5]
    if not fids:
        print("aucun match tennis du jour"); return
    print(f"recherche marketId {MARKET_ID} sur {len(fids)} matchs témoins\n")

    data = ov.odds_main_by_fixtures(fids, "pinnacle,bet365,unibet.fr,winamax.fr")
    fixtures = data if isinstance(data, list) else (data.get('fixtures') or data.get('data') or [])
    found = False
    for fixture in fixtures:
        fid = fixture.get('fixtureId')
        h = ((fixture.get('participants') or {}).get('participant1Name'))
        a = ((fixture.get('participants') or {}).get('participant2Name'))
        odds = fixture.get('odds') or {}
        rows = []
        for bk, entries in odds.items():
            if not isinstance(entries, dict):
                continue
            for _key, v in entries.items():
                if not isinstance(v, dict) or v.get('marketId') != MARKET_ID:
                    continue
                rows.append((bk, v.get('outcomeId'), v.get('bookmakerOutcomeId'),
                            v.get('price'), v.get('active'), v.get('marketActive')))
        if rows:
            found = True
            print(f"=== {fid} : {h} vs {a} ===")
            for bk, oid, blbl, price, act, mact in rows:
                print(f"  {bk:12} outcomeId={oid} bookmakerOutcomeId={blbl!r} "
                      f"price={price} active={act} marketActive={mact}")
            print()

    if not found:
        print(f"❌ marketId {MARKET_ID} non trouvé dans les cotes de ces {len(fids)} matchs.")
        print("   -> soit personne ne le cote sur ces affiches précises, soit il n'est")
        print("   pas exposé sur /fixtures/odds/main du tout. Réessayer sur d'autres")
        print("   matchs (ATP principal, meilleure couverture) si besoin.")


if __name__ == '__main__':
    main()
