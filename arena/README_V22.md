# Arena V2.2 — Diagnostic et revalidation OddsPapi

- Le collecteur conserve désormais `commence_time` pour les nouveaux résultats.
- Les anciens résultats provisoires sont revérifiés via `/fixtures/settlement`, dans le budget de requêtes déjà configuré (`MAX_SETTLEMENT_CALLS`, 20 revalidations maximum par exécution).
- Une ancienne entrée n'est certifiée que si `Finished`, victoire du marché match, et vainqueur identique à celui archivé. Une tentative sans preuve reste provisoire.
- Arena compare la date de début du match et non la date de résolution API.
- Le workflow Arena affiche les motifs d'exclusion et jusqu'à 25 défis sans correspondance.

**Installation :** Appliquer un paquet, fusionner, lancer `Fetch Results (settlement, fast)` puis `Arena - Valider les résultats confirmés` en `dry_run=true`. Vérifier les logs. Les récompenses réelles ne sont pas activées automatiquement.

**Limite :** le collecteur historique suit les matchs de la base CLV ; les matchs Arena non présents dans cette base ne seront pas automatiquement récupérés. Le diagnostic permettra de les identifier.
