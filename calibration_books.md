# Les bookmakers sont-ils bien calibrés sur le tennis ?

*Mesuré sur 779 matchs dénoués. Mise à jour du 2026-10-02.*

Quand une cote implique 30 % de chances, le joueur gagne-t-il vraiment 30 % du temps ? Les probabilités ci-dessous sont **dévigées** : la marge de l'opérateur est retirée, sinon on mesurerait surtout ce qu'il prélève.

| Probabilité annoncée | Observé | Écart | n |
|---|---:|---:|---:|
| 0 – 15 % | 1.6 % | -8.4 pts | 64 |
| 15 – 30 % | 22.9 % | -1.0 pts | 201 |
| 30 – 45 % | 39.2 % | +1.1 pts | 401 |
| 45 – 55 % | 50.0 % | +0.0 pts | 226 |
| 55 – 70 % | 60.8 % | -1.1 pts | 401 |
| 70 – 85 % | 77.1 % | +1.0 pts | 201 |
| 85 – 100 % | 98.4 % | +8.4 pts | 64 |

## Qualité prédictive par opérateur

| Opérateur | Score de Brier | n |
|---|---:|---:|
| pinnacle | 0.2049 | 1346 |
| unibet | 0.2052 | 1346 |

Le **score de Brier** mesure la qualité d'une prédiction probabiliste : 0,25 correspond à un pile ou face, plus bas est meilleur. Il ne dépend d'aucun découpage en tranches. Échantillon commun : 673 matchs cotés par tous les opérateurs listés.

---

Un écart de calibration n'est pas exploitable tel quel : la marge de l'opérateur l'absorbe. C'est une information sur la qualité de ce que vous achetez, pas sur un rendement.

18+ · Jouer comporte des risques · joueurs-info-service.fr
