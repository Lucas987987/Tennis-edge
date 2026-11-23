# État du dernier run — Steam Pipeline

Run démarré `2026-11-20T11:35:12` · terminé `2026-11-23T08:54:43` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3990 | 428297 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3856 | 1030961 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 303 | 160062 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 105 | 49654 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 39 | 6784 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 2945 | 498774 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 737 | 119404 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 722 | 371037 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3633 | 23162815 | ✅ OK |


**Closings exploitables** : 79 % sur 3 jours (fenêtre t3 : 64 %, n=131) — référence 30 jours 92 % (t3 82 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 102 fichiers, 699.0 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 6.9 % d'écarts > 3 % (186/2704), seuil 30.0 %
**CLV décomposé** : prime +2.22 % · dérive +2.33 % · part de la sélection 44.0 % (n=2516)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 20.1h)
✅ **Taille du dépôt** : 0.16 Go (marge 3.84 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
