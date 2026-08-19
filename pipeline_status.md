# État du dernier run — Steam Pipeline

Run démarré `2026-08-19T01:47:31` · terminé `2026-08-19T01:59:04` (UTC)

**Verdict : 2 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 1888 | 189744 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 0 | 0 | ❌ ABSENT |
| Journal forward — match | `paper_trades_match.jsonl` | 17 | 6650 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 6 | 2333 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 26 | 4028 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 758 | 122462 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 53 | 7604 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 1638 | 16283695 | ✅ OK |

**Partitions** : 14 fichiers, 132.9 Mo au total.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
