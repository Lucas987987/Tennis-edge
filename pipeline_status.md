# État du dernier run — Steam Pipeline

Run démarré `2026-10-05T05:46:03` · terminé `2026-10-05T06:16:10` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3134 | 312260 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3052 | 819619 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 182 | 102032 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 49 | 21300 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 45 | 7627 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1710 | 291358 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 438 | 70470 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 385 | 186160 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3972 | 40883170 | ✅ OK |


**Closings exploitables** : 90 % sur 3 jours (fenêtre t3 : 85 %, n=136) — référence 30 jours 79 % (t3 72 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 67 fichiers, 603.7 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 13.8 % d'écarts > 3 % (132/955), seuil 30.0 %
**CLV décomposé** : prime +1.11 % · dérive +2.50 % · part de la sélection 27.9 % (n=1312)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.5h)
✅ **Taille du dépôt** : 4.29 Go (marge 0.71 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
