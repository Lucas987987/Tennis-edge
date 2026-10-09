# État du dernier run — Steam Pipeline

Run démarré `2026-10-09T06:12:32` · terminé `2026-10-09T06:43:03` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3360 | 334483 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3202 | 857440 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 188 | 105512 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 51 | 22381 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 33 | 5635 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1839 | 314048 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 475 | 76889 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 411 | 201156 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4364 | 47026160 | ✅ OK |


**Closings exploitables** : 97 % sur 3 jours (fenêtre t3 : 87 %, n=151) — référence 30 jours 92 % (t3 86 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 65 fichiers, 518.1 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 14.2 % d'écarts > 3 % (131/921), seuil 30.0 %
**CLV décomposé** : prime +2.17 % · dérive +2.61 % · part de la sélection 39.9 % (n=1440)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.2h)
🔴 **Taille du dépôt** : 4.65 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
