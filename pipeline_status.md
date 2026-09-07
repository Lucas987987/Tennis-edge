# État du dernier run — Steam Pipeline

Run démarré `2026-09-07T04:34:30` · terminé `2026-09-07T04:52:31` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2662 | 265773 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1777 | 472213 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 39 | 16665 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 19 | 7726 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 46 | 7723 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1172 | 195239 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 179 | 27929 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 191 | 76659 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3880 | 32960791 | ✅ OK |


**Closings exploitables** : 88 % sur 3 jours (fenêtre t3 : 69 %, n=119) — référence 30 jours 83 % (t3 45 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 44 fichiers, 472.0 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 16.1 % d'écarts > 3 % (188/1168), seuil 30.0 %
**CLV décomposé** : prime +1.17 % · dérive +2.86 % · part de la sélection 28.2 % (n=776)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 20.1h)
🔴 **Taille du dépôt** : 4.16 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
