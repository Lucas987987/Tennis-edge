# Les bookmakers sont-ils bien calibrés sur le tennis ?

*Mesuré sur 1842 matchs dénoués. Mise à jour du 2026-10-12.*

Quand une cote implique 30 % de chances, le joueur gagne-t-il vraiment 30 % du temps ? Les probabilités ci-dessous sont **dévigées** : la marge de l'opérateur est retirée, sinon on mesurerait surtout ce qu'il prélève.

| Probabilité annoncée | Observé | Écart | n |
|---|---:|---:|---:|
| 0 – 15 % | 6.7 % | -3.5 pts | 150 |
| 15 – 30 % | 21.8 % | -1.9 pts | 482 |
| 30 – 45 % | 39.6 % | +1.8 pts | 935 |
| 45 – 55 % | 50.0 % | +0.0 pts | 550 |
| 55 – 70 % | 60.4 % | -1.8 pts | 935 |
| 70 – 85 % | 78.2 % | +1.9 pts | 482 |
| 85 – 100 % | 93.3 % | +3.5 pts | 150 |

## Qualité prédictive par opérateur

| Opérateur | Score de Brier | n |
|---|---:|---:|
| bwin | 0.2072 | 3332 |
| pinnacle | 0.2077 | 3332 |
| unibet | 0.2077 | 3332 |

Le **score de Brier** mesure la qualité d'une prédiction probabiliste : 0,25 correspond à un pile ou face, plus bas est meilleur. Il ne dépend d'aucun découpage en tranches. Échantillon commun : 1666 matchs cotés par tous les opérateurs listés.

---

Un écart de calibration n'est pas exploitable tel quel : la marge de l'opérateur l'absorbe. C'est une information sur la qualité de ce que vous achetez, pas sur un rendement.

18+ · Jouer comporte des risques · joueurs-info-service.fr
