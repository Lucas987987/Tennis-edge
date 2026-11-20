# Arena V1.5.1 — Album privé

Correctif ciblé de l’interface :
- Le mode test attend désormais le chargement réel du profil et de l’album après réception du jeton.
- L’inscription déclenche immédiatement une actualisation de la collection.
- Le chargement de l’album est indépendant des défis publics et du classement.
- Une erreur de lecture D1 est distinguée d’un album réellement vide.
- Les réponses concurrentes obsolètes ne remplacent plus le dernier état de l’album.
- Aucun changement du Worker, des tables D1, des secrets ou de l’algorithme principal.

Installation : workflow « Appliquer un paquet », puis fusionner la PR. GitHub Pages mettra à jour l’interface. Rafraîchir la page et activer le mode test.
