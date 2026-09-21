# Les bookmakers sont-ils bien calibrés sur le tennis ?

*Mesuré sur 1551 matchs dénoués. Mise à jour du 2026-09-21.*

Quand une cote implique 30 % de chances, le joueur gagne-t-il vraiment 30 % du temps ? Les probabilités ci-dessous sont **dévigées** : la marge de l'opérateur est retirée, sinon on mesurerait surtout ce qu'il prélève.

| Probabilité annoncée | Observé | Écart | n |
|---|---:|---:|---:|
| 0 – 15 % | 6.2 % | -3.9 pts | 112 |
| 15 – 30 % | 22.1 % | -1.5 pts | 426 |
| 30 – 45 % | 39.2 % | +1.4 pts | 790 |
| 45 – 55 % | 50.0 % | +0.0 pts | 446 |
| 55 – 70 % | 60.8 % | -1.4 pts | 790 |
| 70 – 85 % | 77.9 % | +1.5 pts | 426 |
| 85 – 100 % | 93.8 % | +3.9 pts | 112 |

## Qualité prédictive par opérateur

| Opérateur | Score de Brier | n |
|---|---:|---:|
| bwin | 0.2065 | 2852 |
| unibet | 0.2071 | 2852 |
| pinnacle | 0.2072 | 2852 |

Le **score de Brier** mesure la qualité d'une prédiction probabiliste : 0,25 correspond à un pile ou face, plus bas est meilleur. Il ne dépend d'aucun découpage en tranches. Échantillon commun : 1426 matchs cotés par tous les opérateurs listés.

---

Un écart de calibration n'est pas exploitable tel quel : la marge de l'opérateur l'absorbe. C'est une information sur la qualité de ce que vous achetez, pas sur un rendement.

18+ · Jouer comporte des risques · joueurs-info-service.fr
