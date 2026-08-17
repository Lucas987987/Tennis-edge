# État du dernier run — Steam Pipeline

Run démarré `2026-08-17T01:52:05` · terminé `2026-08-17T02:02:30` (UTC)

**Verdict : 2 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 1856 | 186659 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 0 | 0 | ❌ ABSENT |
| Journal forward — match | `paper_trades_match.jsonl` | 17 | 6650 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 6 | 2333 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 49 | 7714 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 734 | 118755 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 48 | 6804 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 2564 | 23401577 | ✅ OK |

**Partitions** : 12 fichiers, 167.5 Mo au total.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
