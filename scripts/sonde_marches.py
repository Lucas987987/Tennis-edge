#!/usr/bin/env python3
"""sonde_marches.py — 2 requêtes au plus : quels marchés OddsPapi cote-t-il sur un match ?

    python scripts/sonde_marches.py [jour AAAA-MM-JJ] [book]

1. Historique d'UN match terminé ce jour-là (défaut : avant-hier, Pinnacle) :
   liste chaque marché (marketId), son nombre d'issues, de points, et les champs
   d'un point (pour voir si une « ligne » — 22,5 jeux, −3,5 — est fournie).
2. Table des marchés de l'API (/markets), si elle est servie, pour mettre un
   nom sur chaque identifiant. Échec toléré.
Objectif (21/10/2026) : savoir si l'API sert le total de jeux, le handicap de
jeux et le score exact en sets, avant de dépenser des requêtes à les collecter.
Écrit sonde_marches.json.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov  # noqa: E402
import closing_store  # noqa: E402

CONNUS = {ov.MW_MARKET: 'vainqueur du match', ov.SET1_MARKET: 'vainqueur set 1', ov.SET2_MARKET: 'vainqueur set 2'}


def main():
    jour = sys.argv[1] if len(sys.argv) > 1 else (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
    book = sys.argv[2] if len(sys.argv) > 2 else 'pinnacle'
    closing = closing_store.load_all('closing_lines.json', max_age_days=None)
    cands = [(m.get('commence_time', ''), m) for m in closing.values()
             if str(m.get('commence_time', '')).startswith(jour) and (m.get('fixture_id') or m.get('id'))
             and 'challenger' not in str(m.get('tournament', '')).lower()]
    if not cands:
        print(f"❌ aucun match du {jour} dans closing_lines")
        return 1
    ct, m = sorted(cands, key=lambda x: x[0])[len(cands) // 2]
    fid = m.get('fixture_id') or m.get('id')
    print(f"Match : {m.get('home')} – {m.get('away')} · {m.get('tournament')} · {ct} · fixture {fid} · {book}")

    data = ov.historical(fid, book)                                     # requête 1
    series = ((data or {}).get('odds') or {}).get(book) or {}
    marches = {}
    for oid, serie in series.items():
        if not isinstance(serie, dict) or not serie:
            continue
        pt = next(iter(serie.values()), {}) or {}
        mid = pt.get('marketId')
        d = marches.setdefault(str(mid), {'issues': 0, 'points': 0, 'exemple': None, 'issues_ids': []})
        d['issues'] += 1
        d['points'] += len(serie)
        d['issues_ids'].append(pt.get('outcomeId'))
        if d['exemple'] is None:
            d['exemple'] = {k: v for k, v in pt.items() if k not in ('limit',)}

    noms = {}
    try:
        tab, _ = ov.api_get('/markets', {'sportId': ov.TENNIS_SPORT_ID})   # requête 2
        items = tab if isinstance(tab, list) else (tab or {}).get('markets', []) or []
        for x in items:
            if isinstance(x, dict) and x.get('marketId') is not None:
                noms[str(x['marketId'])] = {k: x.get(k) for k in ('marketName', 'marketNameShort', 'handicap', 'period', 'outcomes') if k in x}
        print(f"Table des marchés : {len(noms)} entrées")
    except Exception as e:
        print(f"Table des marchés non servie ({type(e).__name__}: {e})")

    print(f"\n{len(marches)} marchés cotés par {book} sur ce match :")
    for mid, d in sorted(marches.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 0):
        nom = CONNUS.get(int(mid) if mid.isdigit() else mid) or (noms.get(mid) or {}).get('marketName') or '?'
        print(f"  {mid:>6} · {nom[:45]:45s} · {d['issues']:2d} issues · {d['points']:5d} points · exemple {json.dumps(d['exemple'], ensure_ascii=False)[:160]}")
    q = ov.QUOTA
    print(f"\nRequêtes réseau envoyées : {ov.REQUETES_RESEAU} · quota restant : {q.get('remaining')} / {q.get('limit')}")
    with open('sonde_marches.json', 'w', encoding='utf-8') as f:
        json.dump({'jour': jour, 'book': book, 'fixture': fid, 'match': f"{m.get('home')} – {m.get('away')}",
                   'marches': marches, 'noms': {k: v for k, v in noms.items() if k in marches}}, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
