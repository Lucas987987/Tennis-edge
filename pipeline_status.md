# État du dernier run — Steam Pipeline

Run démarré `2026-09-13T04:52:36` · terminé `2026-09-13T05:14:10` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2934 | 292417 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2105 | 560815 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 69 | 33063 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 41 | 20247 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 32 | 5539 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1349 | 230897 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 227 | 35744 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 228 | 98312 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 1859 | 16842724 | ✅ OK |


**Closings exploitables** : 86 % sur 3 jours (fenêtre t3 : 81 %, n=84) — référence 30 jours 82 % (t3 48 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 47 fichiers, 472.9 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 13.8 % d'écarts > 3 % (214/1548), seuil 30.0 %
**CLV décomposé** : prime +1.96 % · dérive +2.77 % · part de la sélection 37.5 % (n=953)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 20.5h)
✅ **Taille du dépôt** : 1.07 Go (marge 2.93 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
