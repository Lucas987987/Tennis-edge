# État du dernier run — Steam Pipeline

Run démarré `2026-09-09T04:37:05` · terminé `2026-09-09T04:55:54` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2812 | 280554 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1906 | 506405 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 46 | 20343 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 41 | 20211 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 57 | 9554 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1230 | 205097 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 213 | 33495 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 213 | 90135 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4622 | 56481416 | ✅ OK |


**Closings exploitables** : 83 % sur 3 jours (fenêtre t3 : 67 %, n=208) — référence 30 jours 83 % (t3 48 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 45 fichiers, 656.3 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 16.3 % d'écarts > 3 % (190/1168), seuil 30.0 %
**CLV décomposé** : prime +1.11 % · dérive +2.83 % · part de la sélection 27.4 % (n=834)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 20.0h)
🔴 **Taille du dépôt** : 4.45 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
