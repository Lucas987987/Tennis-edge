# État du dernier run — Steam Pipeline

Run démarré `2026-08-27T09:57:44` · terminé `2026-08-27T10:22:44` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2219 | 222205 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1417 | 375547 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 36 | 14768 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 17 | 6949 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 164 | 26450 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 924 | 149193 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 144 | 22163 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 7350 | 36271407 | ✅ OK |

**Partitions** : 81 fichiers, 662.7 Mo au total.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
