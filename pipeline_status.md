# État du dernier run — Steam Pipeline

Run démarré `2026-09-05T04:23:41` · terminé `2026-09-05T04:44:15` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2583 | 257980 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1724 | 457050 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 38 | 16079 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 17 | 7009 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 23 | 3789 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1062 | 171984 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 167 | 25851 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 177 | 69113 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 1679 | 8979134 | ✅ OK |

**Partitions** : 37 fichiers, 303.7 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 16.4 % d'écarts > 3 % (179/1090), seuil 30.0 %
**CLV décomposé** : prime +1.28 % · dérive +3.56 % · part de la sélection 23.9 % (n=668)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.8h)
🟠 **Taille du dépôt** : 3.99 Go -- zone de vigilance, marge 0.01 Go avant le seuil de 4.0 Go

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
