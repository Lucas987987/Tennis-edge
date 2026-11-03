# État du dernier run — Steam Pipeline

Run démarré `2026-11-03T06:51:45` · terminé `2026-11-03T08:02:03` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3855 | 383193 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3806 | 1018777 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 246 | 135703 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 71 | 36304 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 76 | 12496 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 2897 | 490872 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 612 | 99161 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 597 | 303512 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 6434 | 58351722 | ✅ OK |


**Closings exploitables** : 93 % sur 3 jours (fenêtre t3 : 86 %, n=208) — référence 30 jours 92 % (t3 80 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 89 fichiers, 698.8 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 8.3 % d'écarts > 3 % (162/1958), seuil 30.0 %
**CLV décomposé** : prime +2.22 % · dérive +2.33 % · part de la sélection 43.5 % (n=2473)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.2h)
🔴 **Taille du dépôt** : 6.64 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — ne PAS réécrire l'historique (force-push interdit). Poursuivre la migration R2 (README_MIGRATION_R2.md) ; « nouveau dépôt propre » à planifier plus tard, à froid.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
