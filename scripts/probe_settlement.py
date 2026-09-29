#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_settlement.py — SONDE : structure reelle de /fixtures/settlement.

Objectif : comprendre pourquoi set1/set2 (marches 123/125) ne sortent pas.
Affiche pour un fixtureId TERMINE :
  - status + scores bruts
  - la liste COMPLETE des settlements[] (marketId, outcomeId, status, types !)
  - le diagnostic de settlement_result() apres correction str-compare

Usage : FIXTURE_ID=id1200762571900838 python scripts/probe_settlement.py
(defaut : Linette v Pohankova, fini 2-0 aujourd'hui)
"""
import json, os
import oddspapi_v5 as ov

FID = os.environ.get('FIXTURE_ID', 'id1200762571900838')

def main():
    if not ov.KEY:
        print("X RAPIDAPI_KEY absente"); return
    print(f"=== sonde settlement — fixture {FID} ===\n")
    data = ov.settlement(FID)
    if not isinstance(data, dict):
        print(f"reponse inattendue: {type(data)} {str(data)[:300]}"); return

    print("STATUS  :", json.dumps(data.get('status'), ensure_ascii=False))
    print("SCORES  :", json.dumps(data.get('scores'), ensure_ascii=False)[:500])
    setl = data.get('settlements') or []
    print(f"\nSETTLEMENTS ({len(setl)} entrees) :")
    for s in setl[:60]:
        mid, oid = s.get('marketId'), s.get('outcomeId')
        print(f"  marketId={mid!r} ({type(mid).__name__})  outcomeId={oid!r} ({type(oid).__name__})"
              f"  status={s.get('status')!r}  autres_cles={sorted(set(s.keys()) - {'marketId','outcomeId','status'})}")
    if len(setl) > 60:
        print(f"  ... (+{len(setl)-60})")

    # Y a-t-il d'autres cles au niveau racine qu'on ignore ?
    print("\nCLES RACINE :", sorted(data.keys()))

    print("\nsettlement_result() →", ov.settlement_result(FID))

if __name__ == '__main__':
    main()
