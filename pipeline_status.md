# État du dernier run — Steam Pipeline

Run démarré `2026-11-02T06:12:44` · terminé `2026-11-02T07:12:28` (UTC)

**Verdict : 1 livrable(s) à vérifier**

| Livrable | Fichier | Lignes | Octets | État |
|---|---|---:|---:|---|
| Résultats match + set | `set_results.json` | 3855 | 383193 | ✅ OK |
| Pont résultats (études) | `resultats_derived.json` | 3806 | 1018777 | ✅ OK |
| Journal forward — match | `paper_trades_match.jsonl` | 242 | 133775 | ✅ OK |
| Journal forward — set 1 | `paper_trades_set1.jsonl` | 70 | 35961 | ✅ OK |
| Journal forward — set 2 | `paper_trades_set2.jsonl` | 0 | 0 | ⚠️ VIDE |
| Audit des moves (live) | `moves_detail.csv` | 74 | 11951 | ✅ OK |
| Audit des moves (historique) | `moves_detail_hist.csv` | 2897 | 490872 | ✅ OK |
| CLV réalisé du canal public | `canal_clv_detail.csv` | 600 | 97121 | ✅ OK |
| Journal du canal public | `canal_public_log.jsonl` | 586 | 297548 | ✅ OK |
| Courbes live reconstruites | `book_curves_live.jsonl` | 5775 | 42853716 | ✅ OK |


**Closings exploitables** : 97 % sur 3 jours (fenêtre t3 : 90 %, n=174) — référence 30 jours 93 % (t3 80 %). C'est le dénominateur du CLV : un match sans closing fiable ne valide ni ne réfute rien.
**Partitions** : 89 fichiers, 692.8 Mo — ⚠️ **vue partielle** (sparse-checkout : pm_ticks/kx_ticks absents de ce run). La taille réelle du dépôt est celle de la sentinelle ci-dessous, pas celle-ci.

✅ **Qualité de clôture (Q3)** : 8.7 % d'écarts > 3 % (170/1948), seuil 30.0 %
**CLV décomposé** : prime +2.22 % · dérive +2.33 % · part de la sélection 43.5 % (n=2472)
✅ **Études Polymarket** : 0 échec(s) · 2 avertissement(s) (info) (il y a 19.7h)
🔴 **Taille du dépôt** : 6.62 Go -- SEUIL FRANCHI (alarme 4.0 Go, zone GitHub ~5 Go) -- SEUIL FRANCHI — ne PAS réécrire l'historique (force-push interdit). Poursuivre la migration R2 (README_MIGRATION_R2.md) ; « nouveau dépôt propre » à planifier plus tard, à froid.

Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit (le script n'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.
