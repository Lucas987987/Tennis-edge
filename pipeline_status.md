# État du dernier run — Steam Pipeline

Run démarré `2026-10-18T04:35:14` · terminé `2026-10-18T05:13:34` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3735 | 371354 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3552 | 954348 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 208 | 116960 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 58 | 26258 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 34 | 5560 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 2172 | 371424 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 544 | 88248 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 466 | 231566 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3127 | 25762045 | ✅ OK |


**Closings exploitables** : 95 % sur 3 jours (fenêtre t3 : 84 %, n=130) — référence 30 jours 92 % (t3 84 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 70 fichiers, 560.1 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 10.2 % d'écarts > 3 % (165/1612), seuil 30.0 %
**CLV décomposé** : prime +2.04 % · dérive +2.40 % · part de la sélection 40.6 % (n=1774)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 20.5h)
🔴 **Taille du dépôt** : 5.38 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — ne PAS réécrire l'historique (force-push interdit). Poursuivre la migration R2 (README_MIGRATION_R2.md) ; « nouveau dépôt propre » à planifier plus tard, à froid.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
