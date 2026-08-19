#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compress_hist_partitions.py — Compresse les partitions historiques CLOSES.

POURQUOI
parts/ pesait 637 Mo et grossissait d'environ 80 Mo par semaine, sans jamais
être purgé : purge_old_partitions() ne filtre que parts/live_*, et HIST_DAYS=0
par choix délibéré (l'historique EST l'actif de recherche du projet, on ne veut
rien jeter). À ce rythme, le gigaoctet était atteint en cinq semaines, et
chaque exécution de capture_closing — toutes les 5 à 10 minutes — reclone le
dépôt entier.

SOLUTION : gzip, sans aucune perte
Mesuré sur hist_book_2026-W33.jsonl : 97,7 Mo -> 14,1 Mo, soit 14 % de la
taille d'origine. Sur l'ensemble de l'historique : 435 Mo -> environ 63 Mo.
gzip est un algorithme SANS PERTE et l'intégrité est revérifiée ici après
chaque compression (relecture ligne à ligne + comparaison octet pour octet)
AVANT toute suppression de l'original.

La lecture est transparente : ov.iter_hist_lines() lit indifféremment .jsonl et
.jsonl.gz, donc AUCUN script consommateur n'a besoin d'être modifié.

SÉCURITÉ
  • seules les partitions CLOSES sont compressées — jamais celle en cours
    d'écriture (ov.current_hist_partition_path), jamais les partitions live ;
  • l'original n'est supprimé qu'après vérification d'intégrité réussie ;
  • idempotent : une partition déjà compressée est ignorée ;
  • DRY_RUN=1 pour voir ce qui serait fait sans rien modifier.

Env : MIN_MB (5 = ne compresse pas les miettes), DRY_RUN, MARKETS (book,set1,set2).
"""
import os, sys, glob, gzip, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov

MIN_MB  = float(os.environ.get('MIN_MB', '5'))
DRY     = os.environ.get('DRY_RUN', '0') == '1'
MARKETS = [m.strip() for m in os.environ.get('MARKETS', 'book,set1,set2').split(',') if m.strip()]
# Partitions supplémentaires, hors marchés historiques : ticks Polymarket
# (parts/pm_ticks_<date>.jsonl, une par jour). Même traitement, mêmes garde-fous :
# jamais la partition du jour, suppression de l'original après vérification.
EXTRA_GLOBS = [g.strip() for g in os.environ.get(
    'EXTRA_GLOBS', 'parts/pm_ticks_*.jsonl').split(',') if g.strip()]


def verifie(src, dst):
    """Relit les deux fichiers ligne à ligne : contenu strictement identique ?"""
    try:
        with open(src, 'rb') as a, gzip.open(dst, 'rb') as b:
            while True:
                la, lb = a.readline(), b.readline()
                if la != lb:
                    return False
                if not la:
                    return True
    except Exception as e:
        print(f"    ⚠️ vérification impossible : {e}")
        return False


def main():
    # Partitions en cours d'écriture : à ne JAMAIS toucher.
    actives = set()
    for m in MARKETS:
        try:
            actives.add(os.path.abspath(ov.current_hist_partition_path(m)))
        except Exception:
            pass

    # La partition Polymarket du JOUR est encore en écriture : à ne pas toucher.
    import datetime as _dt
    aujourdhui = _dt.datetime.utcnow().strftime('%Y-%m-%d')
    for g in EXTRA_GLOBS:
        for p in glob.glob(g):
            if aujourdhui in os.path.basename(p):
                actives.add(os.path.abspath(p))

    total_avant = total_apres = 0
    n_comp = n_skip = n_fail = 0

    cibles = [f'parts/hist_{m}_*.jsonl' for m in MARKETS] + EXTRA_GLOBS
    for motif in cibles:
        for p in sorted(glob.glob(motif)):
            ap = os.path.abspath(p)
            mo = os.path.getsize(p) / 1e6
            if ap in actives:
                print(f"  ⏭️  {p} — partition COURANTE, laissée en clair")
                n_skip += 1; continue
            if os.path.exists(p + '.gz'):
                print(f"  ⏭️  {p} — .gz déjà présent")
                n_skip += 1; continue
            if mo < MIN_MB:
                print(f"  ⏭️  {p} — {mo:.1f} Mo < {MIN_MB} Mo")
                n_skip += 1; continue

            if DRY:
                print(f"  [DRY] {p} ({mo:.1f} Mo) serait compressé")
                n_comp += 1; continue

            tmp = p + '.gz.tmp'
            try:
                with open(p, 'rb') as fi, gzip.open(tmp, 'wb', compresslevel=6) as fo:
                    shutil.copyfileobj(fi, fo, length=1024 * 1024)
            except Exception as e:
                print(f"  ❌ {p} — compression échouée : {e}")
                if os.path.exists(tmp):
                    os.remove(tmp)
                n_fail += 1; continue

            os.replace(tmp, p + '.gz')
            if not verifie(p, p + '.gz'):
                print(f"  ❌ {p} — INTÉGRITÉ KO, original CONSERVÉ, .gz supprimé")
                os.remove(p + '.gz')
                n_fail += 1; continue

            apres = os.path.getsize(p + '.gz') / 1e6
            os.remove(p)                       # supprimé SEULEMENT après vérification
            total_avant += mo; total_apres += apres; n_comp += 1
            print(f"  ✅ {p} : {mo:.1f} -> {apres:.1f} Mo ({apres/mo*100:.0f}%)")

    print()
    print(f"{n_comp} compressée(s) · {n_skip} ignorée(s) · {n_fail} échec(s)")
    if total_avant:
        print(f"{total_avant:.1f} Mo -> {total_apres:.1f} Mo "
              f"(gain {total_avant - total_apres:.1f} Mo)")
    reste = sum(os.path.getsize(f) for f in glob.glob('parts/*')) / 1e6
    print(f"parts/ pèse désormais {reste:.1f} Mo")
    if n_fail:
        raise SystemExit(f"❌ {n_fail} échec(s) — originaux conservés, rien n'est perdu.")


if __name__ == '__main__':
    main()
