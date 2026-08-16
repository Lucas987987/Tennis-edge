# État du dernier run — Steam Pipeline

Run démarré `2026-08-16T13:37:36` · terminé `2026-08-16T13:45:33` (UTC)

**Verdict : 2 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 1824 | 183523 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 0 | 0 | ❌ ABSENT |
| Journal forward — match | `paper_trades_match.jsonl` | 16 | 6156 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 6 | 2333 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 61 | 9509 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 831 | 133742 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 48 | 5821 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3910 | 28616543 | ✅ OK |

**Partitions** : 25 fichiers, 639.1 Mo au total.

> ⛔ **Zone rouge** — une partition approche le mur GitHub de 100 Mo :
> - `parts/hist_book_2026-W33.jsonl` : 97.7 Mo

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
