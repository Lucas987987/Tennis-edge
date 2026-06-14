#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_set_results.py — Collecte les resultats de SET (set1/set2) + match.

Ecrit/maj set_results.json : {uid: {"match":"home"/"away", "set1":..., "set2":...}}.
Source : ov.settlement_result(fixture_id) (1 requete /fixtures/settlement par match
fini). Incremental : ne refait pas les matchs deja resolus.

Utilise par paper_journal (MARKET=set1/set2) pour denouer les paris set au bon
resultat. Lit closing_lines.json pour la liste des matchs + fixture_id.

Env : RAPIDAPI_KEY. SET_RESULTS (def set_results.json),
      RESULTS_MAX_PER_RUN (def 80), RESULTS_COOLDOWN (def 2.0).
"""
import os, json, datetime, time
import oddspapi_v5 as ov

CLOSING = 'closing_lines.json'
OUT = os.environ.get('SET_RESULTS', 'set_results.json')
MAX = int(os.environ.get('RESULTS_MAX_PER_RUN', '80'))
COOL = float(os.environ.get('RESULTS_COOLDOWN', '2.0'))


def main():
    if not ov.KEY:
        print("❌ RAPIDAPI_KEY absente"); return
    if not os.path.exists(CLOSING):
        print("Pas de closing_lines.json"); return
    closing = json.load(open(CLOSING, encoding='utf-8'))

    cache = {}
    if os.path.exists(OUT):
        try:
            cache = json.load(open(OUT, encoding='utf-8'))
        except Exception:
            cache = {}

    now = datetime.datetime.utcnow()
    todo = []
    for uid, m in closing.items():
        if uid in cache and cache[uid].get('match'):
            continue  # deja resolu
        fid = m.get('fixture_id') or m.get('id')
        ct = m.get('commence_time', '')
        if not fid or not ct:
            continue
        try:
            start = datetime.datetime.fromisoformat(ct.replace('Z', '+00:00')).replace(tzinfo=None)
        except Exception:
            continue
        if start <= now:
            todo.append((uid, fid))

    todo = todo[:MAX]
    print(f"{len(todo)} matchs a resoudre (cache: {len(cache)})")
    got = 0
    for uid, fid in todo:
        time.sleep(COOL)
        try:
            r = ov.settlement_result(fid)
        except Exception as e:
            print(f"  ⚠️ {fid}: {e}"); continue
        if not r.get('finished'):
            continue
        cache[uid] = {'match': r.get('winner'), 'set1': r.get('set1'), 'set2': r.get('set2')}
        got += 1
    json.dump(cache, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f"✅ {got} resultats ajoutes -> {OUT} ({len(cache)} total)")


if __name__ == '__main__':
    main()
