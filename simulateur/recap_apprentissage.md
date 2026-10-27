# Récapitulatif de l’apprentissage — 2026-W44

Généré le 2026-10-27T23:12:53+00:00 · état **ok**.

> Lecture seule des rapports hebdomadaires. Les populations restent séparées ; aucune adoption nouvelle n’est déclenchée par ce document et aucun gain de ROI n’est déduit.

## En bref

- **Facteurs adoptés** : Contexte du tournoi, Face-à-face, Forme et fatigue, Morphologie, Points importants, Styles, Vitesse du court.
- **Candidats encore en attente** : Adversaires communs, Matchup.
- **Apprentissage sur nos propres pronostics** : accumulation — 140/400 matchs documentés ; en attente : 140 matchs joués avec les deux % (il en faut 400)
- **Pronostics récents évalués** : 150 matchs ; exactitude de la combinaison 63.33 %.
- **Dérive** : accumulation ; 0 alerte(s).
- **Champion modifié cette semaine** : — (initialisation du suivi).

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
| 150 | 0.633311 | 0.223103 | 63.33 % | 3.4 % | 4.909524 |

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
- **Dérive** : accumulation, sur 150 matchs ; alertes : aucune.
- **Empreinte du champion** : `cd5f6330137afe0a82f35629f007cb47a9a941148ccff2ed56b5fbadcae16b8f`.
- **Sources manquantes** : aucune.

Ce récapitulatif décrit l’apprentissage et ses contrôles. Il ne constitue ni une preuve prospective supplémentaire ni une promesse d’amélioration future des vainqueurs, des scores ou du ROI.
