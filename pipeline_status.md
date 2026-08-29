# État du dernier run — Steam Pipeline

Run démarré `2026-08-29T14:09:53` · terminé `2026-08-29T14:22:26` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2385 | 238505 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1568 | 415085 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 37 | 15267 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 17 | 6949 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 98 | 15838 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 976 | 157718 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 155 | 23971 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 6601 | 29715988 | ✅ OK |

**Partitions** : 78 fichiers, 702.0 Mo au total.

✅ **Qualité de clôture (Q3)** : 16.5 % d'écarts > 3 % (162/980), seuil 30.0 %
**CLV décomposé** : prime +1.34 % · dérive +3.62 % · part de la sélection 24.6 % (n=610)
✅ **Études Polymarket** : 0 échec(s) · 3 avertissement(s) (info) (il y a 3.0h)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
