# État du dernier run — Steam Pipeline

Run démarré `2026-10-04T15:17:09` · terminé `2026-10-04T15:46:54` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3109 | 309770 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3054 | 819969 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 181 | 101688 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 49 | 21300 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 54 | 9124 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1689 | 287689 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 433 | 69686 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 381 | 183963 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4209 | 48729019 | ✅ OK |


**Closings exploitables** : 91 % sur 3 jours (fenêtre t3 : 88 %, n=144) — référence 30 jours 79 % (t3 72 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 64 fichiers, 811.6 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 13.7 % d'écarts > 3 % (135/988), seuil 30.0 %
**CLV décomposé** : prime +1.12 % · dérive +2.50 % · part de la sélection 27.9 % (n=1291)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 5.0h)
✅ **Taille du dépôt** : 4.29 Go (marge 0.71 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
