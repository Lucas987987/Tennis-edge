# État du dernier run — Steam Pipeline

Run démarré `2026-08-21T05:51:59` · terminé `2026-08-21T05:58:53` (UTC)

**Verdict : 2 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 1910 | 191857 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 0 | 0 | ❌ ABSENT |
| Journal forward — match | `paper_trades_match.jsonl` | 17 | 6650 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 6 | 2333 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 12 | 1863 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 758 | 122462 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 53 | 7604 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 957 | 7213381 | ✅ OK |

**Partitions** : 22 fichiers, 394.0 Mo au total.

> ⛔ **Zone rouge** — une partition approche le mur GitHub de 100 Mo :
> - `parts/pm_ticks_2026-08-19.jsonl` : 97.8 Mo

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
