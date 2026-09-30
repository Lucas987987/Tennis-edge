# État du dernier run — Steam Pipeline

Run démarré `2026-09-30T06:10:12` · terminé `2026-09-30T06:18:00` (UTC)

**Verdict : 2 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 2872 | 286510 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 2835 | 765431 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 172 | 96878 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 49 | 21300 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 28 | 4570 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 302 | 50215 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 382 | 61505 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 351 | 166593 | ⏳ FIGÉ |
| Courbes live reconstruites | `book_curves_live.jsonl` | 3568 | 27973278 | ✅ OK |


**Closings exploitables** : 83 % sur 3 jours (fenêtre t3 : 77 %, n=86) — référence 30 jours 65 % (t3 52 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 20 fichiers, 330.6 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 10.4 % d'écarts > 3 % (117/1121), seuil 30.0 %
**CLV décomposé** : prime +0.93 % · dérive +2.97 % · part de la sélection 23.1 % (n=205)
✅ **Études Polymarket** : 0 échec(s) (il y a 15.4h)
✅ **Taille du dépôt** : 0.18 Go (marge 3.82 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
