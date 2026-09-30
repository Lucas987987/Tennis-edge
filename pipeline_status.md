# État du dernier run — Steam Pipeline

Run démarré `2026-09-30T06:47:35` · terminé `2026-09-30T07:05:24` (UTC)

**Verdict : 2 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2874 | 286708 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2837 | 765904 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 172 | 96878 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 49 | 21300 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 28 | 4570 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1198 | 199650 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 382 | 61505 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 351 | 166593 | ⏳ FIGÉ |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3581 | 28792194 | ✅ OK |


**Closings exploitables** : 84 % sur 3 jours (fenêtre t3 : 76 %, n=91) — référence 30 jours 65 % (t3 52 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 41 fichiers, 496.5 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 14.4 % d'écarts > 3 % (161/1121), seuil 30.0 %
**CLV décomposé** : prime +1.17 % · dérive +2.84 % · part de la sélection 28.8 % (n=802)
✅ **Études Polymarket** : 0 échec(s) (il y a 16.2h)
✅ **Taille du dépôt** : 0.18 Go (marge 3.82 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
