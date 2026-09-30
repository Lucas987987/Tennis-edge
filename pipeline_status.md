# État du dernier run — Steam Pipeline

Run démarré `2026-09-30T09:50:55` · terminé `2026-09-30T10:15:00` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2884 | 287683 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2845 | 767858 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 172 | 96878 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 49 | 21300 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 33 | 5438 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1559 | 258707 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 385 | 61968 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 353 | 167676 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3723 | 32305044 | ✅ OK |


**Closings exploitables** : 86 % sur 3 jours (fenêtre t3 : 80 %, n=101) — référence 30 jours 66 % (t3 54 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 53 fichiers, 633.9 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 14.4 % d'écarts > 3 % (161/1121), seuil 30.0 %
**CLV décomposé** : prime +1.06 % · dérive +2.61 % · part de la sélection 26.8 % (n=1161)
✅ **Études Polymarket** : 0 échec(s) (il y a 19.4h)
✅ **Taille du dépôt** : 0.18 Go (marge 3.82 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
