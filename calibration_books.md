# Les bookmakers sont-ils bien calibrés sur le tennis ?

*Mesuré sur 1958 matchs dénoués. Mise à jour du 2026-10-19.*

Quand une cote implique 30 % de chances, le joueur gagne-t-il vraiment 30 % du temps ? Les probabilités ci-dessous sont **dévigées** : la marge de l'opérateur est retirée, sinon on mesurerait surtout ce qu'il prélève.

| Probabilité annoncée | Observé | Écart | n |
|---|---:|---:|---:|
| 0 – 15 % | 5.9 % | -4.2 pts | 152 |
| 15 – 30 % | 23.6 % | -0.2 pts | 530 |
| 30 – 45 % | 39.9 % | +2.1 pts | 986 |
| 45 – 55 % | 50.0 % | +0.0 pts | 580 |
| 55 – 70 % | 60.1 % | -2.1 pts | 986 |
| 70 – 85 % | 76.4 % | +0.2 pts | 530 |
| 85 – 100 % | 94.1 % | +4.2 pts | 152 |

## Qualité prédictive par opérateur

| Opérateur | Score de Brier | n |
|---|---:|---:|
| bwin | 0.2091 | 3328 |
| unibet | 0.2094 | 3328 |
| pinnacle | 0.2096 | 3328 |

Le **score de Brier** mesure la qualité d'une prédiction probabiliste : 0,25 correspond à un pile ou face, plus bas est meilleur. Il ne dépend d'aucun découpage en tranches. Échantillon commun : 1664 matchs cotés par tous les opérateurs listés.

---

Un écart de calibration n'est pas exploitable tel quel : la marge de l'opérateur l'absorbe. C'est une information sur la qualité de ce que vous achetez, pas sur un rendement.

18+ · Jouer comporte des risques · joueurs-info-service.fr
