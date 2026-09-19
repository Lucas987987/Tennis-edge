# État du dernier run — Steam Pipeline

Run démarré `2026-09-19T04:39:54` · terminé `2026-09-19T05:06:12` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3255 | 324063 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2424 | 651612 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 127 | 67636 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 44 | 23335 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 46 | 7934 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1537 | 263490 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 310 | 49258 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 285 | 130441 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 2410 | 27628547 | ✅ OK |


**Closings exploitables** : 96 % sur 3 jours (fenêtre t3 : 88 %, n=120) — référence 30 jours 83 % (t3 56 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 52 fichiers, 598.7 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 12.7 % d'écarts > 3 % (232/1823), seuil 30.0 %
**CLV décomposé** : prime +2.03 % · dérive +2.80 % · part de la sélection 37.1 % (n=1141)
⚠️ **Études Polymarket** : 3 échec(s) (il y a 20.0h)
🟠 **Taille du dépôt** : 3.29 Go -- zone de vigilance, marge 0.71 Go avant le seuil de 4.0 Go

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
