# Tennis Edge Arena V1.8 — import de tous les matchs éligibles

Paquet compatible avec le workflow « Appliquer un paquet ».

## Changements
- Suppression du plafond MAX_MATCHES=30 et de ARENA_IMPORT_LIMIT.
- Suppression du sélecteur GitHub 1/5/10/30.
- Traitement de tous les matchs éligibles du snapshot local (ATP, WTA, Challenger).
- Conservation de la fenêtre temporelle actuelle (20 min à 7 jours), de la fraîcheur du snapshot (240 min), des contrôles des joueurs, des doublons et des conflits.
- Conservation de curl et du secret GitHub ARENA_ADMIN_TOKEN.
- Pause de 0,3 seconde entre requêtes, aucune limite numérique.
- Timeout GitHub porté à 30 minutes.

## Utilisation
1. Appliquer le ZIP via « Appliquer un paquet » et fusionner la PR.
2. Lancer « Arena - Import automatique des matchs ».
3. Choisir dry_run=true pour compter les rencontres sans écrire dans D1.
4. Puis dry_run=false, diagnostic=false pour importer toutes les rencontres éligibles.

## Précautions
L'import n'efface aucune donnée existante. Le Worker utilise INSERT OR IGNORE avec identifiant stable. Le flux est pris dans matches_oddspapi.json ; aucune cote n'est transmise.
La tâche n'est pas encore programmée périodiquement : lancement manuel, pour éviter un déclenchement non supervisé tant que le volume réel et les quotas Cloudflare n'ont pas été mesurés.
