# Les bookmakers sont-ils bien calibrés sur le tennis ?

*Mesuré sur 1704 matchs dénoués. Mise à jour du 2026-10-02.*

Quand une cote implique 30 % de chances, le joueur gagne-t-il vraiment 30 % du temps ? Les probabilités ci-dessous sont **dévigées** : la marge de l'opérateur est retirée, sinon on mesurerait surtout ce qu'il prélève.

| Probabilité annoncée | Observé | Écart | n |
|---|---:|---:|---:|
| 0 – 15 % | 5.6 % | -4.8 pts | 124 |
| 15 – 30 % | 22.2 % | -1.5 pts | 459 |
| 30 – 45 % | 40.2 % | +2.3 pts | 879 |
| 45 – 55 % | 50.0 % | +0.0 pts | 484 |
| 55 – 70 % | 59.8 % | -2.3 pts | 879 |
| 70 – 85 % | 77.8 % | +1.5 pts | 459 |
| 85 – 100 % | 94.4 % | +4.8 pts | 124 |

## Qualité prédictive par opérateur

| Opérateur | Score de Brier | n |
|---|---:|---:|
| bwin | 0.2089 | 3084 |
| unibet | 0.2095 | 3084 |
| pinnacle | 0.2098 | 3084 |

Le **score de Brier** mesure la qualité d'une prédiction probabiliste : 0,25 correspond à un pile ou face, plus bas est meilleur. Il ne dépend d'aucun découpage en tranches. Échantillon commun : 1542 matchs cotés par tous les opérateurs listés.

---

Un écart de calibration n'est pas exploitable tel quel : la marge de l'opérateur l'absorbe. C'est une information sur la qualité de ce que vous achetez, pas sur un rendement.

18+ · Jouer comporte des risques · joueurs-info-service.fr
