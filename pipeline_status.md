# État du dernier run — Steam Pipeline

Run démarré `2026-10-21T04:53:29` · terminé `2026-10-21T05:32:57` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3781 | 375901 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3506 | 942977 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 213 | 118752 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 58 | 28143 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 57 | 9426 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 2226 | 380840 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 576 | 93577 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 489 | 244577 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 5735 | 70242943 | ✅ OK |


**Closings exploitables** : 88 % sur 3 jours (fenêtre t3 : 61 %, n=213) — référence 30 jours 91 % (t3 80 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 73 fichiers, 569.2 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 9.9 % d'écarts > 3 % (175/1759), seuil 30.0 %
**CLV décomposé** : prime +2.04 % · dérive +2.40 % · part de la sélection 40.6 % (n=1829)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.9h)
🔴 **Taille du dépôt** : 5.68 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — ne PAS réécrire l'historique (force-push interdit). Poursuivre la migration R2 (README_MIGRATION_R2.md) ; « nouveau dépôt propre » à planifier plus tard, à froid.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
