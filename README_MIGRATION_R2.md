# Migration R2 — mode d'emploi (15/10/2026)

Le dépôt pèse **5,24 Go** et grossit chaque jour. Les fichiers qui changent à
chaque run partent vers Cloudflare R2 :
- les ticks Polymarket et Kalshi (`parts/pm_ticks_*`, `parts/kx_ticks_*`) ;
- les courbes live (`parts/live_*`).

Et `clv_history.jsonl` (83 Mo, le mur GitHub est à 100 Mo) est découpé par mois.

Le principe tient en trois règles :

- **Rien n'est jamais réécrit dans l'historique git.** Aucun `git push --force`,
  nulle part. Tout se fait par commits et push normaux.
- **Une seule variable pilote tout** : `R2_PRIMARY` = `off` | `double` | `on`.
- **Filet git permanent** : une partition ne quitte un commit que si R2 en a
  une copie **identique** (même empreinte SHA-256). En cas de doute, elle
  reste dans git. Le pire cas, c'est de la croissance, jamais une perte.

---

## Ce que contient la livraison

| Fichier | Rôle |
|---|---|
| `scripts/r2_io.py` (nouveau) | Le seul accès à R2 : lecture, écriture, liste, manifestes, rapatriement. Sans secrets, il ne fait rien et le dit. |
| `scripts/r2_parts.py` (nouveau) | Les commandes des workflows : `pull`, `push`, `gate`, `verify`, `status`. |
| `scripts/clv_store.py` (nouveau) | `clv_history` par mois : lecture, ajout, migration, vérification. |
| `Tennis_Edge_Lab/clv_source.py` (nouveau) | La même lecture pour le Lab. |
| `.github/workflows/r2_parts_verify.yml` (nouveau) | Compare R2 et git chaque jour à 06:47 UTC. Lecture seule. |
| `.github/workflows/clv_migration.yml` (nouveau) | Découpe `clv_history.jsonl`, en deux étapes manuelles. |
| 21 workflows modifiés | Les collecteurs et les courbes live envoient vers R2. Les lecteurs rapatrient depuis R2 en mode `on`. |
| 25 scripts modifiés (+ 4 du Lab) | Les lecteurs de `clv_history` passent par `clv_store`. `restore_curves` lit R2 avant les releases. `archive_ticks` ne crée plus de release en mode `on`. Le shadow V6.4 n'écrit plus à chaque tick. |
| `tests/test_r2_io.py`, `test_r2_parts.py`, `test_clv_store.py`, `r2_fakes.py` | 35 tests nouveaux. La suite complète passe : 124 tests dans `tests/`, 137 dans le Lab. |
| `RUNBOOK_FILTER_REPO.md`, `LISEZMOI*.md` | Marqués **OBSOLÈTE — INTERDIT** (force-push). |
| `scripts/repo_sentinel.py` | Ne recommande plus `git filter-repo`. |

---

## Étape 0 — Appliquer la livraison (Codespaces, 10 min)

1. Ouvrir un Codespace **neuf** sur `main`.
2. Créer une branche :
   ```bash
   git switch -c feat/r2-primary
   ```
3. Téléverser `r2_livraison.zip` dans le Codespace (glisser-déposer dans
   l'explorateur), puis :
   ```bash
   unzip -o r2_livraison.zip -d /tmp/r2 && git apply --3way /tmp/r2/r2_migration.patch
   ```
   Si `git apply` signale un conflit (un fichier a changé sur `main` depuis
   le 15/10 à 17:01 UTC), arrêtez-vous et envoyez-moi le message. Sinon :
   ```bash
   git status   # 57 fichiers modifiés, 11 nouveaux
   ```
4. Lancer les tests (2 min) :
   ```bash
   python -m unittest discover -s tests && python -m unittest discover -s Tennis_Edge_Lab/tests
   ```
   Il faut lire `OK` deux fois.
5. Committer et pousser **normalement** :
   ```bash
   git add -A && git commit -m "Migration R2 : partitions ticks/live + clv_history mensuel"
   git push -u origin feat/r2-primary
   ```
6. Sur github.com : ouvrir la Pull Request **feat/r2-primary → main**, puis
   **Merge** (bouton vert, merge normal).

Dès le merge, les workflows tournent en mode **double**, même sans variable
(c'est la valeur par défaut). Git reste la source de vérité, R2 reçoit une
copie.

## Étape 1 — Secrets et variable (GitHub, 2 min)

Côté Cloudflare, **il n'y a rien à créer**. Le compartiment
`tennis-edge-courbes` et les trois secrets existent déjà : `courbes_r2.yml` s'en
sert toutes les heures.

1. **Settings → Secrets and variables → Actions → onglet Secrets** : vérifier
   que `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` et `R2_ENDPOINT` sont bien là.
2. Onglet **Variables → New repository variable** :
   - Nom : `R2_PRIMARY`, valeur : `double`.
3. Variable `R2_V64_SHADOW_ENABLED` : la laisser à `false` ou absente. Le
   shadow V6.4 est remplacé par ce nouveau chemin.

## Étape 2 — Contrôler les premiers runs (le jour même)

Dans **Actions**, ouvrir un run de chacun de ces workflows :

| Workflow | Étape à regarder | Ce qu'il faut lire |
|---|---|---|
| Kalshi Collector | « R2 — envoyer les partitions (kx) » | `↑ kx_ticks_…` puis `opérations R2 : classe A=2` |
| Polymarket Collector | « R2 — envoyer les partitions (pm) » | idem avec `pm_ticks_…` |
| Courbes live + alertes | « R2 — envoyer les partitions (live) » | 3 lignes `↑ live_…`, `classe A=4` |

Au **premier** run de chaque collecteur, il y a 8 envois au lieu de 2 : les 7
jours déjà dans git partent une fois pour toutes. C'est normal.

Un message `::warning:: … reste dans git` n'est pas une panne : la donnée est
dans git comme avant. S'il revient à chaque run, envoyez-moi le log.

## Étape 3 — Découper `clv_history.jsonl` (5 min, puis 3 jours d'attente)

1. **Actions → « CLV — partitionner clv_history (migration) » → Run
   workflow**, étape = `migrer`.
2. Dans le log, chercher :
   `clv_store verify — ✅ 4222 lignes de l'ancien fichier retrouvées à
   l'identique`. Le nombre réel peut être plus grand.

   Cinq fichiers apparaissent dans `clv_history/` (juin → octobre). L'ancien
   fichier reste en place comme sauvegarde, mais n'est plus ni lu ni écrit.
   Relancer `migrer` est sans risque : le workflow vérifie et ne refait rien.
3. **Au moins 3 jours plus tard**, après plusieurs runs « Fetch CLV » verts,
   relancer le même workflow avec étape = `supprimer_ancien`. Il revérifie
   octet pour octet avant de retirer `clv_history.jsonl`, qui reste dans
   l'historique git.

## Étape 4 — Phase « double » : 7 jours minimum

Le workflow **« R2 — vérifier partitions (R2 vs git) »** tourne seul chaque
matin. Il compare chaque partition des jours clos (empreinte et nombre de
lignes).

- ✅ vert = R2 et git sont identiques.
- ❌ rouge = **ne pas passer en `on`** ; envoyez-moi le tableau du résumé.

On peut le lancer à la main à tout moment (bouton Run workflow).

**Critère de bascule** : **7 vérifications vertes consécutives**. Les 7 jours
de ticks gardés dans git sont alors tous passés par R2 et ont été comparés.

## Étape 5 — Bascule « on » (1 min)

**Settings → Variables → `R2_PRIMARY` → `on`.** Aucune autre action, aucun
gel des workflows : chaque run lit la variable à son démarrage.

À partir de là :
- Les collecteurs reprennent la partition du jour depuis R2, la prolongent,
  la renvoient, et `gate` la retire du commit. Le log affiche :
  `gate — mode on : 1 partition(s) retirée(s) du commit (déjà dans R2)`.
- Les commits « Kalshi collector », « Polymarket collector » et « Courbes
  live » ne contiennent plus de `parts/…`.
- Les lecteurs (steam_pipeline, études Polymarket, Lab, suivi) rapatrient
  depuis R2 les jours qui leur manquent (7 jours de ticks, 3 jours de live,
  comme avant dans git).
- `archive_ticks` ne crée plus de release. Il vérifie que R2 détient bien
  chaque vieille partition, puis retire la copie git. La ligne d'index
  devient `r2:parts/ticks/<fichier>`.
- La vérification quotidienne reste verte : en `on`, « R2 plus complet que
  git » est l'état normal.

**À surveiller les 48 premières heures** : runs des collecteurs verts,
`archive_ticks` (05:15 UTC) affiche `Bilan R2 : … retiré(s)`, et la
sentinelle de taille ralentit nettement.

---

## Retour arrière (à tout moment, en 1 minute, sans perte)

| Situation | Action |
|---|---|
| Un doute en phase `on` | `R2_PRIMARY` → `double`. Dès le run suivant, les partitions repartent dans git. La partition du jour est reprise depuis R2, rien n'est écrasé. |
| Couper R2 complètement | `R2_PRIMARY` → `off`. **Seulement depuis `double`.** Depuis `on`, repasser d'abord une journée en `double`. |
| Retirer le code | Sur github.com, **Revert** de la Pull Request (bouton sur la PR fusionnée), puis merge du revert. Jamais de force-push. |
| `clv_history` | Tant que l'étape `supprimer_ancien` n'a pas tourné, l'ancien fichier est intact. Après, il reste dans l'historique git (`git show <commit>:clv_history.jsonl`). |

Les objets R2 ne sont jamais supprimés par ce code.

---

## Coût R2 (offre gratuite : 10 Go, 1 M opérations A et 10 M B par mois)

| | par run | runs/jour | par jour |
|---|---|---|---|
| Collecteur Kalshi | 2 A + 2-4 B | ~80 | ~160 A |
| Collecteur Polymarket | 2 A + 2-4 B | ~80 | ~160 A |
| Courbes live | 4 A + 3-6 B | ~240 | ~960 A |
| Vérification, lecteurs | ~3 LIST + GET | — | < 5 000 B |

Total : **~1 300 opérations A par jour, soit ~40 000 par mois (4 % du
gratuit)**, et moins de 3 % des opérations B. Les sorties de R2 sont
gratuites.

Le stockage croît d'environ 20 Mo par jour (~0,6 Go par mois). Dans
Cloudflare → R2 → `tennis-edge-courbes` → Metrics, surveiller une fois par
mois la taille totale. Au-delà de ~8 Go, il faudra une politique d'âge sur
`parts/live/`.

---

## Ce qui reste pour plus tard (pas maintenant)

1. **`closing_lines.json`** : environ 275 versions × 9,5 Mo par jour, c'est
   désormais le plus gros contributeur. L'alléger (matchs terminés vers une
   archive mensuelle) touche fetch_clv, value_journal, capture_quality… Ce
   n'est pas trivial, donc pas fait ici. Prochaine étape conseillée.
2. **`polymarket_markets.json`, `kalshi_markets.json`, `resultats_derived.json`**
   (~420 versions par jour) : même traitement à étudier.
3. **Nettoyage `.gitignore`** (après 1 mois en `on`) : ajouter
   `parts/pm_ticks_*`, `parts/kx_ticks_*` et `parts/live_*`, pour qu'un
   ancien workflow ne puisse plus jamais les committer.
4. **Nouveau dépôt propre** : l'historique déjà accumulé (5,24 Go) ne
   rétrécira pas, car rien n'est réécrit. Le jour où ce sera nécessaire, à
   froid et sans urgence : copie de l'état actuel dans un nouveau dépôt,
   l'ancien archivé en lecture seule. Aucun force-push.
5. `suivi_collecteurs` mesure la « dernière publication » par l'historique
   git. En `on`, il voit les commits d'état des collecteurs, pas ceux des
   ticks. Le rapport reste utile mais moins précis. À adapter sur le
   manifeste R2 (`updated_at`).
6. Le shadow V6.4 (`r2_collector_sink.py`) n'envoie plus rien pendant la
   collecte, mais crée encore un segment par tick. Il est remplacé par
   `r2_parts.py` : le laisser désactivé.

---

## Branches supprimables (à la main, sur github.com → Branches)

Déjà contenues dans `main` ou remplacées :
- `feat/r2-v64-partition-worker`, `feat/r2-v64-single-write-gate`
- `feat/r2-v64-progressive-archive-batches-current`, `feat/r2-v64-progressive-archive-batches-v2`
- `feat/r2-v64-restore-audits-20261010-11`, `feat/r2-v64-restore-kalshi-2026-10-10`
- `feat/r2-v64-restore-kalshi-pr`, `feat/r2-v64-restore-polymarket-pr`
- `fix/ci-r2-isolation-allowlist`
- `feature/tennis-edge-v6-4-storage-phase1` (ancienne conception, remplacée)
- `test/r2-v64-final-validation`, `test/r2-v64-first-write-check`, `test/r2-v64-perf-validation`
- `test/r2-v64-probe`, `test/r2-v64-replay-validation`
- `test/r2-worker-sandbox-run`, `test/r2-worker-sandbox-run2`

À garder jusqu'à la phase `on`, puis supprimable : `feat/tick-publish-per-run`.
C'est un prototype de publication des ticks par branche ; R2 rend le problème
caduc.
