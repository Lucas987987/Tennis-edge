# État du dernier run — Steam Pipeline

Run démarré `2026-10-22T04:54:37` · terminé `2026-10-22T05:33:19` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3855 | 383193 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3568 | 959887 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 215 | 119353 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 58 | 28143 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 65 | 10803 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 2463 | 419735 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 586 | 95297 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 495 | 248071 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 5354 | 69768626 | ✅ OK |


**Closings exploitables** : 93 % sur 3 jours (fenêtre t3 : 63 %, n=210) — référence 30 jours 92 % (t3 80 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 75 fichiers, 667.0 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 10.5 % d'écarts > 3 % (187/1782), seuil 30.0 %
**CLV décomposé** : prime +1.95 % · dérive +2.27 % · part de la sélection 40.6 % (n=2042)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 20.0h)
🔴 **Taille du dépôt** : 5.78 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — ne PAS réécrire l'historique (force-push interdit). Poursuivre la migration R2 (README_MIGRATION_R2.md) ; « nouveau dépôt propre » à planifier plus tard, à froid.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
