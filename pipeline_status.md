# État du dernier run — Steam Pipeline

Run démarré `2026-09-27T05:22:04` · terminé `2026-09-27T05:43:42` (UTC)

**Verdict : 2 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3597 | 357574 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2780 | 751449 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 172 | 97106 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 49 | 26446 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 31 | 5298 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1011 | 174101 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 382 | 61516 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 351 | 166593 | ⏳ FIGÉ |
| Courbes live reconstruites | `book_curves_live.jsonl` | 2252 | 27977371 | ✅ OK |


**Closings exploitables** : 99 % sur 3 jours (fenêtre t3 : 93 %, n=100) — référence 30 jours 82 % (t3 71 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 41 fichiers, 547.6 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 9.4 % d'écarts > 3 % (184/1950), seuil 30.0 %
**CLV décomposé** : prime +2.41 % · dérive +2.70 % · part de la sélection 40.3 % (n=911)
⚠️ **Études Polymarket** : 3 échec(s) (il y a 20.3h)
🔴 **Taille du dépôt** : 6.39 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
