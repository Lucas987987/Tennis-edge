# État du dernier run — Steam Pipeline

Run démarré `2026-09-30T05:34:55` · terminé `2026-09-30T05:45:53` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2869 | 286221 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 1837 | 489146 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 41 | 17780 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 38 | 14711 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 28 | 4564 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 302 | 50215 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 191 | 30036 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 209 | 87144 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3562 | 27352945 | ✅ OK |


**Closings exploitables** : 83 % sur 3 jours (fenêtre t3 : 76 %, n=86) — référence 30 jours 65 % (t3 52 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 20 fichiers, 325.9 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 11.7 % d'écarts > 3 % (106/908), seuil 30.0 %
**CLV décomposé** : prime +0.93 % · dérive +2.97 % · part de la sélection 23.1 % (n=205)
✅ **Études Polymarket** : 0 échec(s) (il y a 14.9h)
✅ **Taille du dépôt** : 0.18 Go (marge 3.82 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
