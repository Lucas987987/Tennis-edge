# Les bookmakers sont-ils bien calibrés sur le tennis ?

*Mesuré sur 1025 matchs dénoués. Mise à jour du 2026-08-25.*

Quand une cote implique 30 % de chances, le joueur gagne-t-il vraiment 30 % du temps ? Les probabilités ci-dessous sont **dévigées** : la marge de l'opérateur est retirée, sinon on mesurerait surtout ce qu'il prélève.

| Probabilité annoncée | Observé | Écart | n |
|---|---:|---:|---:|
| 0 – 15 % | 5.9 % | -4.4 pts | 68 |
| 15 – 30 % | 23.4 % | -0.2 pts | 269 |
| 30 – 45 % | 41.7 % | +3.8 pts | 528 |
| 45 – 55 % | 50.0 % | +0.0 pts | 320 |
| 55 – 70 % | 58.3 % | -3.8 pts | 528 |
| 70 – 85 % | 76.6 % | +0.2 pts | 269 |
| 85 – 100 % | 94.1 % | +4.4 pts | 68 |

## Qualité prédictive par opérateur

| Opérateur | Score de Brier | n |
|---|---:|---:|
| bwin | 0.2150 | 1904 |
| unibet | 0.2158 | 1904 |
| pinnacle | 0.2162 | 1904 |

Le **score de Brier** mesure la qualité d'une prédiction probabiliste : 0,25 correspond à un pile ou face, plus bas est meilleur. Il ne dépend d'aucun découpage en tranches. Échantillon commun : 952 matchs cotés par tous les opérateurs listés.

---

Un écart de calibration n'est pas exploitable tel quel : la marge de l'opérateur l'absorbe. C'est une information sur la qualité de ce que vous achetez, pas sur un rendement.

18+ · Jouer comporte des risques · joueurs-info-service.fr
