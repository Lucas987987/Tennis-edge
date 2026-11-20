# Correctifs du 04/09/2026 — panne du run 91710599493

## 1. steam_pipeline rouge alors que tout a réussi

Le run avait ses 10 livrables ✅ et son push OK (`2cfa7b94..06588c71`). Il est
mort sur `--strict` : « Polymarket : 1 échec(s) », **0 livrable en défaut**.

Cause : `grep -c "❌"` comptait les lignes contenant ❌ sans distinguer le
marqueur du workflow des cinq `print("❌ …")` que les scripts émettent en
sortie NORMALE (code 0) quand il n'y a pas encore de données appariables.
À 04h20 UTC en creux de calendrier, c'est le cas courant. Le fichier
régénéré à 08h58 disait 0 échec sans qu'aucun correctif ait été appliqué.

- `.github/workflows/polymarket_studies.yml`
  - marqueur `PMSTUDY_FAIL:` qu'aucun script ne peut imprimer
  - `n_echecs` compte `^PMSTUDY_FAIL:` uniquement
  - nouveau verrou : un échec réel rend CE run rouge, après le commit

- `scripts/pipeline_status.py`
  - l'alerte de contenu Polymarket ne bloque plus `--strict` : ces quatre
    scripts sont des études exploratoires que steam_pipeline ne produit pas,
    ne contrôle pas et ne peut pas réparer. Statut toujours affiché en ⚠️
    dans le Markdown.
  - la **fraîcheur** reste bloquante : un producteur externe mort est
    exactement ce que `--strict` a été écrit pour attraper.

## 2. La sentinelle de taille était aveugle depuis le 03/09

`secrets.GH_TOKEN` n'existe pas dans le dépôt. Il arrivait vide, `gh api`
refusait, `repo_sentinel` écrivait zone='indisponible', `|| true` avalait le
reste. Dernière taille réelle : 3,48 Go le 29/08, pour une alarme à 4,0 Go.
Rien ne l'attrapait : `genere_le` restait frais puisque le fichier était bien
réécrit chaque jour — avec `taille_go: null`.

- `.github/workflows/health_check.yml`
  - `GH_TOKEN: ${{ secrets.GH_TOKEN || github.token }}`
  - `permissions: contents: read / metadata: read` (sans quoi le jeton
    automatique aurait échoué comme le secret vide)

- `scripts/repo_sentinel.py`
  - nouveau champ `derniere_mesure_reussie_le`, préservé d'un run à l'autre.
    C'est lui, et non `genere_le`, qui dit si la surveillance fonctionne.

- `scripts/pipeline_status.py`
  - bloque sur **cécité durable** (>72 h sans mesure réussie), pas sur une
    indisponibilité passagère — `repo_sentinel` a raison de dire qu'un rouge
    quotidien cesse d'être un signal.

## 3. Node 20 retiré des runners le 16/09/2026

Douze jours. Les runners forcent déjà Node 24 en avertissement.

- checkout v4→v5 (50), setup-python v5→v6 (48), cache v4→v5,
  upload-artifact v4→v5, configure-pages v5→v6, deploy-pages v4→v5,
  upload-pages-artifact v3→v5

## 4. steam_pipeline rapatriait 426 Mo pour en lire une fraction

37 s de checkout au run 91710599493.

- `.github/workflows/steam_pipeline.yml` : sparse-checkout après inventaire
  script par script (`live_*`, `hist_*`, `ARCHIVE_INDEX.json` ; pm_ticks et
  kx_ticks écartés — aucun script du pipeline ne les lit).
- `scripts/pipeline_status.py` : `_checkout_partiel()`. Sans lui, le compteur
  de partitions aurait affiché une fraction comme un total — le compteur qui
  surveille la trajectoire du dépôt serait devenu une fausse réassurance,
  exactement ce que la sentinelle vient de subir.

## Vérifications

- 50 workflows : YAML valide
- scripts + tests : compilation OK, 13/13 tests passent
- motifs sparse-checkout testés sur un dépôt git réel : `live_*`/`hist_*`
  présents, ticks écartés, `git add -A` ne supprime rien (skip-worktree)
- logique de cécité : 12 h → passe, 6 jours → bloque, jamais mesuré → bloque
- compteur Polymarket sur rapport mixte : ancien 2 (faux), nouveau 1 (vrai)
