# État du dernier run — Steam Pipeline

Run démarré `2026-10-08T06:09:39` · terminé `2026-10-08T06:42:16` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3313 | 329831 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3181 | 852132 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 188 | 105512 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 51 | 22381 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 50 | 8556 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1777 | 302961 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 473 | 76579 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 409 | 200128 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4584 | 53188149 | ✅ OK |


**Closings exploitables** : 92 % sur 3 jours (fenêtre t3 : 83 %, n=179) — référence 30 jours 83 % (t3 78 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 62 fichiers, 532.8 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 14.6 % d'écarts > 3 % (134/917), seuil 30.0 %
**CLV décomposé** : prime +1.11 % · dérive +2.48 % · part de la sélection 27.8 % (n=1379)
⏳ **Études Polymarket** : statut périmé ou sans date (âge 43.3h) -- le producteur (polymarket_studies.yml) tourne-t-il encore ?
🔴 **Taille du dépôt** : 4.59 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
