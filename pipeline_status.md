# État du dernier run — Steam Pipeline

Run démarré `2026-10-07T06:03:36` · terminé `2026-10-07T06:36:02` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3263 | 324951 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3127 | 838460 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 187 | 104980 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 50 | 21850 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 53 | 9020 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1757 | 299457 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 468 | 75609 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 407 | 198816 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 5351 | 58083945 | ✅ OK |


**Closings exploitables** : 85 % sur 3 jours (fenêtre t3 : 77 %, n=184) — référence 30 jours 80 % (t3 75 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 64 fichiers, 471.6 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 13.9 % d'écarts > 3 % (129/925), seuil 30.0 %
**CLV décomposé** : prime +1.11 % · dérive +2.45 % · part de la sélection 28.0 % (n=1359)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.2h)
🟠 **Taille du dépôt** : 4.57 Go -- zone de vigilance, marge 0.43 Go avant le seuil de 5.0 Go

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
