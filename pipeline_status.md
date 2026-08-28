# État du dernier run — Steam Pipeline

Run démarré `2026-08-28T11:21:55` · terminé `2026-08-28T11:34:53` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2285 | 228700 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1495 | 395921 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 37 | 15267 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 17 | 6949 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 118 | 19220 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 950 | 153448 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 154 | 23793 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 7130 | 24724504 | ✅ OK |

**Partitions** : 80 fichiers, 586.5 Mo au total.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
