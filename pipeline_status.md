# État du dernier run — Steam Pipeline

Run démarré `2026-10-04T05:58:10` · terminé `2026-10-04T06:27:09` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3085 | 307398 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3041 | 816711 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 181 | 101450 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 49 | 21300 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 51 | 8594 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1672 | 284744 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 432 | 69539 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 380 | 183450 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3673 | 45706762 | ✅ OK |


**Closings exploitables** : 99 % sur 3 jours (fenêtre t3 : 96 %, n=144) — référence 30 jours 81 % (t3 72 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 63 fichiers, 756.8 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 13.8 % d'écarts > 3 % (137/994), seuil 30.0 %
**CLV décomposé** : prime +1.11 % · dérive +2.50 % · part de la sélection 28.0 % (n=1274)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 20.4h)
🔴 **Taille du dépôt** : 4.2 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
