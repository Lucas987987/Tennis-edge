# Arena V1.7.4 — premier import réel contrôlé

Ce paquet modifie uniquement le script d’import et son workflow GitHub Actions. Aucun changement du Worker, des tables D1, de l’algorithme, ni des données existantes.

## Procédure
1. Appliquer le paquet et fusionner la PR.
2. Lancer **Arena - Import automatique des matchs** avec `dry_run=false`, `diagnostic=false`, `max_matches=1`.
3. Vérifier dans les logs `IMPORT CIBLE`, puis `Import terminé : 1 créés` ou `0 créés, 1 déjà présents`.
4. Vérifier que le défi est visible sur Arena.

Si le Worker renvoie HTTP 403, 500 ou une erreur D1, le run s’arrête immédiatement. Aucun second match n’est envoyé. Un run vert ne prouve pas à lui seul que l’interface affiche le défi : vérifier Arena.

**Important** : les sources peuvent contenir des horaires reportés ou inexacts ; contrôler le match avant de l’annoncer. Les imports automatiques restent désactivés.
