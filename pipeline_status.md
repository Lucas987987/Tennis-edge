# État du dernier run — Steam Pipeline

Run démarré `2026-09-06T04:33:59` · terminé `2026-09-06T04:50:26` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2608 | 260412 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1742 | 462464 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 38 | 16323 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 17 | 7070 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 31 | 5140 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1086 | 175932 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 168 | 26019 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 180 | 70618 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 2191 | 16454907 | ✅ OK |

**Partitions** : 41 fichiers, 423.3 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 16.0 % d'écarts > 3 % (181/1129), seuil 30.0 %
**CLV décomposé** : prime +1.24 % · dérive +3.61 % · part de la sélection 23.5 % (n=693)
⏳ **Études Polymarket** : statut périmé ou sans date (âge 43.9h) -- le producteur (polymarket_studies.yml) tourne-t-il encore ?
🟠 **Taille du dépôt** : 3.99 Go -- zone de vigilance, marge 0.01 Go avant le seuil de 4.0 Go

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
