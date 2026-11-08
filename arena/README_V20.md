# Tennis Edge Arena V2.0 — validation sûre des résultats

## Ce paquet
- Ajoute une route **admin GET** paginée pour consulter les défis ouverts dont le début remonte à plus de 3 heures.
- Utilise l'endpoint `admin/settle` existant et les triggers D1 existants : attribution unique de points/XP ; aucun nouveau schéma D1.
- Ajoute un workflow toutes les 3 heures et une simulation manuelle.
- **Ne valide jamais** les fichiers `resultats_derived.json`, `resultats_fast.json` ou `resultats_oddspapi.json` tels quels : les résultats historiques actuels sont provisoires.
- Nécessite un fichier `arena/data/results_confirmed.json` explicitement confirmé par une source officielle ou par un contrôle humain. Sans résultat confirmé, aucun point n'est attribué.

## Déploiement
1. Appliquer le paquet, fusionner la PR.
2. Lancer **Arena - Deployer Cloudflare** (Worker mis à jour, mêmes secrets).
3. Lancer **Arena - Valider les résultats confirmés** avec `dry_run=true` pour le diagnostic.
4. Les passages programmés exécutent le rapprochement réel, mais n'écrivent que pour des résultats confirmés et non ambigus.

## Exemple de format
```json
{"schema_version":1,"results":[{"date":"2026-11-08","tournament":"WTA Finals Women Singles","player_a":"Coco Gauff","player_b":"Jessica Pegula","winner":"a","status":"completed","source":"official","verified":true,"provisional":false}]}
```
**L'exemple n'est PAS une affirmation de résultat réel**. Ne le recopiez pas comme résultat sans confirmation.

## Limitations
- Ce paquet sécurise la validation automatique et les récompenses existantes ; il n'ajoute pas encore de fournisseur de résultats officiels ni de nouveaux graphismes/cartes.
- Les dates/tournois/joueurs doivent correspondre exactement après normalisation. Les résultats ambigus ou absents sont ignorés.
- Aucun changement du moteur de simulations, des cotes, des comptes, ni des tables D1.
