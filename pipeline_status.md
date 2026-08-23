# État du dernier run — Steam Pipeline

Run démarré `2026-08-23T01:56:46` · terminé `2026-08-23T02:08:20` (UTC)

**Verdict : 2 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 1952 | 195940 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 0 | 0 | ❌ ABSENT |
| Journal forward — match | `paper_trades_match.jsonl` | 20 | 7750 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 8 | 3068 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 21 | 3342 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 804 | 129685 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 64 | 9278 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 1210 | 3952485 | ✅ OK |

**Partitions** : 22 fichiers, 396.6 Mo au total.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
