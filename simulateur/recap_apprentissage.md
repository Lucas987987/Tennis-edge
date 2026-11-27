# Récapitulatif de l’apprentissage — 2026-W48

Généré le 2026-11-27T13:43:19+00:00 · état **a_verifier**.

> Lecture seule des rapports hebdomadaires. Les populations restent séparées ; aucune adoption nouvelle n’est déclenchée par ce document et aucun gain de ROI n’est déduit.

## En bref

- **Facteurs adoptés** : Adversaires communs, Conditions, Contexte du tournoi, dotation, Durée, Face-à-face, Forme et fatigue, Matchup, Morphologie, Points importants, Pression, Profil de réaction, Styles, Vitesse du court, voyage.
- **Candidats encore en attente** : Aucun.
- **Apprentissage sur nos propres pronostics** : non_adopte — 1786/400 matchs documentés ; en attente : 0 nouveaux matchs depuis le dernier jugement (il en faut 30)
- **Pronostics récents évalués** : 1754 matchs ; exactitude de la combinaison 66.93 %.
- **Dérive** : surveillance ; 0 alerte(s).
- **Champion modifié cette semaine** : oui.

## Facteurs : apprentissage et jugement

Effectifs : **8005** matchs d’apprentissage et **2596** matchs de jugement.

| Mesure sur le jugement | Avant | Après | Variation favorable |
|---|---:|---:|---:|
| Log loss | 0.6335 | 0.61779 | 0.01571 |
| Exactitude | 64.4 % | 66.2 % | 1.8 point(s) |

La log loss est plus faible quand elle est meilleure. Ce avant/après appartient au jugement des facteurs ; il n’est pas mélangé avec les pronostics récents ci-dessous.

### Groupes non adoptés ou en accumulation

| Groupe | Candidat brut | Statut |
|---|---|---|
| Blessure | non | pas adopté (cumul : gain -0.0000 ± 0.0000, garde -0.0003 ± 0.0002, sur 3070 matchs ; il en faut 300 et 2 erreurs types) |
| Match Charting | non | pas adopté (cumul : gain -0.0000 ± 0.0000, garde -0.0001 ± 0.0004, sur 3070 matchs ; il en faut 300 et 2 erreurs types) |
| densite_air | non | pas adopté (cumul : gain +0.0000 ± 0.0000, garde -0.0001 ± 0.0000, sur 3070 matchs ; il en faut 300 et 2 erreurs types) |

## Performance des pronostics récents

| Matchs | Log loss | Brier | Exactitude | Score exact | Erreur moyenne de jeux |
|---:|---:|---:|---:|---:|---:|
| 1754 | 0.594498 | 0.205267 | 66.93 % | 3.03 % | 4.844743 |

## Recalibrage : décisions séparées

Direct : **1758** pronostics sur **6** semaine(s). Rejoué : **6841** pronostics sur **17** semaine(s). Les deux populations ne sont jamais agrégées.

| Population | Méthode | Statut | Gain pondéré de log loss | Fenêtres positives | Adopté |
|---|---|---|---:|---:|---|
| direct | Contraction hiérarchique | accumulation | -0.015882 | 0/1 | non |
| direct | Isotone | accumulation | -0.072072 | 0/1 | non |
| direct | Régression logistique | accumulation | -2e-06 | 0/1 | non |
| rejoue | Contraction hiérarchique | confirmation | -0.002007 | 4/8 | non |
| rejoue | Isotone | confirmation | -0.052528 | 0/8 | non |
| rejoue | Régression logistique | confirmation | -0.002082 | 3/8 | non |

## Gouvernance, dérive et champion

- **Gouvernance** : a_verifier.
- **Promotions retenues** : aucune.
- **Promotions différées** : aucune.
- **Dérive** : surveillance, sur 1754 matchs ; alertes : aucune.
- **Empreinte du champion** : `9ae2e641adf8c1485652a022d6811bd5455869473f2cb85a6fa865d271abb61a`.
- **Sources manquantes** : aucune.

Ce récapitulatif décrit l’apprentissage et ses contrôles. Il ne constitue ni une preuve prospective supplémentaire ni une promesse d’amélioration future des vainqueurs, des scores ou du ROI.
