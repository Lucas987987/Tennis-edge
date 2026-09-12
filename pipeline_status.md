# État du dernier run — Steam Pipeline

Run démarré `2026-09-12T20:18:25` · terminé `2026-09-12T20:38:05` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2921 | 291117 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2079 | 553309 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 69 | 33048 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 41 | 20247 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 40 | 6851 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1326 | 226899 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 227 | 35744 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 228 | 98312 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 2188 | 25797642 | ✅ OK |


**Closings exploitables** : 86 % sur 3 jours (fenêtre t3 : 83 %, n=88) — référence 30 jours 82 % (t3 48 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 46 fichiers, 493.4 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 13.8 % d'écarts > 3 % (211/1528), seuil 30.0 %
**CLV décomposé** : prime +1.98 % · dérive +2.77 % · part de la sélection 37.6 % (n=930)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 11.9h)
✅ **Taille du dépôt** : 1.07 Go (marge 2.93 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
