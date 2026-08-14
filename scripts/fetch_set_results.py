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



# uid CANONIQUE (identique a build_live_curves) : les cles de closing_lines ont
# change de format au fil du temps ('atp_tournoi_x_vs_y' vs date). On ecrit donc
# TOUJOURS les resultats sous l'uid date derive des champs, pour que courbes /
# journal / audit joignent. (La cle closing brute n'est plus utilisee.)
import re as _re, unicodedata as _ud
def _norm_slug(x):
    x = _ud.normalize('NFD', str(x).lower().strip())
    x = ''.join(c for c in x if not _ud.combining(c))
    return _re.sub(r'[^a-z0-9]+', '_', x).strip('_')
def _canon_uid(m):
    ct, h, a = m.get('commence_time',''), m.get('home',''), m.get('away','')
    if not (ct and h and a): return None
    return f"{ct[:10]}_{_norm_slug(h)}_{_norm_slug(a)}"

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
    for key, m in closing.items():
        uid = _canon_uid(m) or key
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
            todo.append((uid, fid, start))

    # PRIORITÉ AUX MATCHS RÉCENTS : sans tri, l'ordre est celui du dict
    # closing_lines.json (arbitraire). Avec 908 matchs en attente et seulement
    # MAX=80 traités par run, les matchs RÉCENTS (ceux dont canal_public/ROI
    # ont besoin) restaient noyés dans le backlog indéfiniment -- même bug
    # que fetch_book_curves.py, corrigé le 14/08/2026, jamais appliqué ici.
    # Constat : 26/30 alertes récentes du canal AVAIENT leur match dans
    # closing_lines.json (pas de bug d'uid) mais seulement 4/30 résolus.
    todo.sort(key=lambda x: x[2], reverse=True)
    todo = [(uid, fid) for uid, fid, _ in todo[:MAX]]
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
