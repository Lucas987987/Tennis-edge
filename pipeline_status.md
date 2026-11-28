# État du dernier run — Steam Pipeline

Run démarré `2026-11-20T11:35:12` · terminé `2026-11-28T09:10:56` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 4017 | 431204 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3932 | 1050391 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 329 | 179719 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 122 | 60398 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 17 | 3068 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 3568 | 604397 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 814 | 132145 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 770 | 398822 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 1658 | 12938044 | ✅ OK |


**Closings exploitables** : 95 % sur 3 jours (fenêtre t3 : 85 %, n=86) — référence 30 jours 92 % (t3 84 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 107 fichiers, 888.1 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 7.7 % d'écarts > 3 % (224/2918), seuil 30.0 %
**CLV décomposé** : prime +2.11 % · dérive +2.39 % · part de la sélection 43.1 % (n=3073)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.1h)
✅ **Taille du dépôt** : 0.49 Go (marge 3.51 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
