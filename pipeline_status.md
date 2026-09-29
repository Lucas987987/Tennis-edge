# État du dernier run — Steam Pipeline

Run démarré `2026-09-29T13:47:06` · terminé `2026-09-29T13:55:36` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2826 | 281952 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1807 | 480802 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 41 | 17569 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 38 | 14711 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 11 | 1734 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 276 | 45804 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 189 | 29688 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 203 | 84173 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 2615 | 6346560 | ✅ OK |


**Closings exploitables** : 75 % sur 3 jours (fenêtre t3 : 64 %, n=36) — référence 30 jours 53 % (t3 41 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 14 fichiers, 149.8 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 11.3 % d'écarts > 3 % (104/922), seuil 30.0 %
**CLV décomposé** : prime +0.87 % · dérive +2.99 % · part de la sélection 21.2 % (n=179)
⏳ **Études Polymarket** : statut périmé ou sans date (âge 532.5h) -- le producteur (polymarket_studies.yml) tourne-t-il encore ?
✅ **Taille du dépôt** : 0.18 Go (marge 3.82 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
