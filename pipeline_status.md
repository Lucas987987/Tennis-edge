# État du dernier run — Steam Pipeline

Run démarré `2026-10-11T08:40:46` · terminé `2026-10-11T09:14:26` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3450 | 343319 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3359 | 901710 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 197 | 110318 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 51 | 22381 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 41 | 6811 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1893 | 323009 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 483 | 78193 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 420 | 205798 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3561 | 37495766 | ✅ OK |


**Closings exploitables** : 94 % sur 3 jours (fenêtre t3 : 78 %, n=138) — référence 30 jours 92 % (t3 84 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 66 fichiers, 560.3 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 10.7 % d'écarts > 3 % (155/1447), seuil 30.0 %
**CLV décomposé** : prime +2.13 % · dérive +2.50 % · part de la sélection 40.4 % (n=1494)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 22.5h)
🔴 **Taille du dépôt** : 4.84 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — lancer le git filter-repo (RUNBOOK_FILTER_REPO.md) sans attendre.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
