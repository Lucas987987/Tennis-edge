# État du dernier run — Steam Pipeline

Run démarré `2026-08-25T09:50:16` · terminé `2026-08-25T10:08:56` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2065 | 207071 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1233 | 327732 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 34 | 12614 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 15 | 5575 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 118 | 18755 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 855 | 137999 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 130 | 19750 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 6017 | 28984289 | ✅ OK |

**Partitions** : 72 fichiers, 630.5 Mo au total.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
