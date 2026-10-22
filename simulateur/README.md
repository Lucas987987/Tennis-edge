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
| `match_simule.py` | le match joué **5 000 fois au hasard, point par point**, avec ces profils : feuille de stats prévue (moyenne et fourchette à 80 %), scores, match type set par set |
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
faute ?), au niveau du pronostic (Elo ou Pinnacle) et avec la même forme du
jour. Sa probabilité de victoire retombe sur celle du moteur exact (test). Le
test `backtest_match_simule.py` compare la feuille prévue à la vraie, contre la
moyenne du circuit et contre deux « joueurs moyens » au même niveau. Lancer :
Actions → « Pronostic - test du modèle ».
