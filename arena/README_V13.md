# Tennis Edge Arena V1.3
Installation: Appliquer un paquet, fusionner, lancer 'Arena - Installer demo privee', puis publier GitHub Pages.
Nouveautés: classement des 7 derniers jours et du mois; création sécurisée de vrais défis via le workflow 'Arena - Ajouter un vrai match (manuel)'; cartes des gagnants des défis réels.
Aucune cote, aucune modification du moteur de simulation. Les défis réels ne sont PAS encore importés automatiquement : il faut une source de calendrier fiable, un mapping d'identifiants et un contrôle des doublons avant d'activer un collecteur.
Créer les vrais matchs via le workflow manuel (heure UTC, au moins 10 minutes dans le futur). Les pronostics ferment 5 minutes avant le début. Ne pas publier des rencontres fictives comme réelles.
La validation des résultats réels reste une opération administrateur via la route /api/arena/admin/settle avec le secret ARENA_ADMIN_TOKEN et une session autorisée; aucun résultat n'est inventé.
Le mode test privé reste réservé à l'administrateur. Le workflow de déploiement conserve les données D1 et les secrets existants.
Attention: les cartes de rareté, les bonus de séries, les récompenses automatiques et le calendrier automatique ne sont pas implémentés dans cette étape.
