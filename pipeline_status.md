# État du dernier run — Steam Pipeline

Run démarré `2026-09-24T08:29:22` · terminé `2026-09-24T08:51:53` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3500 | 348034 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2706 | 729896 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 169 | 95050 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 49 | 26446 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 89 | 15253 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1665 | 285927 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 370 | 59468 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 339 | 160245 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4486 | 59773050 | ✅ OK |


**Closings exploitables** : 95 % sur 3 jours (fenêtre t3 : 84 %, n=189) — référence 30 jours 84 % (t3 61 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 56 fichiers, 840.6 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 11.9 % d'écarts > 3 % (228/1916), seuil 30.0 %
**CLV décomposé** : prime +2.13 % · dérive +2.79 % · part de la sélection 37.4 % (n=1268)
⚠️ **Études Polymarket** : 3 échec(s) (il y a 23.5h)
🔴 **Taille du dépôt** : 5.09 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
