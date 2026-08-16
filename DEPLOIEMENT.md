# Lot de correctifs — 16/08/2026

**21 fichiers** : 17 scripts (dont 1 nouveau) + 4 workflows. Tout a été testé sur les vraies données du zip, pas seulement compilé.

---

## 1. `steam_pipeline.yml` produisait du vide chaque nuit

**Symptôme dans le zip** : `moves_detail.csv` et `moves_detail_hist.csv` font 154 octets — uniquement la ligne d'en-tête.

**Cause** : les fichiers plats `*_curves_live.jsonl` sont dans `.gitignore` depuis la migration en partitions live. Ils ne sont reconstruits que par `curves_parts.py rebuild`, appelé **uniquement dans `capture_closing.yml`**. Dans `steam_pipeline.yml` ils sont donc absents au checkout. Chaque script les lisait derrière un garde `if not os.path.exists(): return` → sortie vide, aucun code d'erreur, aucune alerte.

Même famille que les trois crises précédentes : **rien ne plante, tout est vide.**

**Correctifs** :
- Nouveau résolveur `ov.open_curves(path)` dans `oddspapi_v5.py` :
  - nom legacy monolithique (`book_curves.jsonl`…) → partitions `parts/hist_*`
  - plat live absent → `rebuild` automatique depuis `parts/live_*`
  - rien d'exploitable → **`FileNotFoundError` bruyante**, plus jamais de retour vide silencieux
- Appliqué à 14 scripts consommateurs
- Étape `curves_parts.py rebuild` ajoutée en tête de `steam_pipeline.yml`

**Récupéré (mesuré)** :

| Sortie | Avant | Après |
|---|---|---|
| `move_audit` live | 0 move | **56 moves** |
| `move_audit` historique | 0 move | **830 moves** |
| `steam_backtest` | 0 match | **1282 matchs** |
| `canal_recap` | 0 prix suivi | **18 prix suivis** |
| `capture_quality` / `margin_dynamics` / `book_asymmetry` | vide | études complètes |

Les 830 moves reconfirment le résultat central hors échantillon d'origine : CLV médian **+3,0% → +10,9% → +15,9%** quand l'ampleur du mouvement monte.

---

## 2. Deux sources de résultats mortes → hypothèse gelée n°1 à vide

**Symptôme** : `resultats.json` et `resultats_fast.json` valent `"count": 0` alors qu'ils sont régénérés chaque jour (horodatage du 16/08 dans les fichiers). Ce sont les **deux seuls** fichiers lus par `calibration_buckets.py` et `opening_value.py` → `calibration_buckets_report.json` = `{"status": "no_results"}`.

C'est la source de l'**hypothèse gelée n°1** (calibration 2,20-3,50, résidu +5,8 pts) : elle ne tournait plus du tout.

Pendant ce temps `resultats_oddspapi.json` (1057) et `set_results.json` (1762) sont pleins.

**Correctif** : nouveau `scripts/results_bridge.py` → `resultats_derived.json`, **1716 résultats exploitables**. Câblé via `RESULTS=` dans les deux workflows. Sort en erreur si les deux sources sont vides (jamais de succès silencieux).

**À investiguer séparément** : pourquoi `update_results_fast.yml` (2×/jour) produit 0 ? Pour Sackmann la cause est connue (egress bloqué sur le runner), pas pour celui-là.

---

## 3. `opening_value.py` — biais de sélection sur le futur ⚠️

L'ancienne version comparait la cote d'**ouverture** d'un book au juste prix de **clôture** de Pinnacle, puis ne gardait que les ouvertures dont l'EV dépassait 2%. Elle sélectionnait donc les prix ayant bougé favorablement **en le sachant après coup**. Aucune de ces mises n'est plaçable : à l'ouverture, la clôture n'existe pas encore.

**Le tell** : Pinnacle lui-même ressortait « ouverture molle rentable » à **+30,1% de ROI, IC95 [+12,6 ; +47,5]**. Impossible pour un book sharp contre son propre closing.

**Correctif** : `OPENING_VALUE_MODE=prospective` (nouveau défaut) — la référence est Pinnacle **à l'instant où le book ouvre** (dernier point ≤ t_ouverture). Toute l'information utilisée est disponible au moment de miser. Le mode `close` reste accessible pour diagnostic, avec avertissement explicite en tête de sortie.

**Effet — le biais s'effondre** :

| Book | Avant (biaisé) | Après (prospectif) |
|---|---|---|
| unibet | 208 sélections, **+36,6%** IC [+15,0 ; +58,2] | 11 sélections, +19,0% IC [-70,6 ; +108,6] |
| pinnacle | 381 sélections, **+30,1%** IC [+12,6 ; +47,5] | 33 sélections, +22,2% IC [-32,2 ; +76,5] |
| bwin | — | 11 sélections, -75,0% |

**Plus aucun IC n'exclut zéro.** Conclusion propre : aucun edge d'ouverture molle démontré. Bon matériau pour la série « ce qui ne marche pas » — et un deuxième exemple concret de look-ahead à ajouter au fil épinglé.

Les matchs où Pinnacle n'a pas encore ouvert sont désormais **exclus** (aucune référence disponible) : ce sous-ensemble est exactement l'objet de l'hypothèse gelée n°6, à traiter là-bas.

**Note sur le contrôle Pinnacle** : les 33 sélections restantes viennent de l'écart entre `clv_history.jsonl` et `book_curves` (deux sources qui ne voient pas le même prix au même instant — anomalie déjà documentée dans `capture_quality`). À traiter comme un **plancher de bruit** : aucun book ne devrait être considéré comme porteur d'un signal en dessous de ce niveau.

---

## 4. Correctifs mineurs

- `move_anatomy.py` — dépaquetage strict `for t, p in curve_raw` (bug latent jamais repéré, absent du dernier audit)
- `book_asymmetry.py` — idem, 2 sites
- `identify_set_markets.py`, `inplay_setone.py` — les 3 derniers scripts legacy du récap sont fermés
- `etudes_move.yml` — l'avertissement « ces 3 étapes risquent de ne plus rien trouver » est levé

---

## Ordre de déploiement

1. `scripts/oddspapi_v5.py` **en premier** (les autres en dépendent)
2. `scripts/results_bridge.py` (nouveau fichier)
3. Les 15 autres scripts
4. Les 4 workflows
5. Lancer `Opening Value` et `Calibration Buckets` à la main pour vérifier
6. Vérifier au prochain `Steam Pipeline` nocturne que `moves_detail.csv` fait bien plus de 154 octets

## Point de vigilance

Le suivi de **limite de mise Pinnacle** a disparu des données : `curves_parts.py` et `build_live_curves.py` n'émettent que `[t, prix]`, et sur les partitions historiques seules 683 courbes sur 8249 ont un `limit_open` non nul. `historical_curves(..., with_limit=True)` existe toujours dans `oddspapi_v5.py`. La fonctionnalité s'est perdue dans une migration — à décider : la remettre en service, ou l'abandonner explicitement.
