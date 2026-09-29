# État du dernier run — Steam Pipeline

Run démarré `2026-09-29T15:03:01` · terminé `2026-09-29T15:11:13` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2831 | 282465 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1808 | 481050 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 41 | 17569 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 38 | 14711 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 15 | 2374 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 276 | 45804 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 189 | 29688 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 203 | 84173 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 2762 | 8029448 | ✅ OK |


**Closings exploitables** : 81 % sur 3 jours (fenêtre t3 : 66 %, n=47) — référence 30 jours 59 % (t3 46 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 14 fichiers, 163.0 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 11.3 % d'écarts > 3 % (104/922), seuil 30.0 %
**CLV décomposé** : prime +0.87 % · dérive +2.99 % · part de la sélection 21.2 % (n=179)
✅ **Études Polymarket** : 0 échec(s) (il y a 0.3h)
✅ **Taille du dépôt** : 0.18 Go (marge 3.82 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
