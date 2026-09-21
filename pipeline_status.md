# État du dernier run — Steam Pipeline

Run démarré `2026-09-21T05:01:11` · terminé `2026-09-21T05:26:48` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3311 | 329493 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2502 | 674216 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 131 | 70150 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 48 | 25836 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 40 | 6800 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1575 | 270132 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 327 | 52263 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 295 | 136493 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3148 | 25366564 | ✅ OK |


**Closings exploitables** : 88 % sur 3 jours (fenêtre t3 : 75 %, n=93) — référence 30 jours 83 % (t3 57 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 55 fichiers, 523.7 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 12.8 % d'écarts > 3 % (232/1816), seuil 30.0 %
**CLV décomposé** : prime +2.05 % · dérive +2.80 % · part de la sélection 37.4 % (n=1179)
⚠️ **Études Polymarket** : 3 échec(s) (il y a 20.1h)
🟠 **Taille du dépôt** : 3.68 Go -- zone de vigilance, marge 0.32 Go avant le seuil de 4.0 Go

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
