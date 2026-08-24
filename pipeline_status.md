# État du dernier run — Steam Pipeline

Run démarré `2026-08-24T01:57:38` · terminé `2026-08-24T02:07:35` (UTC)

**Verdict : 2 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 1992 | 199877 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 0 | 0 | ❌ ABSENT |
| Journal forward — match | `paper_trades_match.jsonl` | 21 | 8119 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 8 | 3068 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 32 | 5132 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 822 | 132648 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 68 | 10124 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 2425 | 8239333 | ✅ OK |

**Partitions** : 26 fichiers, 663.7 Mo au total.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
