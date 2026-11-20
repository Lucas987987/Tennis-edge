# Arena V1.7.1 — source existante Tennis Edge
Le workflow Arena - Import automatique des matchs utilise `matches_oddspapi.json` et `matches_oddspapi_meta.json` présents dans le dépôt au moment du checkout.
Il n'appelle pas l'API sportive, ne transmet aucune cote à Arena, et ne modifie aucun fichier de l'algorithme.
Contrôles : fraîcheur du snapshot (max 4 h), ATP/WTA/Challenger, horaires UTC futurs entre 20 minutes et 7 jours, noms, doublons, limite 30.
L'identifiant côté Worker est déterministe pour le même circuit/tournoi/joueurs/date.
Attention : les changements d'horaire peuvent créer un nouveau défi puisque l'identifiant inclut la date. Une gestion des reports nécessitera une évolution distincte du Worker.
Déploiement : Appliquer un paquet, fusionner PR, puis lancer « Arena - Import automatique des matchs » en simulation (`dry_run=true`). Ensuite lancer en réel (`dry_run=false`) seulement si le quota D1 le permet.
Aucun redéploiement Worker nécessaire si V1.7 a déjà été déployée.
