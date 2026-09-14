# Les bookmakers sont-ils bien calibrés sur le tennis ?

*Mesuré sur 1415 matchs dénoués. Mise à jour du 2026-09-14.*

Quand une cote implique 30 % de chances, le joueur gagne-t-il vraiment 30 % du temps ? Les probabilités ci-dessous sont **dévigées** : la marge de l'opérateur est retirée, sinon on mesurerait surtout ce qu'il prélève.

| Probabilité annoncée | Observé | Écart | n |
|---|---:|---:|---:|
| 0 – 15 % | 9.3 % | -1.1 pts | 107 |
| 15 – 30 % | 21.2 % | -2.3 pts | 386 |
| 30 – 45 % | 39.7 % | +1.8 pts | 716 |
| 45 – 55 % | 50.0 % | +0.0 pts | 412 |
| 55 – 70 % | 60.3 % | -1.8 pts | 716 |
| 70 – 85 % | 78.8 % | +2.3 pts | 386 |
| 85 – 100 % | 90.7 % | +1.1 pts | 107 |

## Qualité prédictive par opérateur

| Opérateur | Score de Brier | n |
|---|---:|---:|
| bwin | 0.2086 | 2570 |
| pinnacle | 0.2092 | 2570 |
| unibet | 0.2092 | 2570 |

Le **score de Brier** mesure la qualité d'une prédiction probabiliste : 0,25 correspond à un pile ou face, plus bas est meilleur. Il ne dépend d'aucun découpage en tranches. Échantillon commun : 1285 matchs cotés par tous les opérateurs listés.

---

Un écart de calibration n'est pas exploitable tel quel : la marge de l'opérateur l'absorbe. C'est une information sur la qualité de ce que vous achetez, pas sur un rendement.

18+ · Jouer comporte des risques · joueurs-info-service.fr
