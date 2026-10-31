# Récapitulatif de l’apprentissage — 2026-W44

Généré le 2026-10-31T20:49:14+00:00 · état **partiel**.

> Lecture seule des rapports hebdomadaires. Les populations restent séparées ; aucune adoption nouvelle n’est déclenchée par ce document et aucun gain de ROI n’est déduit.

## En bref

- **Facteurs adoptés** : Contexte du tournoi, Face-à-face, Forme et fatigue, Morphologie, Points importants, Styles, Vitesse du court.
- **Candidats encore en attente** : Adversaires communs, Matchup.
- **Apprentissage sur nos propres pronostics** : non_adopte — 507/400 matchs documentés ; en attente : 26 nouveaux matchs depuis le dernier jugement (il en faut 30)
- **Pronostics récents évalués** : — matchs ; exactitude de la combinaison —.
- **Dérive** : indisponible ; 0 alerte(s).
- **Champion modifié cette semaine** : oui.

## Facteurs : apprentissage et jugement

Effectifs : **6183** matchs d’apprentissage et **2398** matchs de jugement.

| Mesure sur le jugement | Avant | Après | Variation favorable |
|---|---:|---:|---:|
| Log loss | 0.62627 | 0.61354 | 0.01273 |
| Exactitude | 65.6 % | 66.4 % | 0.8 point(s) |

La log loss est plus faible quand elle est meilleure. Ce avant/après appartient au jugement des facteurs ; il n’est pas mélangé avec les pronostics récents ci-dessous.

### Groupes non adoptés ou en accumulation

| Groupe | Candidat brut | Statut |
|---|---|---|
| Adversaires communs | oui | candidat (1/2) : adopté s'il fait encore mieux la semaine prochaine |
| Blessure | non | pas adopté |
| Match Charting | non | pas adopté |
| Conditions | non | pas adopté |
| Durée | non | pas adopté |
| Matchup | oui | candidat (1/2) : adopté s'il fait encore mieux la semaine prochaine |
| Pression | non | pas adopté |

## Performance des pronostics récents

| Matchs | Log loss | Brier | Exactitude | Score exact | Erreur moyenne de jeux |
|---:|---:|---:|---:|---:|---:|
| — | — | — | — | — | — |

## Recalibrage : décisions séparées

Direct : **159** pronostics sur **2** semaine(s). Rejoué : **4821** pronostics sur **13** semaine(s). Les deux populations ne sont jamais agrégées.

| Population | Méthode | Statut | Gain pondéré de log loss | Fenêtres positives | Adopté |
|---|---|---|---:|---:|---|
| direct | Contraction hiérarchique | accumulation | — | 0/0 | non |
| direct | Isotone | accumulation | — | 0/0 | non |
| direct | Régression logistique | accumulation | — | 0/0 | non |
| rejoue | Contraction hiérarchique | confirmation | -0.000964 | 1/6 | non |
| rejoue | Isotone | confirmation | -0.066334 | 0/6 | non |
| rejoue | Régression logistique | confirmation | -0.003102 | 1/6 | non |

## Gouvernance, dérive et champion

- **Gouvernance** : ok.
- **Promotions retenues** : aucune.
- **Promotions différées** : aucune.
- **Dérive** : indisponible, sur — matchs ; alertes : aucune.
- **Empreinte du champion** : `6b0eaca6d7a10f2e4a917bf2a60bc435dd06bc05e6be7badab2a8a969d1d153c`.
- **Sources manquantes** : derive, evaluation.

Ce récapitulatif décrit l’apprentissage et ses contrôles. Il ne constitue ni une preuve prospective supplémentaire ni une promesse d’amélioration future des vainqueurs, des scores ou du ROI.
