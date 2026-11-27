# État du dernier run — Steam Pipeline

Run démarré `2026-11-20T11:35:12` · terminé `2026-11-27T19:18:48` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 4013 | 398661 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3932 | 1050391 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 328 | 178827 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 121 | 59826 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 30 | 5448 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 3532 | 598425 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 807 | 131030 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 766 | 396536 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 2838 | 20948711 | ✅ OK |


**Closings exploitables** : 97 % sur 3 jours (fenêtre t3 : 91 %, n=96) — référence 30 jours 93 % (t3 84 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 107 fichiers, 959.8 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 7.7 % d'écarts > 3 % (224/2910), seuil 30.0 %
**CLV décomposé** : prime +2.06 % · dérive +2.33 % · part de la sélection 43.0 % (n=3031)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 5.2h)
✅ **Taille du dépôt** : 0.49 Go (marge 3.51 Go)

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
