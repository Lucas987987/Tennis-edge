# Arena V1.7.2 — Diagnostic et sécurité

- Conserve les fichiers de l’algorithme et le Worker inchangés.
- Supprime temporairement le cron automatique d’import : les écritures ne se font que par lancement manuel.
- Exclut les deux matchs si un joueur est présent sur deux affiches du même circuit à moins de 2 heures.
- `dry_run=true` : simulation, zéro écriture.
- `dry_run=false`, `diagnostic=true` : vérification HTTP GET publique du Worker, zéro écriture, aucun jeton envoyé.
- `dry_run=false`, `diagnostic=false` : import réel (NE PAS lancer avant diagnostic).
- Le code 1010 est compatible avec un refus Cloudflare avant Worker ; la vérification GET ne garantit pas que le POST sera autorisé.
- Pour les réponses 403, le journal donne le type de réponse et le CF-Ray, sans exposer le secret.
- Si 1010 persiste sur POST, vérifier les règles de sécurité Cloudflare avec le CF-Ray ; ne pas désactiver toute la sécurité.
