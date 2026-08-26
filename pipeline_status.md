# État du dernier run — Steam Pipeline

Run démarré `2026-08-26T01:56:52` · terminé `2026-08-26T02:09:10` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2140 | 214412 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1328 | 352420 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 35 | 13547 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 16 | 6150 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 123 | 19757 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 892 | 143969 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 136 | 20826 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 6171 | 33746828 | ✅ OK |

**Partitions** : 78 fichiers, 596.8 Mo au total.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
