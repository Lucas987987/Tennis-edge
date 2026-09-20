# État du dernier run — Steam Pipeline

Run démarré `2026-09-20T04:56:45` · terminé `2026-09-20T05:22:45` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3285 | 326971 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2468 | 664351 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 128 | 68256 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 44 | 23335 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 42 | 7264 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1554 | 266420 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 314 | 49941 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 288 | 132129 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 2092 | 20728817 | ✅ OK |


**Closings exploitables** : 92 % sur 3 jours (fenêtre t3 : 82 %, n=100) — référence 30 jours 83 % (t3 56 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 52 fichiers, 585.9 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 12.9 % d'écarts > 3 % (235/1817), seuil 30.0 %
**CLV décomposé** : prime +2.04 % · dérive +2.78 % · part de la sélection 37.6 % (n=1158)
⚠️ **Études Polymarket** : 3 échec(s) (il y a 20.5h)
🟠 **Taille du dépôt** : 3.51 Go -- zone de vigilance, marge 0.49 Go avant le seuil de 4.0 Go

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
