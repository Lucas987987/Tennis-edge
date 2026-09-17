# État du dernier run — Steam Pipeline

Run démarré `2026-09-17T04:55:55` · terminé `2026-09-17T05:21:21` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3188 | 317398 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2325 | 623261 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 121 | 63915 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 44 | 23317 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 72 | 12381 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1482 | 253736 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 288 | 45489 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 268 | 121049 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4366 | 54445862 | ✅ OK |


**Closings exploitables** : 95 % sur 3 jours (fenêtre t3 : 88 %, n=172) — référence 30 jours 83 % (t3 55 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 51 fichiers, 742.1 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 13.1 % d'écarts > 3 % (232/1771), seuil 30.0 %
**CLV décomposé** : prime +2.00 % · dérive +2.76 % · part de la sélection 38.1 % (n=1086)
⚠️ **Études Polymarket** : 3 échec(s) (il y a 20.0h)
✅ **Taille du dépôt** : 2.76 Go (marge 1.24 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
