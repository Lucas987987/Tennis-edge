# Correctif du 12/09/2026 — look-ahead sur l'ampleur, et P9 muette

## 1. Ce qui a été trouvé

### 1.1 `mag_cote_pct` contenait la clôture Pinnacle

Dans `move_audit.py`, la colonne était calculée ainsi :

    mag_odds = (o_open - o_close) / o_open

`o_close` est la cote Pinnacle **de clôture**. La colonne sortait pourtant sous
un nom neutre, sans le suffixe `_POSTHOC` qui protège déjà `mag_proba_pts`. Deux
consommateurs s'en servaient comme **critère d'entrée** :

- `validation_report.py` → hypothèse gelée H14 (« mouvement Pinnacle > 5 % »)
- `pistes_common.charge_moves()` → clé `mag`, utilisée par les pistes qui
  segmentent par ampleur (P5 retournements, P1 limites)

L'audit du 06/09 avait repéré le problème et l'avait documenté en commentaire
comme « limite connue ». Ce n'est pas une limite : une règle qui lit la clôture
ne peut être appliquée par aucun détecteur temps réel. Elle ne se valide pas.

Mesuré sur `moves_detail_hist.csv` (n=1296, 07/06 → 11/09) :

    corr(ampleur à la détection, ampleur finale) = 0,21

Ce ne sont pas deux mesures de la même grandeur.

**Effet sur les résultats.** Sur les données post-gel (26/08 → 11/09) :

| règle | n | CLV>0 | ROI |
|---|---|---|---|
| témoin (tous les moves) | 353 | 66,3 % [61 ; 71] | +2,1 % |
| H14 telle que codée (`mag_cote_pct > 5`) | 92 | **87,0 %** [79 ; 92] | +34,8 % |
| H14 sur l'ampleur à la détection | 45 | 71,1 % [**57 ; 82**] | +14,1 % |
| fenêtre 8-24 h seule, sans critère d'ampleur | 177 | 61,6 % [54 ; 68] | +17,8 % |

Une fois le critère rendu causal, H14 ne se sépare plus du témoin (IC
recouvrants) et son ROI est entièrement absorbé par la fenêtre horaire seule.

Même chose pour P5 : l'écart spectaculaire par tranche d'ampleur
(44,6 % vs 82,0 % de CLV>0) tombe à 65,2 % vs 70,7 %, IC recouvrants, dès que
l'ampleur est mesurée à `t_det`.

### 1.2 La note de fiabilité (P9) n'était jamais écrite

`paper_journal.py` calculait `fiabilite_score` **uniquement dans la branche
`BACKFILL`**, qui ne persiste rien par construction. La branche forward, seule à
appeler `save_journal()`, ne l'écrivait pas.

Constaté sur le journal réel : **0 trade sur 69** portait un score, 17 jours
après l'activation du 26/08. `shadow_sizing_study.py` se contentait d'afficher
« trop tôt » — la piste ne pouvait pas atteindre son n, et rien ne le signalait.

### 1.3 Le composant `book_en_retard` se déclenchait toujours

Dans la branche backfill :

    edge_pct = (sig['odds'] * (sig.get('pct') or 0) - 1) * 100

`pct` est un **pourcentage entier** de réussite historique (53, 64, 80…), pas une
probabilité. Le produit dépassait 3 % dans tous les cas.

Vérifié sur `paper_trades_match.jsonl` : l'ancienne formule renvoie ≥ 3 % sur
**53/53** des paris où `pct` est renseigné, et rien sur les 16 où il vaut 0. Le
composant ne mesurait pas un retard de book — il mesurait si le book avait un
track record.

## 2. Ce qui a été changé

### `scripts/move_audit.py`
- ajout de `o_det` et `mag_odds_det` : le raccourcissement déjà réalisé à
  `t_det`, ce qu'un détecteur temps réel peut voir.
- `mag_cote_pct` porte désormais la valeur **causale** ;
  `mag_cote_pct_POSTHOC` porte la rétrospective, suivant la convention déjà en
  place pour `mag_proba_pts` / `mag_proba_pts_POSTHOC`.
- la présence de `mag_cote_pct_POSTHOC` dans l'en-tête sert de **marqueur de
  version** du CSV.
- bins du tableau d'affichage redécoupés (0-3/3-6/6-10/10-20/20 %+) :
  l'ancien découpage, taillé pour l'ampleur rétrospective, mettait tout dans la
  première tranche. Descriptif uniquement, aucun critère n'en dépend.

### `scripts/pistes_common.py` et `scripts/validation_report.py`
Garde de version dans `charge_moves()` et `roi_ampli_watch()` : un CSV sans la
colonne `_POSTHOC` est antérieur au correctif, on **refuse** de le lire. Un
fallback silencieux redonnerait les chiffres gonflés sans que personne ne le
voie.

### `scripts/validation_report.py` — H14 regelée
- `FREEZE_DATE_AMPLI` = `2026-09-12`, `FREEZE_DATE_AMPLI_V1` = `2026-09-07`
  conservée comme gel **invalidé**.
- seuil 5 %, fenêtre 8-24 h, books : **repris à l'identique**. Ne rien
  réoptimiser est délibéré — réajuster le seuil « pour retrouver le volume »
  rouvrirait l'espace de recherche de 448 combinaisons que le gel du 07/09 avait
  fermé. Le volume baisse, c'est une conséquence de la correction, pas un choix.
- les chiffres fondateurs cités dans la docstring (A n=275 ROI +20,9 %, B, C)
  sont marqués comme issus du critère contaminé : ils gardent leur valeur de
  trace du raisonnement A vs B vs C, plus aucune comme mesures.

### `scripts/paper_journal.py`
- `fiabilite_score` + `fiabilite_detail` écrits dans la branche **forward**,
  juste après la création du trade.
- `lead_min` mesuré par rapport à `now` et non à `t_e` : en forward l'entrée est
  prise au dernier point disponible (`entry_at='now'`), donc `now` est bien
  l'instant du pari. Les deux branches mesurent la même chose.
- `book_en_retard` basé sur `sig['ev']` (la vraie EV, `cote × fair − 1`) dans
  les **deux** branches.

## 3. Vérification

`verifier.sh` passe en deux temps, et les deux comptent :

- **A** : les 23 tests sur le code corrigé → doivent passer.
- **B** : les mêmes tests statiques sur une copie re-buggée par
  `tests/rebug_12_09.py` → doivent **échouer** (9 échecs attendus).

Un test qui passe sur du code correct ne prouve rien s'il passe aussi sur du
code buggé.

Les tests fonctionnels (T5–T7) tournent sur de vraies données : une partition
`parts/hist_book_*.jsonl.gz` pour `move_audit.py`, le vrai
`moves_detail_hist.csv` pour les gardes, le vrai `paper_trades_match.jsonl` pour
le bug de `pct`. Aucun cas synthétique.

Résultat du run de validation : `A ✅ · B ✅ · VERDICT ✅`.

## 4. Application

    unzip -o correctif_12_09.zip -d /tmp/correctif
    cp -r /tmp/correctif/scripts/. scripts/
    cp -r /tmp/correctif/tests/. tests/
    cp /tmp/correctif/verifier.sh .
    chmod +x verifier.sh && bash verifier.sh
    # verdict attendu : A ✅  B ✅
    rm -rf /tmp/correctif
    git add -A
    git commit -m "Correctif look-ahead ampleur (move_audit/H14/pistes) + P9 ecrite en forward"
    git pull --no-rebase --no-edit
    git push

## 5. Après application — ce qu'il faut savoir

1. **`moves_detail_hist.csv` doit être régénéré** par `move_audit.py` (il l'est
   à chaque passage de `steam_pipeline`). D'ici là, les gardes font rendre zéro
   ligne aux pistes et `None` à `roi_ampli_watch` — comportement voulu, pas une
   panne. Le message est explicite dans les logs.

2. **H14 repart de n=0** au 12/09. Tout l'historique redevient in-sample. Avec le
   critère causal, le volume dans la zone est plus faible qu'avec l'ancien : le
   « moins de deux mois pour trancher » annoncé dans la docstring n'est plus
   valable, il faudra le recalculer sur quelques semaines de volume réel.

3. **P9 repart aussi de zéro**, mais cette fois elle accumulera. À surveiller au
   prochain passage de `paper_journal` : les nouveaux trades `OPEN` doivent
   porter `fiabilite_score` et `fiabilite_detail`.

4. **Les seuils de la note de fiabilité restent ceux de P5** (+1 si ampleur
   ≥ 6 %, −1 si < 3 %, −1 si lead < 60 min). Ces trois composants viennent de la
   piste que ce correctif vient d'invalider. Le score reste en mode ombre et ne
   pilote rien, donc le journaliser est sans risque — mais un verdict positif
   sur P9 devra être lu en sachant d'où viennent ses seuils. À reprendre quand
   P5 aura été rejouée proprement.

## 6. Hors périmètre (constaté, non corrigé)

- **P7 segments** : post-gel, `segment_circuit()` classe 167 moves sur 180 en
  « autre » — les libellés `tour` ont changé (`US Open Men Singles`,
  `ATP Challenger …`). Aucun verdict de segment n'est lisible tant que ce n'est
  pas corrigé.
- **P2 lead-lag Polymarket** : `polymarket_flow` est sorti du pipeline, la piste
  tourne chaque dimanche sans source. Le substitut Kalshi a rendu son verdict
  (p=0,87, clos).
- **P6 cross-market** : le protocole v2 (témoin apparié) n'a jamais été écrit ;
  le script affiche toujours l'avertissement du confondeur.
- **Taille du dépôt** : 5,04 Go, seuil franchi.
