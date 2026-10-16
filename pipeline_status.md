# État du dernier run — Steam Pipeline

Run démarré `2026-10-16T16:07:58` · terminé `2026-10-16T16:43:02` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3708 | 368696 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3571 | 959143 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 208 | 116411 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 58 | 26258 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 64 | 10646 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1970 | 336448 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 543 | 88101 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 465 | 231056 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3763 | 45658725 | ✅ OK |


**Closings exploitables** : 98 % sur 3 jours (fenêtre t3 : 88 %, n=126) — référence 30 jours 92 % (t3 84 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 69 fichiers, 518.1 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 9.3 % d'écarts > 3 % (148/1583), seuil 30.0 %
**CLV décomposé** : prime +2.17 % · dérive +2.45 % · part de la sélection 41.3 % (n=1571)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 7.5h)
🔴 **Taille du dépôt** : 5.27 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — ne PAS réécrire l'historique (force-push interdit). Poursuivre la migration R2 (README_MIGRATION_R2.md) ; « nouveau dépôt propre » à planifier plus tard, à froid.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
