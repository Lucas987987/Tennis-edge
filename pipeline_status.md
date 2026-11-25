# État du dernier run — Steam Pipeline

Run démarré `2026-11-20T11:35:12` · terminé `2026-11-25T10:00:04` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 4005 | 429928 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3891 | 1039867 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 317 | 169089 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 113 | 54304 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 42 | 7455 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 3315 | 561175 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 775 | 125994 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 746 | 385095 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4538 | 37524496 | ✅ OK |


**Closings exploitables** : 94 % sur 3 jours (fenêtre t3 : 86 %, n=201) — référence 30 jours 93 % (t3 84 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 103 fichiers, 835.7 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 7.6 % d'écarts > 3 % (215/2836), seuil 30.0 %
**CLV décomposé** : prime +2.06 % · dérive +2.33 % · part de la sélection 43.0 % (n=2844)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 18.9h)
✅ **Taille du dépôt** : 0.26 Go (marge 3.74 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
