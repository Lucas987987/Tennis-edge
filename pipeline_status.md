# État du dernier run — Steam Pipeline

Run démarré `2026-09-22T22:03:32` · terminé `2026-09-22T22:27:23` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3436 | 341797 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2581 | 696515 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 158 | 88249 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 49 | 26446 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 79 | 13534 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1607 | 275743 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 357 | 57304 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 322 | 151288 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4806 | 52133281 | ✅ OK |


**Closings exploitables** : 92 % sur 3 jours (fenêtre t3 : 82 %, n=173) — référence 30 jours 84 % (t3 60 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 55 fichiers, 755.2 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 12.6 % d'écarts > 3 % (231/1835), seuil 30.0 %
**CLV décomposé** : prime +2.08 % · dérive +2.81 % · part de la sélection 37.2 % (n=1210)
⚠️ **Études Polymarket** : 3 échec(s) (il y a 13.1h)
🔴 **Taille du dépôt** : 4.45 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
