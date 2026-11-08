# Tennis Edge Arena V1.4 — Optimisation et collection

Paquet de remplacement compatible avec « Appliquer un paquet ».

## Changements
- Cache Cloudflare Workers Cache API des quatre routes GET publiques (45 à 300 secondes), uniquement pour réponses HTTP 200. Aucune donnée personnelle mise en cache.
- En-têtes CORS reconstruits à chaque réponse du cache pour ne pas mélanger les origines.
- Mémoïsation navigateur des GET publics pendant 30 secondes.
- GET publics sans en-tête Authorization/Content-Type inutile, évitant les preflights CORS sur ces requêtes.
- Cartes gagnées mises en valeur dans l'album existant ; aucune rareté fictive ajoutée à la base.
- Messages d'erreur plus lisibles et correction de validation de date ISO UTC pour l'ajout de vrais matchs.

## Installation
1. Appliquer le ZIP puis fusionner la PR.
2. Lancer le workflow existant « Arena - Installer demo privee » (ou le workflow de déploiement Arena qui est opérationnel dans votre dépôt) pour déployer le Worker modifié. **Ne pas réinitialiser D1.**
3. Contrôler /arena/ et les routes GET après le renouvellement du quota D1.

## Limites
- Le cache n'est pas prérempli ; la première requête après expiration consomme D1.
- Si le quota D1 est épuisé avant le premier remplissage, le cache ne peut pas réparer cette panne immédiatement.
- Cache Workers best-effort par centre de données, sans garantie d'unicité globale ni d'invalidation immédiate.
- Les actions privées continuent à interroger D1, sans cache.
- Les cartes rares/épiques/légendaires et les saisons avec récompenses nécessitent une phase ultérieure de règles et de migration, non incluse ici pour préserver les données.
