Arena V1.5.2 — correctif authentification GET privée

Cause confirmée dans arena/arena.js : les requêtes GET /api/arena/me et /api/arena/me/cards omettaient Authorization, provoquant HTTP 401 Authentication required.

Correction : envoyer Bearer uniquement sur ces deux GET privées et conserver les GET publiques sans jeton pour bénéficier du cache et éviter les préflights inutiles.

Installation : workflow Appliquer un paquet, fusionner la PR, recharger GitHub Pages, réactiver le mode test puis vérifier Mon espace et Mes cartes débloquées.

Aucune migration D1, aucun déploiement Worker, aucun secret modifié. Si la base est toujours au quota, une erreur 500 peut subsister jusqu'à sa réinitialisation.
