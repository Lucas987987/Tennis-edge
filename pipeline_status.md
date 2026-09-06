# État du dernier run — Steam Pipeline

Run démarré `2026-09-06T12:40:08` · terminé `2026-09-06T12:57:02` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2624 | 261975 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1776 | 471074 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 38 | 16323 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 17 | 7070 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 37 | 6303 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1142 | 190049 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 169 | 26182 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 181 | 71149 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 2836 | 19694009 | ✅ OK |


**Closings exploitables** : 93 % sur 3 jours (fenêtre t3 : 65 %, n=136) — référence 30 jours 83 % (t3 44 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 41 fichiers, 444.7 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 16.0 % d'écarts > 3 % (181/1129), seuil 30.0 %
**CLV décomposé** : prime +1.17 % · dérive +2.87 % · part de la sélection 28.2 % (n=746)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 4.2h)
🔴 **Taille du dépôt** : 4.16 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
