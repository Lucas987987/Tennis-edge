# État du dernier run — Steam Pipeline

Run démarré `2026-09-04T19:00:05` · terminé `2026-09-04T19:14:34` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2573 | 257010 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1723 | 456797 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 38 | 16079 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 17 | 7009 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 19 | 3158 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1034 | 167322 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 165 | 25547 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 175 | 68058 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 1365 | 7106814 | ✅ OK |


> ⛔ **Script(s) appelé(s) par un workflow et ABSENT(S) du dépôt** — l'appel échoue derrière un `|| true`, sans run rouge :
> - `scripts/canal_public.py`
**Partitions** : 37 fichiers, 327.6 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 16.8 % d'écarts > 3 % (177/1053), seuil 30.0 %
**CLV décomposé** : prime +1.28 % · dérive +3.56 % · part de la sélection 23.9 % (n=668)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 10.3h)
⚠️ **Taille du dépôt** : mesure indisponible ce run (gh api indisponible (gh: To use GitHub CLI in a GitHub Actions workflow, set the GH_TOKEN environment variable. Example:
  env:
    GH_TOKEN:) — taille NON vérifiée ce run.)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
