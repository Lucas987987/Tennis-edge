# Les bookmakers sont-ils bien calibrés sur le tennis ?

*Mesuré sur 1342 matchs dénoués. Mise à jour du 2026-08-31.*

Quand une cote implique 30 % de chances, le joueur gagne-t-il vraiment 30 % du temps ? Les probabilités ci-dessous sont **dévigées** : la marge de l'opérateur est retirée, sinon on mesurerait surtout ce qu'il prélève.

| Probabilité annoncée | Observé | Écart | n |
|---|---:|---:|---:|
| 0 – 15 % | 8.5 % | -2.0 pts | 82 |
| 15 – 30 % | 22.3 % | -1.4 pts | 350 |
| 30 – 45 % | 40.8 % | +2.9 pts | 710 |
| 45 – 55 % | 50.0 % | +0.0 pts | 400 |
| 55 – 70 % | 59.2 % | -2.9 pts | 710 |
| 70 – 85 % | 77.7 % | +1.4 pts | 350 |
| 85 – 100 % | 91.5 % | +2.0 pts | 82 |

## Qualité prédictive par opérateur

| Opérateur | Score de Brier | n |
|---|---:|---:|
| bwin | 0.2152 | 2454 |
| pinnacle | 0.2160 | 2454 |
| unibet | 0.2161 | 2454 |

Le **score de Brier** mesure la qualité d'une prédiction probabiliste : 0,25 correspond à un pile ou face, plus bas est meilleur. Il ne dépend d'aucun découpage en tranches. Échantillon commun : 1227 matchs cotés par tous les opérateurs listés.

---

Un écart de calibration n'est pas exploitable tel quel : la marge de l'opérateur l'absorbe. C'est une information sur la qualité de ce que vous achetez, pas sur un rendement.

18+ · Jouer comporte des risques · joueurs-info-service.fr
