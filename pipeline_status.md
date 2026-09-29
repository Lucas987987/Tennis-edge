# État du dernier run — Steam Pipeline

Run démarré `2026-09-29T09:39:45` · terminé `2026-09-29T09:48:17` (UTC)

**Verdict : 3 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2737 | 273178 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1787 | 475753 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 40 | 17253 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 38 | 14711 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 1 | 176 | ⚠️ VIDE |
| Audit des moves (historique) | `moves_detail_hist.csv` | 276 | 45804 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 179 | 27929 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 199 | 81647 | ⏳ FIGÉ |
| Courbes live reconstruites | `book_curves_live.jsonl` | 1767 | 547975 | ✅ OK |


**Closings exploitables** : 18 % sur 3 jours (fenêtre t3 : 18 %, n=11) — référence 30 jours 50 % (t3 39 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 14 fichiers, 104.9 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 11.3 % d'écarts > 3 % (104/922), seuil 30.0 %
**CLV décomposé** : prime +0.87 % · dérive +2.99 % · part de la sélection 21.2 % (n=179)
⏳ **Études Polymarket** : statut périmé ou sans date (âge 528.4h) -- le producteur (polymarket_studies.yml) tourne-t-il encore ?
⏳ **Taille du dépôt** : statut périmé ou sans date (âge 524.2h) -- le producteur (health_check.yml) tourne-t-il encore ?

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
