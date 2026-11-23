# Les bookmakers sont-ils bien calibrés sur le tennis ?

*Mesuré sur 2241 matchs dénoués. Mise à jour du 2026-11-23.*

Quand une cote implique 30 % de chances, le joueur gagne-t-il vraiment 30 % du temps ? Les probabilités ci-dessous sont **dévigées** : la marge de l'opérateur est retirée, sinon on mesurerait surtout ce qu'il prélève.

| Probabilité annoncée | Observé | Écart | n |
|---|---:|---:|---:|
| 0 – 15 % | 6.3 % | -3.8 pts | 174 |
| 15 – 30 % | 23.3 % | -0.5 pts | 606 |
| 30 – 45 % | 39.6 % | +1.9 pts | 1121 |
| 45 – 55 % | 50.0 % | +0.0 pts | 680 |
| 55 – 70 % | 60.4 % | -1.9 pts | 1121 |
| 70 – 85 % | 76.7 % | +0.5 pts | 606 |
| 85 – 100 % | 93.7 % | +3.8 pts | 174 |

## Qualité prédictive par opérateur

| Opérateur | Score de Brier | n |
|---|---:|---:|
| bwin | 0.2098 | 3732 |
| pinnacle | 0.2103 | 3732 |
| unibet | 0.2103 | 3732 |

Le **score de Brier** mesure la qualité d'une prédiction probabiliste : 0,25 correspond à un pile ou face, plus bas est meilleur. Il ne dépend d'aucun découpage en tranches. Échantillon commun : 1866 matchs cotés par tous les opérateurs listés.

---

Un écart de calibration n'est pas exploitable tel quel : la marge de l'opérateur l'absorbe. C'est une information sur la qualité de ce que vous achetez, pas sur un rendement.

18+ · Jouer comporte des risques · joueurs-info-service.fr
