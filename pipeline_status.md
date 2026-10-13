# État du dernier run — Steam Pipeline

Run démarré `2026-10-13T06:50:04` · terminé `2026-10-13T07:24:22` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3585 | 356625 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3463 | 930515 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 204 | 114135 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 54 | 23990 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 75 | 12420 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1936 | 330452 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 519 | 84074 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 442 | 218655 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 5415 | 63323293 | ✅ OK |


**Closings exploitables** : 85 % sur 3 jours (fenêtre t3 : 75 %, n=192) — référence 30 jours 90 % (t3 83 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 69 fichiers, 546.5 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 10.3 % d'écarts > 3 % (153/1487), seuil 30.0 %
**CLV décomposé** : prime +2.14 % · dérive +2.48 % · part de la sélection 40.6 % (n=1537)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.1h)
🔴 **Taille du dépôt** : 5.02 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
