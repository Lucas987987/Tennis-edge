# État du dernier run — Steam Pipeline

Run démarré `2026-09-15T04:55:53` · terminé `2026-09-15T05:21:34` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3078 | 306605 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2229 | 595652 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 79 | 38774 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 42 | 22133 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 78 | 13493 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1413 | 241882 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 252 | 39749 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 251 | 111236 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4568 | 47060773 | ✅ OK |


**Closings exploitables** : 80 % sur 3 jours (fenêtre t3 : 69 %, n=183) — référence 30 jours 82 % (t3 53 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 50 fichiers, 649.7 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 13.4 % d'écarts > 3 % (224/1667), seuil 30.0 %
**CLV décomposé** : prime +2.00 % · dérive +2.76 % · part de la sélection 38.6 % (n=1017)
⚠️ **Études Polymarket** : 3 échec(s) (il y a 19.4h)
✅ **Taille du dépôt** : 1.69 Go (marge 2.31 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
