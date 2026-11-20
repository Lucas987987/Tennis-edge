Tennis Edge Arena V1.3.1 — Reparation D1 non destructive

1. Appliquer ce ZIP avec le workflow Appliquer un paquet et fusionner.
2. Lancer Actions > Arena - Reparer D1 sans effacer les donnees.
3. Envoyer les logs complets si les GET renvoient encore 500.

Le workflow ne supprime aucune table ni aucune ligne. Il réapplique uniquement les CREATE IF NOT EXISTS de schema.sql, arena_v12.sql et arena_v13.sql et vérifie les compteurs.
Aucun déploiement Worker, aucun changement de secret, aucun changement de l'algorithme.
Si OPTIONS reste 403, c'est un problème distinct, probablement avant le Worker (règles Cloudflare); il faudra examiner les événements de sécurité Cloudflare.
Attention : le workflow n'est pas une garantie de correction si la cause est une erreur SQL autre que l'absence de tables.
