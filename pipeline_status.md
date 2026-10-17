# État du dernier run — Steam Pipeline

Run démarré `2026-10-17T04:31:18` · terminé `2026-10-17T05:04:57` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3723 | 370175 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3557 | 955611 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 208 | 116411 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 58 | 26258 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 40 | 6611 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 2089 | 357026 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 543 | 88101 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 465 | 231056 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 2593 | 28552570 | ✅ OK |


**Closings exploitables** : 98 % sur 3 jours (fenêtre t3 : 88 %, n=120) — référence 30 jours 92 % (t3 84 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 70 fichiers, 594.8 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 10.1 % d'écarts > 3 % (159/1577), seuil 30.0 %
**CLV décomposé** : prime +2.07 % · dérive +2.42 % · part de la sélection 40.5 % (n=1690)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.9h)
🔴 **Taille du dépôt** : 5.27 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — ne PAS réécrire l'historique (force-push interdit). Poursuivre la migration R2 (README_MIGRATION_R2.md) ; « nouveau dépôt propre » à planifier plus tard, à froid.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
