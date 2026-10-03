# État du dernier run — Steam Pipeline

Run démarré `2026-10-03T07:40:40` · terminé `2026-10-03T08:07:50` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3049 | 303845 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3019 | 811312 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 180 | 100479 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 49 | 21300 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 53 | 8953 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1672 | 284744 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 425 | 68376 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 377 | 181617 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4352 | 64366916 | ✅ OK |


**Closings exploitables** : 97 % sur 3 jours (fenêtre t3 : 96 %, n=171) — référence 30 jours 81 % (t3 71 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 60 fichiers, 936.3 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

> ⛔ **Zone rouge** — une partition approche le mur GitHub de 100 Mo :
> - `parts/live_match_2026-09-30.jsonl` : 90.3 Mo

✅ **Qualité de clôture (Q3)** : 14.3 % d'écarts > 3 % (147/1031), seuil 30.0 %
**CLV décomposé** : prime +1.11 % · dérive +2.50 % · part de la sélection 28.0 % (n=1274)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 21.5h)
🟠 **Taille du dépôt** : 3.63 Go -- zone de vigilance, marge 0.37 Go avant le seuil de 4.0 Go

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
