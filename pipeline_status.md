# État du dernier run — Steam Pipeline

Run démarré `2026-09-18T04:46:43` · terminé `2026-09-18T05:12:25` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3225 | 321078 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2376 | 637681 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 126 | 67060 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 44 | 23335 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 62 | 10684 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1514 | 259413 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 304 | 48224 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 278 | 126745 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3383 | 39977235 | ✅ OK |


**Closings exploitables** : 97 % sur 3 jours (fenêtre t3 : 88 %, n=145) — référence 30 jours 83 % (t3 55 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 51 fichiers, 643.0 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 12.8 % d'écarts > 3 % (232/1806), seuil 30.0 %
**CLV décomposé** : prime +2.03 % · dérive +2.76 % · part de la sélection 38.1 % (n=1118)
⚠️ **Études Polymarket** : 3 échec(s) (il y a 19.7h)
🟠 **Taille du dépôt** : 3.06 Go -- zone de vigilance, marge 0.94 Go avant le seuil de 4.0 Go

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
