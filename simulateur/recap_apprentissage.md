# Récapitulatif de l’apprentissage — 2026-W46

Généré le 2026-11-14T13:02:36+00:00 · état **a_verifier**.

> Lecture seule des rapports hebdomadaires. Les populations restent séparées ; aucune adoption nouvelle n’est déclenchée par ce document et aucun gain de ROI n’est déduit.

## En bref

- **Facteurs adoptés** : Adversaires communs, Contexte du tournoi, Durée, Face-à-face, Forme et fatigue, Matchup, Morphologie, Points importants, Pression, Profil de réaction, Styles, Vitesse du court, voyage.
- **Candidats encore en attente** : dotation.
- **Apprentissage sur nos propres pronostics** : non_adopte — 1139/400 matchs documentés ; en attente : 8 nouveaux matchs depuis le dernier jugement (il en faut 30)
- **Pronostics récents évalués** : 886 matchs ; exactitude de la combinaison 65.24 %.
- **Dérive** : accumulation ; 0 alerte(s).
- **Champion modifié cette semaine** : oui.

## Facteurs : apprentissage et jugement

Effectifs : **6949** matchs d’apprentissage et **2681** matchs de jugement.

| Mesure sur le jugement | Avant | Après | Variation favorable |
|---|---:|---:|---:|
| Log loss | 0.62849 | 0.61631 | 0.01218 |
| Exactitude | 64.9 % | 65.7 % | 0.8 point(s) |

La log loss est plus faible quand elle est meilleure. Ce avant/après appartient au jugement des facteurs ; il n’est pas mélangé avec les pronostics récents ci-dessous.

### Groupes non adoptés ou en accumulation

| Groupe | Candidat brut | Statut |
|---|---|---|
| Blessure | non | pas adopté |
| Match Charting | non | pas adopté |
| Conditions | non | pas adopté |
| densite_air | non | pas adopté |
| dotation | oui | candidat (1/2) : adopté s'il fait encore mieux la semaine prochaine |

## Performance des pronostics récents

| Matchs | Log loss | Brier | Exactitude | Score exact | Erreur moyenne de jeux |
|---:|---:|---:|---:|---:|---:|
| 886 | 0.607769 | 0.21128 | 65.24 % | 2.49 % | 4.937259 |

## Recalibrage : décisions séparées

Direct : **890** pronostics sur **4** semaine(s). Rejoué : **5870** pronostics sur **15** semaine(s). Les deux populations ne sont jamais agrégées.

| Population | Méthode | Statut | Gain pondéré de log loss | Fenêtres positives | Adopté |
|---|---|---|---:|---:|---|
| direct | Contraction hiérarchique | accumulation | — | 0/0 | non |
| direct | Isotone | accumulation | — | 0/0 | non |
| direct | Régression logistique | accumulation | — | 0/0 | non |
| rejoue | Contraction hiérarchique | confirmation | -0.002609 | 3/7 | non |
| rejoue | Isotone | confirmation | -0.061443 | 0/7 | non |
| rejoue | Régression logistique | confirmation | -0.002606 | 2/7 | non |

## Gouvernance, dérive et champion

- **Gouvernance** : a_verifier.
- **Promotions retenues** : aucune.
- **Promotions différées** : aucune.
- **Dérive** : accumulation, sur 886 matchs ; alertes : aucune.
- **Empreinte du champion** : `4bc0859a8dcbc7b674d7bb995c52854692754f48e9275f30c1b804b8e677ae29`.
- **Sources manquantes** : aucune.

Ce récapitulatif décrit l’apprentissage et ses contrôles. Il ne constitue ni une preuve prospective supplémentaire ni une promesse d’amélioration future des vainqueurs, des scores ou du ROI.
