# État du dernier run — Steam Pipeline

Run démarré `2026-10-02T05:43:27` · terminé `2026-10-02T06:08:47` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2997 | 298752 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2921 | 787300 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 177 | 99546 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 49 | 21300 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 56 | 9152 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1649 | 273893 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 418 | 67252 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 372 | 178923 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 5428 | 69635529 | ✅ OK |


**Closings exploitables** : 92 % sur 3 jours (fenêtre t3 : 89 %, n=207) — référence 30 jours 79 % (t3 68 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 60 fichiers, 991.7 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

> ⛔ **Zone rouge** — une partition approche le mur GitHub de 100 Mo :
> - `parts/live_match_2026-09-30.jsonl` : 90.3 Mo

✅ **Qualité de clôture (Q3)** : 14.8 % d'écarts > 3 % (158/1069), seuil 30.0 %
**CLV décomposé** : prime +1.10 % · dérive +2.49 % · part de la sélection 27.8 % (n=1251)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.1h)
🟠 **Taille du dépôt** : 3.02 Go -- zone de vigilance, marge 0.98 Go avant le seuil de 4.0 Go

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
