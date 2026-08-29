# État du dernier run — Steam Pipeline

Run démarré `2026-08-29T06:05:17` · terminé `2026-08-29T06:18:01` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2350 | 235050 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1537 | 407396 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 37 | 15267 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 17 | 6949 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 96 | 15542 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 976 | 157718 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 155 | 23971 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 6529 | 22412443 | ✅ OK |

**Partitions** : 80 fichiers, 640.3 Mo au total.

✅ **Qualité de clôture (Q3)** : 16.5 % d'écarts > 3 % (162/980), seuil 30.0 %
**CLV décomposé** : prime +1.35 % · dérive +3.51 % · part de la sélection 25.7 % (n=585)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
