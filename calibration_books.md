# Les bookmakers sont-ils bien calibrés sur le tennis ?

*Mesuré sur 1404 matchs dénoués. Mise à jour du 2026-09-07.*

Quand une cote implique 30 % de chances, le joueur gagne-t-il vraiment 30 % du temps ? Les probabilités ci-dessous sont **dévigées** : la marge de l'opérateur est retirée, sinon on mesurerait surtout ce qu'il prélève.

| Probabilité annoncée | Observé | Écart | n |
|---|---:|---:|---:|
| 0 – 15 % | 8.3 % | -1.7 pts | 109 |
| 15 – 30 % | 24.1 % | +0.8 pts | 394 |
| 30 – 45 % | 40.3 % | +2.4 pts | 699 |
| 45 – 55 % | 50.0 % | +0.0 pts | 404 |
| 55 – 70 % | 59.7 % | -2.4 pts | 699 |
| 70 – 85 % | 75.9 % | -0.8 pts | 394 |
| 85 – 100 % | 91.7 % | +1.7 pts | 109 |

## Qualité prédictive par opérateur

| Opérateur | Score de Brier | n |
|---|---:|---:|
| bwin | 0.2098 | 2536 |
| unibet | 0.2105 | 2536 |
| pinnacle | 0.2106 | 2536 |

Le **score de Brier** mesure la qualité d'une prédiction probabiliste : 0,25 correspond à un pile ou face, plus bas est meilleur. Il ne dépend d'aucun découpage en tranches. Échantillon commun : 1268 matchs cotés par tous les opérateurs listés.

---

Un écart de calibration n'est pas exploitable tel quel : la marge de l'opérateur l'absorbe. C'est une information sur la qualité de ce que vous achetez, pas sur un rendement.

18+ · Jouer comporte des risques · joueurs-info-service.fr
