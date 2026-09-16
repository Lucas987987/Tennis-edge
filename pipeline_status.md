# État du dernier run — Steam Pipeline

Run démarré `2026-09-16T04:52:54` · terminé `2026-09-16T05:18:02` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3141 | 312805 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2298 | 614797 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 120 | 62551 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 44 | 23317 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 84 | 14498 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1451 | 248343 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 282 | 44562 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 265 | 119329 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 5203 | 60344516 | ✅ OK |


**Closings exploitables** : 86 % sur 3 jours (fenêtre t3 : 76 %, n=214) — référence 30 jours 82 % (t3 54 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 50 fichiers, 709.6 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 13.3 % d'écarts > 3 % (229/1728), seuil 30.0 %
**CLV décomposé** : prime +2.00 % · dérive +2.76 % · part de la sélection 38.2 % (n=1055)
⚠️ **Études Polymarket** : 3 échec(s) (il y a 19.8h)
✅ **Taille du dépôt** : 2.24 Go (marge 1.76 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
