# État du dernier run — Steam Pipeline

Run démarré `2026-09-04T04:28:40` · terminé `2026-09-04T04:50:23` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2458 | 245697 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1605 | 426254 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 38 | 16062 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 17 | 7009 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 11 | 1793 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1034 | 167283 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 161 | 24898 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 1111 | 4566620 | ✅ OK |

**Partitions** : 51 fichiers, 425.0 Mo au total.

✅ **Qualité de clôture (Q3)** : 16.8 % d'écarts > 3 % (177/1053), seuil 30.0 %
**CLV décomposé** : prime +1.34 % · dérive +3.62 % · part de la sélection 24.6 % (n=610)
⚠️ **Études Polymarket** : 1 échec(s) · 2 avertissement(s) (info) (il y a 19.7h)
⚠️ **Taille du dépôt** : mesure indisponible ce run (gh api indisponible (gh: To use GitHub CLI in a GitHub Actions workflow, set the GH_TOKEN environment variable. Example:
  env:
    GH_TOKEN:) — taille NON vérifiée ce run.)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
