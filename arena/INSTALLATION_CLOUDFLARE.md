# Arena V1 — étape 2 Cloudflare

Ce paquet complète le correctif de publication déjà installé. Il n'altère pas le simulateur.

## Préparation Cloudflare (une seule fois)
1. Créer une base D1 nommée `tennis-edge-arena` dans Cloudflare.
2. Copier son `database_id` dans GitHub → Settings → Secrets and variables → Actions → Variables : `ARENA_D1_DATABASE_ID`.
3. Ajouter les variables GitHub :
   - `ARENA_ORIGIN` = `https://lucas987987.github.io` (origine GitHub Pages, sans chemin)
   - `ARENA_API_URL` = URL réelle du Worker après déploiement (ex. https://tennis-edge-arena.<votre-sous-domaine>.workers.dev).
4. Ajouter les secrets GitHub :
   - `CLOUDFLARE_API_TOKEN` (Workers Scripts Edit, D1 Edit, Account settings read)
   - `CLOUDFLARE_ACCOUNT_ID`
   - `ARENA_SESSION_SECRET` (chaîne aléatoire de 32 octets ou plus)
   - `ARENA_ADMIN_TOKEN` (chaîne aléatoire indépendante).
5. Actions → Arena - Deployer Cloudflare → Run workflow.
6. Actions → Deploy Pages → Run workflow pour injecter l'URL de l'API dans la page Arena.

## Important : connexion et données
Le backend V1 exige un jeton de session HMAC signé par un fournisseur d'identité fiable.
Ce paquet NE crée PAS de connexion publique automatique : le bouton Rejoindre ne peut pas
fonctionner sans fournisseur de sessions. Cela évite de permettre à n'importe qui de fabriquer
des comptes et des points. Les défis doivent aussi être alimentés côté serveur.

La boutique et les récompenses ne doivent pas être proposées au public avant les tests
d'authentification, de limitation des abus et de règlement des défis.

Le workflow de déploiement n'est déclenché que manuellement pour éviter un déploiement
accidentel sans configuration.
