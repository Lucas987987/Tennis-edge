# État du dernier run — Steam Pipeline

Run démarré `2026-10-16T04:34:36` · terminé `2026-10-16T05:07:59` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3691 | 367086 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3555 | 955130 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 208 | 116411 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 58 | 26258 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 59 | 9802 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1970 | 336448 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 542 | 87921 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 463 | 229997 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3632 | 42840669 | ✅ OK |


**Closings exploitables** : 98 % sur 3 jours (fenêtre t3 : 91 %, n=168) — référence 30 jours 92 % (t3 84 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 69 fichiers, 517.0 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 9.5 % d'écarts > 3 % (148/1565), seuil 30.0 %
**CLV décomposé** : prime +2.17 % · dérive +2.45 % · part de la sélection 41.3 % (n=1571)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.8h)
🔴 **Taille du dépôt** : 5.24 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
