# État du dernier run — Steam Pipeline

Run démarré `2026-09-06T12:10:22` · terminé `2026-09-06T12:23:51` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2623 | 261882 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1763 | 467731 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 38 | 16323 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 17 | 7070 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 37 | 6303 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1142 | 190049 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 169 | 26182 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 181 | 71149 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 2761 | 19379732 | ✅ OK |


**Closings exploitables** : 50 % sur 7 jours (fenêtre t3 : 36 %, n=255) — référence 30 jours 83 % (t3 44 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 41 fichiers, 442.6 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 16.0 % d'écarts > 3 % (181/1129), seuil 30.0 %
**CLV décomposé** : prime +1.21 % · dérive +3.63 % · part de la sélection 23.0 % (n=713)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 3.6h)
🔴 **Taille du dépôt** : 4.16 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
