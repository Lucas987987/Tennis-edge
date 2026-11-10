# Tennis Edge Arena — Intégration des cartes statistiques V2

Ce paquet ajoute une intégration de cartes existantes de l'algorithme dans la page Arena (collection et aperçus).

Installation : déposer le ZIP dans « Appliquer un paquet », fusionner la PR, lancer « Arena - Integrer cartes statistiques V2 » puis attendre Deploy Pages.

Les cartes sont extraites de `algo/donnees.json` vers `arena/player_cards.json`. Si aucune carte statistique n'est trouvée, le workflow échoue explicitement au lieu de publier des données inventées. Les cartes privées déjà débloquées et les défis Arena sont conservés.

Le script est idempotent, si la V1 est déjà présente il régénère les données. Aucun changement de Worker D1, récompenses ou pronostics.

**Droits** : les cartes contenant des noms de joueurs réels ne sont pas une validation des droits d'exploitation commerciale. Vérifier les droits avant la monétisation.
