# Récapitulatif de l’apprentissage — 2026-W47

Généré le 2026-11-20T22:59:02+00:00 · état **a_verifier**.

> Lecture seule des rapports hebdomadaires. Les populations restent séparées ; aucune adoption nouvelle n’est déclenchée par ce document et aucun gain de ROI n’est déduit.

## En bref

- **Facteurs adoptés** : Adversaires communs, Conditions, Contexte du tournoi, dotation, Durée, Face-à-face, Forme et fatigue, Matchup, Morphologie, Points importants, Pression, Profil de réaction, Styles, Vitesse du court, voyage.
- **Candidats encore en attente** : Blessure.
- **Apprentissage sur nos propres pronostics** : non_adopte — 1462/400 matchs documentés ; en attente : 19 nouveaux matchs depuis le dernier jugement (il en faut 30)
- **Pronostics récents évalués** : 1244 matchs ; exactitude de la combinaison 65.76 %.
- **Dérive** : accumulation ; 0 alerte(s).
- **Champion modifié cette semaine** : oui.

## Facteurs : apprentissage et jugement

Effectifs : **7417** matchs d’apprentissage et **2606** matchs de jugement.

| Mesure sur le jugement | Avant | Après | Variation favorable |
|---|---:|---:|---:|
| Log loss | 0.63499 | 0.6205 | 0.01449 |
| Exactitude | 63.8 % | 65.2 % | 1.4 point(s) |

La log loss est plus faible quand elle est meilleure. Ce avant/après appartient au jugement des facteurs ; il n’est pas mélangé avec les pronostics récents ci-dessous.

### Groupes non adoptés ou en accumulation

| Groupe | Candidat brut | Statut |
|---|---|---|
| Blessure | oui | pas adopté (cumul : gain -0.0000 ± 0.0000, garde -0.0002 ± 0.0002, sur 2606 matchs ; il en faut 300 et 2 erreurs types) |
| Match Charting | non | pas adopté (cumul : gain -0.0000 ± 0.0000, garde -0.0003 ± 0.0005, sur 2606 matchs ; il en faut 300 et 2 erreurs types) |
| densite_air | non | pas adopté (cumul : gain +0.0000 ± 0.0000, garde -0.0001 ± 0.0000, sur 2606 matchs ; il en faut 300 et 2 erreurs types) |

## Performance des pronostics récents

| Matchs | Log loss | Brier | Exactitude | Score exact | Erreur moyenne de jeux |
|---:|---:|---:|---:|---:|---:|
| 1244 | 0.602667 | 0.209654 | 65.76 % | 2.58 % | 4.914343 |

## Recalibrage : décisions séparées

Direct : **1248** pronostics sur **5** semaine(s). Rejoué : **6263** pronostics sur **16** semaine(s). Les deux populations ne sont jamais agrégées.

| Population | Méthode | Statut | Gain pondéré de log loss | Fenêtres positives | Adopté |
|---|---|---|---:|---:|---|
| direct | Contraction hiérarchique | accumulation | 7.7e-05 | 1/1 | non |
| direct | Isotone | accumulation | -0.031115 | 0/1 | non |
| direct | Régression logistique | accumulation | -0.000106 | 0/1 | non |
| rejoue | Contraction hiérarchique | confirmation | -0.002251 | 4/7 | non |
| rejoue | Isotone | confirmation | -0.05424 | 0/7 | non |
| rejoue | Régression logistique | confirmation | -0.002291 | 2/7 | non |

## Gouvernance, dérive et champion

- **Gouvernance** : a_verifier.
- **Promotions retenues** : aucune.
- **Promotions différées** : aucune.
- **Dérive** : accumulation, sur 1244 matchs ; alertes : aucune.
- **Empreinte du champion** : `83f074f24561196b6a39ee67e3d08e4137f2e3b60092e07dc16e0401516bc836`.
- **Sources manquantes** : aucune.

Ce récapitulatif décrit l’apprentissage et ses contrôles. Il ne constitue ni une preuve prospective supplémentaire ni une promesse d’amélioration future des vainqueurs, des scores ou du ROI.
