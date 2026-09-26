# État du dernier run — Steam Pipeline

Run démarré `2026-09-26T05:03:04` · terminé `2026-09-26T05:25:24` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3575 | 355399 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2745 | 741969 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 172 | 96624 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 49 | 26446 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 64 | 10749 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 987 | 169988 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 379 | 61026 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 351 | 166593 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 2709 | 39116632 | ✅ OK |


**Closings exploitables** : 99 % sur 3 jours (fenêtre t3 : 92 %, n=116) — référence 30 jours 82 % (t3 69 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 41 fichiers, 635.8 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 9.5 % d'écarts > 3 % (185/1954), seuil 30.0 %
**CLV décomposé** : prime +2.41 % · dérive +2.74 % · part de la sélection 40.0 % (n=888)
⚠️ **Études Polymarket** : 3 échec(s) (il y a 19.7h)
🔴 **Taille du dépôt** : 6.11 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
