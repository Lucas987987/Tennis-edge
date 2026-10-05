# Les bookmakers sont-ils bien calibrés sur le tennis ?

*Mesuré sur 1814 matchs dénoués. Mise à jour du 2026-10-05.*

Quand une cote implique 30 % de chances, le joueur gagne-t-il vraiment 30 % du temps ? Les probabilités ci-dessous sont **dévigées** : la marge de l'opérateur est retirée, sinon on mesurerait surtout ce qu'il prélève.

| Probabilité annoncée | Observé | Écart | n |
|---|---:|---:|---:|
| 0 – 15 % | 6.2 % | -4.1 pts | 144 |
| 15 – 30 % | 22.9 % | -0.8 pts | 493 |
| 30 – 45 % | 40.2 % | +2.3 pts | 924 |
| 45 – 55 % | 50.0 % | +0.0 pts | 506 |
| 55 – 70 % | 59.8 % | -2.3 pts | 924 |
| 70 – 85 % | 77.1 % | +0.8 pts | 493 |
| 85 – 100 % | 93.8 % | +4.1 pts | 144 |

## Qualité prédictive par opérateur

| Opérateur | Score de Brier | n |
|---|---:|---:|
| bwin | 0.2090 | 3236 |
| unibet | 0.2096 | 3236 |
| pinnacle | 0.2098 | 3236 |

Le **score de Brier** mesure la qualité d'une prédiction probabiliste : 0,25 correspond à un pile ou face, plus bas est meilleur. Il ne dépend d'aucun découpage en tranches. Échantillon commun : 1618 matchs cotés par tous les opérateurs listés.

---

Un écart de calibration n'est pas exploitable tel quel : la marge de l'opérateur l'absorbe. C'est une information sur la qualité de ce que vous achetez, pas sur un rendement.

18+ · Jouer comporte des risques · joueurs-info-service.fr
