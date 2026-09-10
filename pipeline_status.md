# État du dernier run — Steam Pipeline

Run démarré `2026-09-10T04:37:23` · terminé `2026-09-10T04:57:35` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2850 | 284229 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1998 | 530437 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 68 | 32041 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 41 | 20247 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 67 | 11219 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1258 | 209755 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 220 | 34654 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 220 | 93922 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3836 | 50149017 | ✅ OK |


**Closings exploitables** : 87 % sur 3 jours (fenêtre t3 : 76 %, n=186) — référence 30 jours 83 % (t3 49 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 45 fichiers, 603.2 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 16.6 % d'écarts > 3 % (194/1171), seuil 30.0 %
**CLV décomposé** : prime +1.11 % · dérive +2.79 % · part de la sélection 27.6 % (n=862)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.9h)
🔴 **Taille du dépôt** : 4.79 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
