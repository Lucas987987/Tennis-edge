#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_qualifs.py — Vérifie si l'API distingue les tableaux de QUALIFICATIONS
du tableau principal, et localise les marchés SECONDAIRES disponibles.

Deux questions :
1. Un tournoi de qualifs a-t-il un tournamentId séparé, ou un champ dédié
   (categoryName, stage...) qui permet de les filtrer ? Sans ça, impossible
   de les étudier séparément du tableau principal.
2. Quels marchés secondaires (au-delà de Winner/Set1/Set2) sont RÉELLEMENT
   cotés sur un match tennis type -- total games, handicap games, player
   props -- pour préparer leur capture éventuelle.

Coût : 3-4 requêtes API.
"""
import os, re
import oddspapi_v5 as ov

QUAL_HINTS = ('qual', 'quali', 'q-')


def check_tournaments():
    trs = ov.get_tournaments()
    print(f"=== {len(trs)} tournois au catalogue ATP/WTA ===")
    quals = [t for t in trs if isinstance(t, dict) and
             any(h in str(t.get('name') or t.get('tournamentName') or '').lower() for h in QUAL_HINTS)]
    print(f"Tournois dont le NOM contient 'qual' : {len(quals)}")
    for t in quals[:10]:
        print(f"  {t}")
    if not quals:
        print("  Aucun -> les quals ne sont probablement PAS un tournoi séparé,")
        print("  elles font partie du même tournamentId que le tableau principal.")
    print("\n--- structure d'une entrée tournoi (pour voir les champs dispo) ---")
    if trs:
        for k, v in list(trs[0].items())[:15]:
            print(f"  {k:20} = {repr(v)[:60]}")


def check_fixture_stage():
    """Un fixture individuel a-t-il un champ indiquant qualif/main draw/round ?"""
    items = ov.fixtures_today() or []
    print(f"\n=== {len(items)} matchs tennis aujourd'hui : cherche un champ 'stage'/'round' ===")
    stage_fields = set()
    for f in items[:50]:
        if not isinstance(f, dict): continue
        for k in f.keys():
            if any(w in k.lower() for w in ('stage', 'round', 'qual', 'draw', 'phase')):
                stage_fields.add(k)
    if stage_fields:
        print(f"  champs candidats trouvés : {stage_fields}")
        for f in items[:5]:
            for k in stage_fields:
                if k in f: print(f"    {f.get('fixtureId')}: {k} = {f[k]}")
    else:
        print("  Aucun champ round/stage/qual trouvé sur /fixtures/today.")
        print("  Toutes les clés disponibles sur un fixture :")
        if items:
            print(f"    {sorted(items[0].keys())}")


def check_secondary_markets():
    """Marchés réellement cotés sur un match, au-delà de Winner/Set1/Set2."""
    items = ov.fixtures_today() or []
    fids = [f.get('fixtureId') or f.get('id') for f in items if isinstance(f, dict)][:3]
    fids = [f for f in fids if f]
    if not fids:
        print("\n(aucun match pour tester les marchés secondaires)"); return
    print(f"\n=== Marchés cotés sur {len(fids)} matchs témoins (hors 121/123/125) ===")
    data = ov.odds_main_by_fixtures(fids, "pinnacle,bet365,unibet.fr,winamax.fr")
    fixtures = data if isinstance(data, list) else (data.get('fixtures') or data.get('data') or [])
    seen = {}
    KNOWN = {121, 123, 125}
    for fixture in fixtures:
        odds = fixture.get('odds') or {}
        for bk, entries in odds.items():
            if not isinstance(entries, dict): continue
            for _k, v in entries.items():
                if not isinstance(v, dict): continue
                mid = v.get('marketId')
                if mid in KNOWN: continue
                seen.setdefault(mid, set()).add(bk)
    for mid, books in sorted(seen.items(), key=lambda x: -len(x[1]))[:20]:
        print(f"  marketId {mid} : coté par {len(books)} book(s) -> {sorted(books)}")


if __name__ == '__main__':
    check_tournaments()
    check_fixture_stage()
    check_secondary_markets()
