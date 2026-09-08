# État du dernier run — Steam Pipeline

Run démarré `2026-09-08T04:31:08` · terminé `2026-09-08T04:47:05` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2735 | 272966 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1814 | 482413 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 40 | 17209 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 38 | 14609 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 52 | 8661 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1201 | 200169 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 194 | 30422 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 200 | 82231 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4342 | 49632357 | ✅ OK |


**Closings exploitables** : 84 % sur 3 jours (fenêtre t3 : 67 %, n=162) — référence 30 jours 83 % (t3 46 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 44 fichiers, 563.3 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 16.1 % d'écarts > 3 % (188/1168), seuil 30.0 %
**CLV décomposé** : prime +1.12 % · dérive +2.86 % · part de la sélection 27.1 % (n=805)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.3h)
🔴 **Taille du dépôt** : 4.02 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
