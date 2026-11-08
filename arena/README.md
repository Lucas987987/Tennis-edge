# Tennis Edge Arena V1

Module autonome. Aucun fichier du simulateur n'est remplacé. Aucun bookmaker, cote ou pari.

## Déploiement (obligatoire)
1. Appliquer le ZIP à la racine du dépôt avec le workflow **Appliquer un paquet**.
2. Créer une base Cloudflare D1 séparée, puis appliquer `workers/arena/schema.sql`.
3. Déployer `workers/arena/worker.js` comme Worker distinct avec binding D1 `ARENA_DB`.
4. Configurer les secrets `ARENA_SESSION_SECRET` (32+ octets aléatoires) et `ARENA_ADMIN_TOKEN` et la variable `ARENA_ORIGIN` (origine exacte du site).
5. Configurer l'URL API publique `ARENA_API_URL` dans le site avant le chargement du script, et exposer `arena/` à l'URL voulue.
6. Brancher l'authentification existante : **seul le serveur d'identité de confiance** doit signer les jetons `base64url(JSON({sub,exp})).base64url(HMAC_SHA256(secret,première_partie))`. Ne jamais exposer le secret côté navigateur. Jetons courts et HTTPS obligatoires.
7. Créer les défis côté D1 via un processus administrateur de confiance, avec `starts_at` et `closes_at` au format SQLite UTC `YYYY-MM-DD HH:MM:SS`. Le résultat doit être envoyé par POST `/api/arena/admin/settle` avec session authentifiée et `x-arena-admin-token` depuis un backend sécurisé, jamais depuis le navigateur.

## Barème
Bonne prédiction : 100 points et 120 XP. Autre prédiction : 10 points et 20 XP. Un seul choix par utilisateur et par défi, non modifiable. Les prédictions ferment avant le début du match. Le règlement est unique par défi grâce à la clé primaire et au trigger D1.

## Sécurité
Identité HMAC vérifiée côté serveur, interdiction de double prédiction, fermeture horaire côté serveur, stock et solde contrôlés par triggers SQLite atomiques, points et XP attribués par trigger idempotent. Le classement n'expose que le pseudo et les XP. Aucune information sensible dans les réponses publiques. L'admin doit être isolé et les secrets ne doivent jamais être mis dans Git.

## Limites explicites
L'interface est un MVP : les cartes sont des fiches visuelles non collectionnables, la délivrance réelle d'un abonnement ou avantage nécessite une intégration de provisioning et une vérification juridique/commerciale. L'authentification n'est pas fournie par ce paquet. Ne pas annoncer le service comme prêt au public avant configuration, tests de charge et revue sécurité. L'API n'impose pas encore de limitation de débit : configurer Cloudflare WAF/rate limiting avant ouverture.
