# État du dernier run — Steam Pipeline

Run démarré `2026-10-06T06:24:54` · terminé `2026-10-06T06:52:34` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3205 | 319179 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3070 | 824296 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 187 | 104980 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 50 | 21850 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 54 | 9179 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 1733 | 295163 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 460 | 74198 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 403 | 196180 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 4805 | 47412045 | ✅ OK |


**Closings exploitables** : 86 % sur 3 jours (fenêtre t3 : 77 %, n=168) — référence 30 jours 79 % (t3 72 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 67 fichiers, 546.2 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 13.6 % d'écarts > 3 % (128/941), seuil 30.0 %
**CLV décomposé** : prime +1.11 % · dérive +2.48 % · part de la sélection 27.9 % (n=1335)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.2h)
✅ **Taille du dépôt** : 4.45 Go (marge 0.55 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
