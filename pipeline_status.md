# État du dernier run — Steam Pipeline

Run démarré `2026-10-10T05:55:24` · terminé `2026-10-10T06:29:17` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3397 | 338122 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3233 | 865602 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 188 | 105512 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 51 | 22381 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 33 | 5555 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1863 | 318048 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 479 | 77530 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 417 | 204193 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3360 | 37485169 | ✅ OK |


**Closings exploitables** : 99 % sur 3 jours (fenêtre t3 : 84 %, n=142) — référence 30 jours 92 % (t3 85 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 66 fichiers, 569.6 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 13.6 % d'écarts > 3 % (130/953), seuil 30.0 %
**CLV décomposé** : prime +2.17 % · dérive +2.59 % · part de la sélection 40.3 % (n=1464)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.0h)
🔴 **Taille du dépôt** : 4.71 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
