# Tennis Edge Arena V1.7.5 — transport curl sécurisé

Le 403 Cloudflare `error code: 1010` rencontré avec Python urllib peut provenir de l'empreinte du client. Cette version utilise **curl** (transport différent), sans modifier les règles de sécurité Cloudflare ni le Worker.

**Ce n'est pas une garantie de contourner un blocage Cloudflare** : si le 1010 persiste, les logs affichent le code et le `cf-ray` pour une analyse ciblée.

- Aucun changement de schéma D1, de comptes, de points, de cartes, du Worker ou de l'algorithme.
- Les filtres des matchs et l'exclusion des joueurs fictifs sont conservés.
- `dry_run=true` : aucun appel d'écriture.
- `diagnostic=true` avec `dry_run=false` : diagnostic sans écriture (transport précédent).
- Premier essai réel : `dry_run=false`, `diagnostic=false`, `max_matches=1`.
- Le secret admin est transmis à curl via sa configuration sur stdin, pas dans les arguments de processus.
- Pas de relance automatique en cas d'échec. Un succès 200 signifie que le défi existait déjà ; 201 qu'il a été créé.

**Ne pas activer 30 matchs tant qu'un premier import n'a pas réussi et que le quota D1 n'est pas confirmé.**
