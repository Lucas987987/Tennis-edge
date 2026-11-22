# État du dernier run — Steam Pipeline

Run démarré `2026-11-20T11:35:12` · terminé `2026-11-22T08:02:07` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3978 | 427029 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3856 | 1030961 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 292 | 156802 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 104 | 49359 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 26 | 4384 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 2945 | 498774 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 709 | 114920 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 695 | 356345 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 2479 | 13772738 | ✅ OK |


**Closings exploitables** : 70 % sur 3 jours (fenêtre t3 : 60 %, n=98) — référence 30 jours 92 % (t3 82 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 98 fichiers, 694.7 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 7.0 % d'écarts > 3 % (185/2660), seuil 30.0 %
**CLV décomposé** : prime +2.22 % · dérive +2.33 % · part de la sélection 44.0 % (n=2516)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.1h)
✅ **Taille du dépôt** : 0.13 Go (marge 3.87 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
