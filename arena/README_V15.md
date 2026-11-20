# Tennis Edge Arena V1.5 — cartes illustrées et album personnel

Patch frontend uniquement. Aucun changement Worker, SQL, GitHub Actions, secrets ou moteur Tennis Edge.

- Les cartes d'aperçu sont illustrées par un dessin vectoriel intégré (aucun téléchargement ni licence d'image).
- Les cartes gagnées sont affichées depuis `/api/arena/me/cards` après authentification privée, avec la mention DÉBLOQUÉE.
- Quatre habillages de rareté sont disponibles : commune, rare, épique, légendaire. Les raretés sont purement visuelles/provisoires et **ne sont pas attribuées ni enregistrées dans D1**. Ne pas les interpréter comme une vraie rareté gagnée.
- Le quota D1 peut encore empêcher l'affichage des cartes personnelles. Dans ce cas, un message explicite apparaît.
- Le profil et les cartes déjà gagnées ne sont pas modifiés.

## Installation
Utiliser le workflow « Appliquer un paquet » avec ce ZIP, fusionner la PR, puis attendre le déploiement GitHub Pages. Recharger la page sans cache.

## Vérification
1. Voir les cartes illustrées dans « Cartes de joueurs » même sans connexion.
2. Activer le mode test privé ; si le quota D1 le permet, voir les cartes gagnées dans « Mes cartes débloquées ».
3. Ne pas confondre aperçu et cartes réellement obtenues.
