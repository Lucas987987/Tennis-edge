# État du dernier run — Steam Pipeline

Run démarré `2026-11-09T06:39:58` · terminé `2026-11-09T07:52:09` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3855 | 383193 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3806 | 1018777 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 250 | 138021 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 72 | 37009 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 36 | 6093 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 2945 | 498511 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 633 | 102664 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 619 | 315530 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4476 | 33884116 | ✅ OK |


**Closings exploitables** : 94 % sur 3 jours (fenêtre t3 : 85 %, n=129) — référence 30 jours 93 % (t3 81 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 93 fichiers, 702.3 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 8.1 % d'écarts > 3 % (171/2110), seuil 30.0 %
**CLV décomposé** : prime +2.22 % · dérive +2.33 % · part de la sélection 44.0 % (n=2516)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 20.4h)
🔴 **Taille du dépôt** : 6.8 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — ne PAS réécrire l'historique (force-push interdit). Poursuivre la migration R2 (README_MIGRATION_R2.md) ; « nouveau dépôt propre » à planifier plus tard, à froid.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
