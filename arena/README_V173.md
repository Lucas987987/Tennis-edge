# Arena V1.7.3 — diagnostic authentification sans écriture

Ce paquet ne remplace pas le Worker et ne touche pas à l’algorithme.

1. Appliquer le paquet, puis fusionner la PR.
2. Actions → Arena - Import automatique des matchs → Run workflow.
3. Mettre `dry_run=false` et `diagnostic=true`. **Aucun défi n’est créé : le POST contient volontairement `{}`.**
4. Si le Worker répond HTTP 400 « Invalid challenge », le jeton administrateur est valide.
5. Si HTTP 403 JSON « Forbidden », le jeton est refusé par le Worker. Si HTTP 403 HTML/1010, le blocage est en amont chez Cloudflare.
6. Ne lancer l’import réel qu’après diagnostic OK. Le test réel doit être limité à un match dans une prochaine étape.

Les noms provisoires `r16p1`, `r16p2`, `TBD`, `Qualifier`, `bye`, etc. sont exclus. La détection de conflits à moins de 2 heures est conservée.

Le mode `dry_run=true` a priorité : aucune requête POST, même si `diagnostic=true`.
Les imports automatiques planifiés restent désactivés.
