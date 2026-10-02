# État du dernier run — Steam Pipeline

Run démarré `2026-10-02T20:27:25` · terminé `2026-10-02T20:51:27` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3037 | 302722 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3009 | 808816 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 180 | 100407 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 49 | 21300 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 62 | 10481 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1649 | 280750 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 424 | 68229 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 376 | 181108 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 5734 | 77700383 | ✅ OK |


**Closings exploitables** : 96 % sur 3 jours (fenêtre t3 : 95 %, n=186) — référence 30 jours 80 % (t3 70 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 60 fichiers, 1055.1 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

> ⛔ **Zone rouge** — une partition approche le mur GitHub de 100 Mo :
> - `parts/live_match_2026-09-30.jsonl` : 90.3 Mo

✅ **Qualité de clôture (Q3)** : 14.2 % d'écarts > 3 % (149/1048), seuil 30.0 %
**CLV décomposé** : prime +1.10 % · dérive +2.49 % · part de la sélection 27.8 % (n=1251)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 10.2h)
🟠 **Taille du dépôt** : 3.63 Go -- zone de vigilance, marge 0.37 Go avant le seuil de 4.0 Go

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
