# Simulateur de matchs (21/10/2026)

Simule un match de tennis **point par point**, de façon exacte : au lieu de
jouer 5 000 matchs au hasard, il calcule la probabilité de chaque issue.

| Fichier | Rôle |
|---|---|
| `modele.py` | le moteur : jeu, tie-break, set, match ; victoire, sets, total de jeux, handicaps, tie-breaks |
| `notes.py` | force au service et au retour de chaque joueur, ajustée aux adversaires, sans regarder le futur |
| `donnees.py` | lecture des CSV Sackmann et jointure avec les cotes Pinnacle de tennis-data |
| `backtest.py` | le test : réglage sur 2023, jugement sur 2024 → janvier 2026 contre la clôture Pinnacle |
| `marches_sets.py` | le moteur contre les marchés « set 1 » (Pinnacle et books mous), 30 min avant le début |
| `profils_service.py` | profil de service et de retour de chaque joueur : % de 1re balle, aces, doubles fautes, points gagnés derrière la 1re et la 2e balle (→ `profils_service.json`) |
| `match_simule.py` | le match joué **20 000 fois en production**, point par point : feuille prévue, scores et scénario réellement tiré, rejouable par sa trace de points |
| `fiabilite.py` | note de robustesse 0–100 par match, fondée sur les données, l’accord des modèles et la calibration antérieure |
| `ablation.py` | Elo, simulation, mélange de base et pipeline complet sur les mêmes pronostics figés, avec bootstrap par semaine |
| `evaluation_sorties.py` | log loss des sets, rang des scores, erreur des jeux et des statistiques, couverture réelle des intervalles à 80 % |
| `validation_fiabilite.py` | performances par niveau de note, calibration et contraste temporel apparié |
| `profils_robustes.py` | challengers de récence et de shrinkage sur les mêmes matchs, avec sous-groupes peu documentés, transitions, absences et BO5 |
| `dependances_points.py` | tests du point précédent, des tie-breaks, de la fatigue et de l’évolution entre sets sur les séquences ordonnées |
| `gouvernance.py` | périodes disjointes, traçabilité et une seule nouvelle promotion hebdomadaire |
| `recherche_externe.py` | croisement séparé avec les mouvements de marché et H13–H19, sans réinjection dans le modèle |
| `tests/` | invariants probabilistes, ancrage, traces vidéo, identités, surfaces, scores et sorties unifiées |
| `backtest_match_simule.py` | le test de la feuille simulée sur ATP/WTA 2024 → janvier 2026, avant l'heure (→ `rapport_match_simule.json`) |

Lancer le test : Actions → « Simulateur - test contre Pinnacle » → Run workflow.
Le résultat arrive dans `rapport_backtest.json` (et les notes des joueurs dans
`notes_joueurs.json`).

**Forme du jour** (21/10/2026) : sur 2 706 matchs réels, les matchs finissent en
2 sets bien plus souvent (63,7 %) que si chaque point était indépendant (54,7 %).
Le moteur ajoute un écart de forme par match (σ = 0,15, réglé sur juin–août,
vérifié sur septembre–octobre : 63,5 % prévus, 64,6 % réels).

**Verdict du test du 21/10/2026** : sur la victoire, le modèle statistique perd
contre Pinnacle (log loss 0,619 contre 0,592 ; paris −4,5 % à −7 %).

**Règle** : aucun pari sur ce modèle tant que le test ne montre pas qu'il
apporte quelque chose à Pinnacle. Données : archive des CSV de Jeff Sackmann
(CC BY-NC-SA 4.0, usage non commercial), arrêtée en juin 2026.

**Match simulé** (22/10/2026) : le moteur exact donne les probabilités ; la
simulation joue en plus chaque point (1re balle dans le court ? ace ? double
faute ?), au niveau de la variante indépendante affichée (Elo, simulation ou
combinaison) et avec la même forme du jour. Aucune cote n'entre dans ces trois
variantes. Sa probabilité de victoire retombe sur celle du moteur exact (test). Le
test `backtest_match_simule.py` compare la feuille prévue à la vraie, contre la
moyenne du circuit et contre deux « joueurs moyens » au même niveau. Lancer :
Actions → « Pronostic - test du modèle ».


## Validation et gouvernance (26/10/2026)

Le workflow hebdomadaire produit les rapports `rapport_evaluation_sorties.json`,
`rapport_validation_fiabilite.json`, `rapport_profils_robustes.json`,
`rapport_dependances_points.json`, `rapport_recherche_externe.json` et
`rapport_gouvernance.json`. Une métrique indisponible reste absente : elle n'est
jamais remplacée par zéro. Les scores sont rangés à partir de 1 et les
statistiques sont rattachées uniquement à la variante qui les a simulées.

Les profils candidats sont comparés au champion réellement publié. Un challenger
est choisi sur la période de découverte, puis doit confirmer chronologiquement,
améliorer la log loss d'au moins 0,001 et passer l'hystérésis de deux semaines.
La gouvernance finale limite en outre les promotions à une par semaine.

Les effets dynamiques entre points restent des candidats de recherche tant que
leur gain sur les points n'a pas aussi été validé sur le vainqueur. La recherche
de marché censure chaque cote au moment disponible et chaque signal à sa date de
signalisation. Sans volumes ni confirmation multi-bookmakers, ses résultats sont
exploratoires ; ils ne modifient jamais les probabilités indépendantes.
