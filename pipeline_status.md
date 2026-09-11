# État du dernier run — Steam Pipeline

Run démarré `2026-09-11T04:33:49` · terminé `2026-09-11T04:56:12` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2875 | 286684 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2011 | 534421 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 68 | 32539 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 41 | 20247 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 46 | 7677 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1297 | 216504 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 225 | 35442 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 223 | 95752 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 2856 | 34479197 | ✅ OK |


**Closings exploitables** : 87 % sur 3 jours (fenêtre t3 : 79 %, n=135) — référence 30 jours 83 % (t3 49 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 46 fichiers, 557.4 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 16.5 % d'écarts > 3 % (199/1207), seuil 30.0 %
**CLV décomposé** : prime +1.98 % · dérive +2.78 % · part de la sélection 37.8 % (n=901)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.9h)
🔴 **Taille du dépôt** : 5.04 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
