# État du dernier run — Steam Pipeline

Run démarré `2026-09-25T05:01:11` · terminé `2026-09-25T05:25:36` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3532 | 351176 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2705 | 731001 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 170 | 95660 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 49 | 26446 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 72 | 12301 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1695 | 290974 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 372 | 59804 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 345 | 163531 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4075 | 50758955 | ✅ OK |


**Closings exploitables** : 97 % sur 3 jours (fenêtre t3 : 86 %, n=175) — référence 30 jours 83 % (t3 65 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 56 fichiers, 771.2 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 11.4 % d'écarts > 3 % (221/1944), seuil 30.0 %
**CLV décomposé** : prime +2.14 % · dérive +2.77 % · part de la sélection 37.8 % (n=1298)
⚠️ **Études Polymarket** : 3 échec(s) (il y a 20.0h)
🔴 **Taille du dépôt** : 5.7 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
