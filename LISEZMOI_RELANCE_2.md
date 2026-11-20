> ## ⛔ OBSOLÈTE — INTERDIT D'EXÉCUTION (15/10/2026)
>
> Cette procédure réécrit l'historique et se termine par un **force-push**
> (`git push --force`). C'est **interdit** sur ce dépôt depuis la perte de
> données du 29/09/2026. Ne lancez aucune commande de ce document.
>
> Ce qui la remplace :
> 1. **Migration R2** (en cours) : les données qui changent à chaque run
>    (ticks Polymarket/Kalshi, courbes live) sortent de git vers Cloudflare
>    R2, et `clv_history.jsonl` est découpé par mois. Voir
>    `README_MIGRATION_R2.md`.
> 2. **Plus tard, à froid, sans urgence** : un *nouveau dépôt propre* (copie
>    de l'état actuel sans historique lourd), l'ancien dépôt étant archivé en
>    lecture seule. Aucun force-push, aucune réécriture : l'ancien reste
>    intact et consultable.
>
> Le contenu ci-dessous est conservé **pour mémoire uniquement**.

---

# Relance de l'étape 3 — 2e correction, 05/09/2026

## Ce qui a marché

Le correctif de jeton est bon : **56 workflows sur 57 suspendus**, plus un
seul 403. `GITHUB_TOKEN` avait bien la permission qui manquait au PAT.

Le job s'est arrêté proprement AVANT de toucher à l'historique, et les 57
workflows ont été réactivés (`✅ tous les workflows sont réactivés (vérifié)`).
Dépôt intact, rien à restaurer.

## Ce qui bloquait

    HTTP 422: Unable to disable this workflow.  (workflow 284757662)

C'est **« Pages build and deployment »**, le workflow que GitHub génère
lui-même quand Pages est activé. Son chemin est `dynamic/pages/...`, il
n'existe pas dans `.github/workflows/`, et l'API refuse de le désactiver.
Il ne commite rien sur `main` : il n'a jamais été une menace pour la purge.

Mon garde-fou de la passe précédente était devenu **trop strict** — il
bloquait une opération sûre. C'est le défaut symétrique de celui d'avant :
la première version mentait en disant « ✅ suspendus » alors que rien ne
l'était, la seconde refusait de partir pour un workflow inoffensif. Un
garde-fou qui crie au loup finit contourné, ce qui est ici le pire résultat
possible.

## Le correctif

**On ne tente de suspendre que les workflows définis par un fichier du
dépôt** (`path` commençant par `.github/workflows/`). Les workflows gérés
par GitHub sont listés comme ignorés, sans bloquer.

**Puis on RELIT l'état réel** au lieu de se fier au code de retour des
commandes. Ce qui compte n'est pas que les appels aient réussi, c'est
qu'aucun workflow capable de committer ne soit encore actif. Un workflow
dont le fichier n'existe plus dans le dépôt ne peut pas se déclencher : il
n'est pas comptabilisé.

Testé sur cinq cas : workflow GitHub dynamique -> ignoré · la purge
elle-même -> exclue · déjà désactivé -> exclu · fichier supprimé -> non
bloquant · workflow réel encore actif -> **code de sortie 1**.
Et le cas nominal, tout suspendu -> code 0.

## Marche à suivre

1. Remplacer `purge_3_executer.yml`.
2. `main` a de nouveau avancé : **relancer « Purge 2/3 — LISTE »**.
3. Lancer « Purge 3/3 » avec `JE CONFIRME LA PURGE`.

La ligne à chercher dans le log avant tout le reste :

    ✅ aucun workflow du dépôt n'est encore actif (vérifié en relisant l'état).

Si elle n'y est pas, rien de ce qui suit ne compte.

## Rappel du gain attendu

Le run précédent l'a mesuré pour de vrai, avant d'échouer au push :

    3.9G .git  ->  520M .git     (18 871 commits conservés)
