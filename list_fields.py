#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
list_fields.py — Inspecte la STRUCTURE brute d'une réponse odds de l'API.

Objectif : savoir si l'API expose les LIMITES DE MISE (liquidity / maxStake /
limit). C'est la donnée que certains services affichent en pointillé sur leurs
graphiques : Pinnacle relève ses limites quand il est confiant dans son prix.

Hypothèse à tester si la donnée existe : un mouvement accompagné d'une hausse
de limite serait plus fiable qu'un mouvement à limite basse (simple ajustement
automatique sur faible volume).

Coût : 2 requêtes API. À lancer une fois via le workflow Steam Diag.
"""
import os, json
import oddspapi_v5 as ov

MOTS = ('limit', 'max', 'stake', 'liquid', 'volume', 'amount', 'size', 'matched')


def walk(obj, prefix='', depth=0, seen=None, hits=None):
    """Parcourt le JSON et collecte tous les chemins de champs."""
    if seen is None: seen = set()
    if hits is None: hits = []
    if depth > 6:
        return seen, hits
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            seen.add(path)
            if any(m in k.lower() for m in MOTS):
                hits.append((path, repr(v)[:80]))
            walk(v, path, depth+1, seen, hits)
    elif isinstance(obj, list) and obj:
        walk(obj[0], f"{prefix}[]", depth+1, seen, hits)
    return seen, hits


def main():
    fx, _ = ov.api_get("/fixtures/today", {"sport": "tennis"})
    items = fx if isinstance(fx, list) else (fx.get('fixtures') or fx.get('data') or [])
    fid = None
    for f in items:
        if isinstance(f, dict) and (f.get('id') or f.get('fixtureId')):
            fid = f.get('id') or f.get('fixtureId'); break
    if not fid:
        print("aucun match tennis du jour"); return
    print(f"match témoin : {fid}\n")

    data = ov.odds_main_by_fixtures([fid], "pinnacle,unibet")
    seen, hits = walk(data)

    print(f"=== {len(seen)} chemins de champs trouvés ===")
    print("\n--- champs liés aux LIMITES / LIQUIDITÉ ---")
    if hits:
        for path, val in hits[:30]:
            print(f"  {path:50} = {val}")
    else:
        print("  AUCUN champ limite/liquidité dans la réponse.")
        print("  -> l'API ne semble pas exposer cette donnée sur cet endpoint.")

    print("\n--- structure d'une entrée de cote (pour référence) ---")
    fixtures = data if isinstance(data, list) else (data.get('fixtures') or data.get('data') or [])
    for fixture in fixtures[:1]:
        odds = fixture.get('odds') or {}
        for bk, entries in list(odds.items())[:1]:
            for key, v in list(entries.items())[:2]:
                print(f"  [{bk}] {key} :")
                if isinstance(v, dict):
                    for k2, v2 in v.items():
                        print(f"      {k2:24} = {repr(v2)[:60]}")

    print("\n--- autres endpoints à tester si rien ici ---")
    print("  /fixtures/odds/historical peut contenir des champs supplémentaires")
    hist, st = ov.api_get("/fixtures/odds/historical",
                          {"fixtureId": fid, "bookmaker": "pinnacle"})
    if hist:
        s2, h2 = walk(hist)
        if h2:
            print("  champs limite trouvés dans /historical :")
            for path, val in h2[:15]:
                print(f"    {path:48} = {val}")
        else:
            print("  aucun champ limite dans /historical non plus.")


if __name__ == '__main__':
    main()
