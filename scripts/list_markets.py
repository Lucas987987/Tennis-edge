#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
list_markets.py — Découvre les marchés tennis disponibles et leurs marketId.

À lancer UNE FOIS (workflow Steam Diag) pour identifier l'identifiant du marché
« nombre de sets / gagne au moins un set » (handicap ou total de sets), afin de
pouvoir le capturer comme on capture déjà 121 (vainqueur), 123 (set 1), 125 (set 2).

Deux sources :
  1. /markets — le catalogue complet (id + libellé).
  2. un match tennis réel — les marketId réellement cotés sur ce match, ce qui est
     l'information décisive (le catalogue liste beaucoup de marchés non couverts).

Coût : 2-3 requêtes API.
"""
import os, json
import oddspapi_v5 as ov

MOTS = ('set', 'sets', 'handicap', 'total', 'games', 'jeux')


def catalogue():
    # l'API exige exactement un filtre : sportId (tennis = 12)
    data, st = ov.api_get("/markets", {"sportId": ov.TENNIS_SPORT_ID})
    if not data:
        print("❌ /markets ne répond pas"); return {}
    items = data if isinstance(data, list) else (data.get('markets') or data.get('data') or [])
    out = {}
    for m in items:
        if not isinstance(m, dict):
            continue
        mid = m.get('id') or m.get('marketId')
        name = m.get('name') or m.get('title') or m.get('market') or ''
        if mid is None:
            continue
        out[str(mid)] = str(name)
    print(f"=== /markets : {len(out)} marchés au catalogue ===")
    inter = {k: v for k, v in out.items() if any(w in v.lower() for w in MOTS)}
    for k, v in sorted(inter.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
        print(f"  marketId {k:>5}  {v}")
    if not inter:
        print("  (aucun libellé contenant set/handicap/total — voir la liste brute ci-dessous)")
        for k, v in list(sorted(out.items()))[:60]:
            print(f"  {k:>5}  {v}")
    return out


def sur_un_match(cat):
    """Marchés réellement cotés sur un match tennis à venir : la vraie référence."""
    items = ov.fixtures_today() or []
    fid = None
    for f in items:
        if isinstance(f, dict):
            fid = f.get('fixtureId') or f.get('id')
            if fid: break
    if not fid:
        print("\n(aucun match tennis du jour pour l'échantillon)"); return
    data = ov.odds_main_by_fixtures([fid], "pinnacle,bet365,unibet.fr,winamax.fr")
    fixtures = data if isinstance(data, list) else (data.get('fixtures') or data.get('data') or [])
    seen = {}
    for fixture in fixtures:
        for bk in (fixture.get('bookmakers') or []):
            bname = bk.get('key') or bk.get('name') or '?'
            for v in (bk.get('odds') or bk.get('values') or []):
                mid = str(v.get('marketId'))
                seen.setdefault(mid, set()).add(bname)
    print(f"\n=== Marchés réellement cotés sur le match {fid} ===")
    for mid, books in sorted(seen.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
        label = cat.get(mid, '?')
        flag = "  ← déjà capturé" if mid in ('121', '123', '125') else ""
        print(f"  marketId {mid:>5}  {label:<40} [{', '.join(sorted(books))}]{flag}")
    print("\nCherche ci-dessus un marché de type « total sets » / « handicap sets » : "
          "c'est celui qui permet de suivre « gagne au moins un set ».")


if __name__ == '__main__':
    cat = catalogue()
    try:
        sur_un_match(cat)
    except Exception as e:
        print(f"(échantillon match indisponible : {e})")
