# Récapitulatif de l’apprentissage — 2026-W45

Généré le 2026-11-04T13:43:50+00:00 · état **ok**.

> Lecture seule des rapports hebdomadaires. Les populations restent séparées ; aucune adoption nouvelle n’est déclenchée par ce document et aucun gain de ROI n’est déduit.

## En bref

- **Facteurs adoptés** : Adversaires communs, Contexte du tournoi, Face-à-face, Forme et fatigue, Matchup, Morphologie, Points importants, Styles, Vitesse du court.
- **Candidats encore en attente** : Durée, Pression, Profil de réaction.
- **Apprentissage sur nos propres pronostics** : non_adopte — 795/400 matchs documentés ; en attente : 6 nouveaux matchs depuis le dernier jugement (il en faut 30)
- **Pronostics récents évalués** : 787 matchs ; exactitude de la combinaison 66.45 %.
- **Dérive** : accumulation ; 0 alerte(s).
- **Champion modifié cette semaine** : oui.

## Facteurs : apprentissage et jugement

Effectifs : **6734** matchs d’apprentissage et **2597** matchs de jugement.

| Mesure sur le jugement | Avant | Après | Variation favorable |
|---|---:|---:|---:|
| Log loss | 0.62766 | 0.61625 | 0.01141 |
| Exactitude | 64.9 % | 66.2 % | 1.3 point(s) |

La log loss est plus faible quand elle est meilleure. Ce avant/après appartient au jugement des facteurs ; il n’est pas mélangé avec les pronostics récents ci-dessous.

### Groupes non adoptés ou en accumulation

| Groupe | Candidat brut | Statut |
|---|---|---|
| Blessure | non | pas adopté |
| Match Charting | non | pas adopté |
| Conditions | non | pas adopté |
| Durée | oui | candidat (1/2) : adopté s'il fait encore mieux la semaine prochaine |
| Pression | oui | candidat (1/2) : adopté s'il fait encore mieux la semaine prochaine |
| Profil de réaction | oui | candidat (1/2) : adopté s'il fait encore mieux la semaine prochaine |

## Performance des pronostics récents

| Matchs | Log loss | Brier | Exactitude | Score exact | Erreur moyenne de jeux |
|---:|---:|---:|---:|---:|---:|
| 787 | 0.60906 | 0.211389 | 66.45 % | 2.97 % | 4.922222 |

## Recalibrage : décisions séparées

Direct : **792** pronostics sur **3** semaine(s). Rejoué : **5571** pronostics sur **14** semaine(s). Les deux populations ne sont jamais agrégées.

| Population | Méthode | Statut | Gain pondéré de log loss | Fenêtres positives | Adopté |
|---|---|---|---:|---:|---|
| direct | Contraction hiérarchique | accumulation | — | 0/0 | non |
| direct | Isotone | accumulation | — | 0/0 | non |
| direct | Régression logistique | accumulation | — | 0/0 | non |
| rejoue | Contraction hiérarchique | confirmation | -0.002785 | 3/6 | non |
| rejoue | Isotone | confirmation | -0.069134 | 0/6 | non |
| rejoue | Régression logistique | confirmation | -0.002715 | 1/6 | non |

## Gouvernance, dérive et champion

- **Gouvernance** : ok.
- **Promotions retenues** : aucune.
- **Promotions différées** : aucune.
- **Dérive** : accumulation, sur 787 matchs ; alertes : aucune.
- **Empreinte du champion** : `6e751f4a428aebf4ad1450d9b6f4f6276f5ea053709ca1d07258b4f72619f286`.
- **Sources manquantes** : aucune.

Ce récapitulatif décrit l’apprentissage et ses contrôles. Il ne constitue ni une preuve prospective supplémentaire ni une promesse d’amélioration future des vainqueurs, des scores ou du ROI.
