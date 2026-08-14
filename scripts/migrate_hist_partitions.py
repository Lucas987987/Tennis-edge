#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_hist_partitions.py — Migration UNE FOIS des fichiers historiques
monolithiques (book_curves.jsonl, set1_curves.jsonl, set2_curves.jsonl) vers
des partitions mensuelles (parts/hist_<market>_<YYYY-MM>.jsonl).

CONTEXTE (14/08/2026) : book_curves.jsonl a atteint 140,73 Mo après un run
normal -- GitHub rejette tout push > 100 Mo ("pre-receive hook declined").
Le pipeline tournait "sans erreur" chaque nuit (le commit se créait bien en
LOCAL) mais le push échouait silencieusement (`git push || true`), gelant le
fichier distant depuis plusieurs jours sans qu'aucune alerte ne se déclenche.

Ce script répartit chaque ligne dans la partition de son MOIS (déterminé par
son commence_time), puis supprime les fichiers monolithiques d'origine.
Idempotent : si un fichier monolithique n'existe plus (déjà migré), il est
simplement ignoré.
"""
import os, json, datetime

MARKETS = {
    'book': 'book_curves.jsonl',
    'set1': 'set1_curves.jsonl',
    'set2': 'set2_curves.jsonl',
}


def month_of(commence_time):
    try:
        dt = datetime.datetime.fromisoformat(str(commence_time).replace('Z', '').replace('+00:00', ''))
        return dt.strftime('%Y-%m')
    except Exception:
        return 'inconnu'


def migrate_one(market, legacy_path):
    if not os.path.exists(legacy_path):
        print(f"  [{market}] {legacy_path} absent -- déjà migré ou jamais créé, rien à faire.")
        return
    os.makedirs('parts', exist_ok=True)
    buckets = {}   # 'YYYY-MM' -> liste de lignes
    n_total, n_bad = 0, 0
    with open(legacy_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n_total += 1
            try:
                d = json.loads(line)
            except Exception:
                n_bad += 1
                continue
            ym = month_of(d.get('commence_time'))
            buckets.setdefault(ym, []).append(line)

    for ym, lines in sorted(buckets.items()):
        out_path = f'parts/hist_{market}_{ym}.jsonl'
        # APPEND (pas overwrite) : si une partition existe déjà partiellement
        # (ex. re-run après un premier passage partiel), on ne perd rien.
        with open(out_path, 'a', encoding='utf-8') as out:
            for line in lines:
                out.write(line + '\n')
        print(f"  [{market}] {ym} : {len(lines)} lignes -> {out_path}")

    size_before = os.path.getsize(legacy_path) / 1e6
    os.remove(legacy_path)
    print(f"  [{market}] {legacy_path} supprimé ({size_before:.1f} Mo libérés, "
          f"{n_total} lignes migrées vers {len(buckets)} partition(s), {n_bad} ligne(s) illisible(s) ignorée(s))")


def main():
    print("=== Migration historique -> partitions mensuelles ===\n")
    for market, legacy_path in MARKETS.items():
        migrate_one(market, legacy_path)
    print("\n✅ Migration terminée. Chaque partition devrait rester largement sous 100 Mo ;")
    print("   si une partition mensuelle approche elle-même la limite (mois très chargé),")
    print("   il faudra affiner le découpage (ex. par semaine) -- vérifier périodiquement.")


if __name__ == '__main__':
    main()
