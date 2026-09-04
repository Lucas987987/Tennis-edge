# Correctifs bis — 04/09/2026

## Ce qui n'allait pas dans ce que je vous ai fait poser ce matin

### `metadata: read` dans health_check.yml — À CORRIGER EN PRIORITÉ
Clé INVALIDE dans un bloc `permissions:` de workflow. Le scope metadata est
toujours accordé en lecture et ne se déclare pas. GitHub rejette le fichier à
la validation : **health_check ne tournerait plus du tout** — donc la
sentinelle de taille non plus, celle-là même qu'on venait de réparer.
`contents: read` seul suffit à `gh api repos/{owner}/{repo}`.
Audit fait sur les 50 workflows : aucune autre clé invalide.

### bump_actions_node24.yml — deux défauts
1. **GITHUB_TOKEN ne peut pas pousser un fichier de workflow.** Structurel :
   il n'existe aucune clé `workflows` dans le bloc permissions. Le run
   91880753053 a tout édité, tout validé, puis s'est fait rejeter au push.
   Un PAT fine-grained à scope *Workflows* est obligatoire — mode d'emploi
   en tête du fichier corrigé.
2. **Le sed réécrivait sa propre liste `PAIRES`.** Log : « actions/cache@v4
   -> v5 : 2 fichier(s) » pour une occurrence réelle. La liste vit maintenant
   hors du dépôt et le workflow s'exclut du balayage.

La vérification pré-commit contrôle désormais aussi les **clés du bloc
permissions** : elle aurait attrapé `metadata: read`. `yaml.safe_load` ne
voyait rien — c'est du YAML parfaitement valide, refusé par GitHub seul.

## Capture closing : mesure plutôt que supposition

Cadence RÉELLE, mesurée sur `parts/live_match_*` :

| jour  | passages | écart médian | par heure |
|-------|----------|--------------|-----------|
| 03/09 | 86       | 10,0 min     | 6 à 9     |
| 04/09 | 62       | 10,0 min     | 6 à 9     |

Attendu à 5 min : 12/heure, 288/jour. Vous en avez la moitié.

La configuration est pourtant juste : cron `*/5`, `SEUIL_CRON_SECOURS_MIN=4`,
bloc `concurrency` retiré. Rien à corriger dans le dépôt — le goulot est en
amont, et rien n'enregistrait lequel des deux déclencheurs manque.

`capture_closing.py` compte maintenant les passages par déclencheur dans
`capture_state.json` (`passages_par_declencheur`, remis à zéro chaque
journée UTC). Lecture dans 24 h :

- `repository_dispatch` ≈ 288 → le worker tient la cadence
- `repository_dispatch` < 150 → le worker est le problème (côté Cloudflare)
- `schedule` dominant, total < 200 → GitHub étale le cron `*/5`. Il n'est
  pas garanti : sous charge il est livré toutes les 8-12 min. Dans ce cas
  seul le worker peut tenir 5 min, et il faut cesser de compter sur le cron.

L'hypothèse la plus probable au vu des 6-9 passages/heure, très réguliers,
est la troisième — mais je préfère que la donnée tranche.

## Vérifications

- 50 workflows : YAML valide, aucune clé permissions invalide
- `capture_closing.py` compile ; cumul journalier et remise à zéro testés
- nouveau bump rejoué sur un dépôt jouet : comptes exacts, liste `PAIRES`
  intacte après passage
- garde-fou permissions testé sur un fichier piégé contenant `metadata: read`
  → refus, code de sortie 1
