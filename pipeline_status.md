# État du dernier run — Steam Pipeline

Run démarré `2026-08-18T01:27:23` · terminé `2026-08-18T01:56:51` (UTC)

**Verdict : 2 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 1870 | 188014 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 0 | 0 | ❌ ABSENT |
| Journal forward — match | `paper_trades_match.jsonl` | 17 | 6650 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 6 | 2333 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 39 | 6121 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 746 | 120618 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 52 | 7450 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 1997 | 21358978 | ✅ OK |

**Partitions** : 15 fichiers, 203.7 Mo au total.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
