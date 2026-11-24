# Récapitulatif de l’apprentissage — 2026-W48

Généré le 2026-11-24T13:15:53+00:00 · état **a_verifier**.

> Lecture seule des rapports hebdomadaires. Les populations restent séparées ; aucune adoption nouvelle n’est déclenchée par ce document et aucun gain de ROI n’est déduit.

## En bref

- **Facteurs adoptés** : Adversaires communs, Conditions, Contexte du tournoi, dotation, Durée, Face-à-face, Forme et fatigue, Matchup, Morphologie, Points importants, Pression, Profil de réaction, Styles, Vitesse du court, voyage.
- **Candidats encore en attente** : Blessure, Match Charting.
- **Apprentissage sur nos propres pronostics** : non_adopte — 1650/400 matchs documentés ; en attente : 1 nouveaux matchs depuis le dernier jugement (il en faut 30)
- **Pronostics récents évalués** : 1588 matchs ; exactitude de la combinaison 66.31 %.
- **Dérive** : surveillance ; 0 alerte(s).
- **Champion modifié cette semaine** : oui.

## Facteurs : apprentissage et jugement

Effectifs : **7808** matchs d’apprentissage et **2602** matchs de jugement.

| Mesure sur le jugement | Avant | Après | Variation favorable |
|---|---:|---:|---:|
| Log loss | 0.63518 | 0.62026 | 0.01492 |
| Exactitude | 63.8 % | 65.2 % | 1.4 point(s) |

La log loss est plus faible quand elle est meilleure. Ce avant/après appartient au jugement des facteurs ; il n’est pas mélangé avec les pronostics récents ci-dessous.

### Groupes non adoptés ou en accumulation

| Groupe | Candidat brut | Statut |
|---|---|---|
| Blessure | oui | pas adopté (cumul : gain -0.0000 ± 0.0000, garde -0.0003 ± 0.0002, sur 2933 matchs ; il en faut 300 et 2 erreurs types) |
| Match Charting | oui | pas adopté (cumul : gain -0.0000 ± 0.0000, garde -0.0001 ± 0.0004, sur 2933 matchs ; il en faut 300 et 2 erreurs types) |
| densite_air | non | pas adopté (cumul : gain +0.0000 ± 0.0000, garde -0.0001 ± 0.0000, sur 2933 matchs ; il en faut 300 et 2 erreurs types) |

## Performance des pronostics récents

| Matchs | Log loss | Brier | Exactitude | Score exact | Erreur moyenne de jeux |
|---:|---:|---:|---:|---:|---:|
| 1588 | 0.600838 | 0.20798 | 66.31 % | 2.97 % | 4.898043 |

## Recalibrage : décisions séparées

Direct : **1592** pronostics sur **6** semaine(s). Rejoué : **6650** pronostics sur **17** semaine(s). Les deux populations ne sont jamais agrégées.

| Population | Méthode | Statut | Gain pondéré de log loss | Fenêtres positives | Adopté |
|---|---|---|---:|---:|---|
| direct | Contraction hiérarchique | accumulation | -0.015882 | 0/1 | non |
| direct | Isotone | accumulation | -0.072072 | 0/1 | non |
| direct | Régression logistique | accumulation | -2e-06 | 0/1 | non |
| rejoue | Contraction hiérarchique | confirmation | -0.002123 | 4/8 | non |
| rejoue | Isotone | confirmation | -0.05417 | 0/8 | non |
| rejoue | Régression logistique | confirmation | -0.002234 | 2/8 | non |

## Gouvernance, dérive et champion

- **Gouvernance** : a_verifier.
- **Promotions retenues** : aucune.
- **Promotions différées** : aucune.
- **Dérive** : surveillance, sur 1588 matchs ; alertes : aucune.
- **Empreinte du champion** : `e32b8d35c62855f1633f53459aef71bae5e4d941b2e3fb09f98e1f3e89c5e491`.
- **Sources manquantes** : aucune.

Ce récapitulatif décrit l’apprentissage et ses contrôles. Il ne constitue ni une preuve prospective supplémentaire ni une promesse d’amélioration future des vainqueurs, des scores ou du ROI.
