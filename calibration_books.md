# Les bookmakers sont-ils bien calibrés sur le tennis ?

*Mesuré sur 2190 matchs dénoués. Mise à jour du 2026-10-26.*

Quand une cote implique 30 % de chances, le joueur gagne-t-il vraiment 30 % du temps ? Les probabilités ci-dessous sont **dévigées** : la marge de l'opérateur est retirée, sinon on mesurerait surtout ce qu'il prélève.

| Probabilité annoncée | Observé | Écart | n |
|---|---:|---:|---:|
| 0 – 15 % | 6.5 % | -3.6 pts | 170 |
| 15 – 30 % | 23.3 % | -0.5 pts | 593 |
| 30 – 45 % | 39.6 % | +1.9 pts | 1099 |
| 45 – 55 % | 50.0 % | +0.0 pts | 656 |
| 55 – 70 % | 60.4 % | -1.9 pts | 1099 |
| 70 – 85 % | 76.7 % | +0.5 pts | 593 |
| 85 – 100 % | 93.5 % | +3.6 pts | 170 |

## Qualité prédictive par opérateur

| Opérateur | Score de Brier | n |
|---|---:|---:|
| pinnacle | 0.2102 | 4000 |
| unibet | 0.2102 | 4000 |

Le **score de Brier** mesure la qualité d'une prédiction probabiliste : 0,25 correspond à un pile ou face, plus bas est meilleur. Il ne dépend d'aucun découpage en tranches. Échantillon commun : 2000 matchs cotés par tous les opérateurs listés.

---

Un écart de calibration n'est pas exploitable tel quel : la marge de l'opérateur l'absorbe. C'est une information sur la qualité de ce que vous achetez, pas sur un rendement.

18+ · Jouer comporte des risques · joueurs-info-service.fr
