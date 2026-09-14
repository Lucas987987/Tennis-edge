# État du dernier run — Steam Pipeline

Run démarré `2026-09-14T05:00:44` · terminé `2026-09-14T05:21:21` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3009 | 299812 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2133 | 569652 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 71 | 34045 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 41 | 20308 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 67 | 11563 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1381 | 236421 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 233 | 36757 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 239 | 104056 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4030 | 31530619 | ✅ OK |


**Closings exploitables** : 78 % sur 3 jours (fenêtre t3 : 67 %, n=147) — référence 30 jours 82 % (t3 50 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 50 fichiers, 501.7 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 13.8 % d'écarts > 3 % (222/1606), seuil 30.0 %
**CLV décomposé** : prime +1.98 % · dérive +2.76 % · part de la sélection 37.8 % (n=985)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.7h)
✅ **Taille du dépôt** : 1.18 Go (marge 2.82 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
