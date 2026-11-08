# Arena V2.1 — Résultats OddsPapi certifiés

Le collecteur existant appelle `/fixtures/settlement`. Désormais, une entrée est `provisional: false` UNIQUEMENT si le statut renvoyé est exactement `Finished` et si le vainqueur vient du marché match (WIN/WON), pas d'une inférence de score. Le statut et la preuve sont archivés. Les anciennes entrées restent provisoires et ne sont pas requalifiées.

Le rapprochement Arena lit `resultats_oddspapi.json` et exige la preuve `winner_from_market=true`, la date de résolution à ±1 jour du défi, le tournoi et les deux joueurs identiques (ordre inversé autorisé). Les cas ambigus ne sont pas validés. La validation D1 est idempotente via `arena_settlements`.

**Important** : le workflow programmé reste en simulation par sécurité. Exécuter d'abord le collecteur existant, puis `Arena - Valider les résultats confirmés` avec `dry_run=true`. Si les correspondances sont bonnes, lancer manuellement avec `dry_run=false`. Ne pas automatiser l'écriture réelle avant validation de l'identité des rencontres et des dates (resolved_at n'est pas la date de début).

Aucune nouvelle requête API, aucune modification de l'algorithme ni de la base D1.
