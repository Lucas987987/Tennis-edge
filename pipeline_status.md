# État du dernier run — Steam Pipeline

Run démarré `2026-10-01T06:01:04` · terminé `2026-10-01T06:25:55` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2936 | 292812 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2872 | 775029 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 173 | 97470 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 49 | 21300 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 40 | 6610 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1615 | 268173 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 403 | 64863 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 363 | 173554 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4436 | 52323129 | ✅ OK |


**Closings exploitables** : 89 % sur 3 jours (fenêtre t3 : 84 %, n=154) — référence 30 jours 77 % (t3 64 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 56 fichiers, 797.4 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

> ⛔ **Zone rouge** — une partition approche le mur GitHub de 100 Mo :
> - `parts/live_match_2026-09-30.jsonl` : 90.3 Mo

✅ **Qualité de clôture (Q3)** : 14.5 % d'écarts > 3 % (157/1083), seuil 30.0 %
**CLV décomposé** : prime +1.08 % · dérive +2.56 % · part de la sélection 27.2 % (n=1217)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.8h)
✅ **Taille du dépôt** : 1.96 Go (marge 2.04 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
