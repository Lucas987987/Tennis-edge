# Tennis Edge Arena V1.7 — Import automatique contrôlé

## Contenu
- Workflow « Arena - Import automatique des matchs », exécuté toutes les 3 heures.
- Import JSON HTTPS de matchs ATP, WTA, Challenger, sans cotes.
- Filtrage des matchs à venir (20 min à 7 jours), 30 maximum par exécution.
- Identifiants déterministes et INSERT OR IGNORE côté Worker : les matchs déjà importés ne sont pas dupliqués.
- Mode simulation pour lancement manuel, sans écritures D1.
- Aucune migration D1, aucune modification de l'algorithme Tennis Edge.

## Configuration nécessaire
1. Installer le ZIP via « Appliquer un paquet » et fusionner.
2. Redéployer le Worker Arena avec le workflow « Arena - Installer demo privee » : indispensable car worker.js est modifié.
3. Dans GitHub Settings > Secrets and variables > Actions > Variables, créer ARENA_MATCH_FEED_URL pointant vers un flux HTTPS JSON **fiable et autorisé**.
4. Lancer « Arena - Import automatique des matchs » avec dry_run=true, consulter les logs.
5. Lancer avec dry_run=false pour importer. Le cron s'exécutera ensuite automatiquement.

Sans URL de calendrier configurée, le workflow se termine proprement sans importer de match. Ce paquet ne fournit pas un calendrier réel et ne prétend pas découvrir des matchs automatiquement sans source.

## Format du flux
{"matches":[{"circuit":"ATP","title":"Tournoi - Tour","player_a":"Joueur A","player_b":"Joueur B","starts_at":"2026-11-15T14:00:00Z"}]}

Les dates doivent être en UTC, avec suffixe Z. Les joueurs et les horaires doivent provenir de données réelles et vérifiées. Les changements de calendrier ou annulations ne sont pas encore synchronisés. Le résultat final doit toujours être validé par le workflow d'administration existant.

## D1
Les appels à D1 sont limités aux matchs sélectionnés. Ne pas activer l'import en production tant que le quota est saturé. L'API continue de servir le cache public selon V1.4.
