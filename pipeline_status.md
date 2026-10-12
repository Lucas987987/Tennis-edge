# État du dernier run — Steam Pipeline

Run démarré `2026-10-12T06:03:45` · terminé `2026-10-12T06:37:43` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3516 | 349850 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3378 | 907740 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 199 | 110959 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 52 | 22671 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 59 | 9825 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1906 | 325299 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 491 | 79420 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 424 | 208102 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4941 | 51422401 | ✅ OK |


**Closings exploitables** : 90 % sur 3 jours (fenêtre t3 : 77 %, n=164) — référence 30 jours 91 % (t3 84 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 69 fichiers, 496.6 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 10.5 % d'écarts > 3 % (153/1462), seuil 30.0 %
**CLV décomposé** : prime +2.13 % · dérive +2.50 % · part de la sélection 40.4 % (n=1507)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.6h)
🔴 **Taille du dépôt** : 4.91 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
