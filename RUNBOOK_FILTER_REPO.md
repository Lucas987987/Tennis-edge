# RUNBOOK — Purge de l'historique git (`git filter-repo`)
### À exécuter un dimanche matin creux · durée ~60 min · fenêtre de coupure ~30 min

**Objectif** : réduire la taille de l'HISTORIQUE. Le working tree et les
Releases (archives `ticks-YYYY-MM`) ne sont PAS touchés.

> ### ✅ EXÉCUTÉ LE 12/09/2026 — 5,16 GiB → 962,80 MiB, sans perte
>
> Purge réelle menée de bout en bout. Les sections qui suivent ont été
> réécrites à partir de ce qui s'est effectivement passé, pas de ce qui
> était prévu. **Lis d'abord « Ce qui a coûté du temps » plus bas** : quatre
> pièges ont mangé deux heures, aucun n'était dans la v2.
>
> | | avant | après |
> |---|---|---|
> | `size-pack` | 5,16 GiB | **962,80 MiB** |
> | objets | 260 091 | 213 838 |
> | commits réécrits | — | 47 160 |
> | clone `--depth 1` | 347 MiB | 265 MiB |
>
> Aucune ligne de collecte perdue : partitions chaudes sauvées avant la
> purge et recommitées après (commit `89b721d`).

> ### ⚠️ LA VENTILATION BOUGE VITE — REMESURER EST OBLIGATOIRE
>
> Mesure du 12/09 (clone `--mirror` complet, 5 252 Mo ventilés) :
>
> | Catégorie | Poids | % | 29/08 |
> |---|---|---|---|
> | `parts/live_*` | 2 469 Mo | **47,0 %** | 20,0 % |
> | ticks pm/kx | 1 045 Mo | 19,9 % | 11,5 % |
> | `*_curves_live.jsonl` | 608 Mo | 11,6 % | 17,4 % |
> | `parts/hist_*` | 523 Mo | 10,0 % | **à garder** |
> | `closing_lines.json` | 358 Mo | 6,8 % | **intouchable** |
> | autres | 248 Mo | 4,7 % | dont ~193 Mo morts |
> | `*.zip` | 0 Mo | 0,0 % | non-sujet |
>
> En quatorze jours, `parts/live_*` est passé de 20 % à 47 % et
> `curves_live` de 17 % à 12 %. **L'étape A du runbook v2, appliquée seule
> le 12/09, aurait rendu 600 Mo au lieu de 4,2 Go.** Ne jamais purger sur
> une ventilation vieille de plus de quelques jours.
>
> Les 193 Mo « morts » dans *autres* : `book_curves.jsonl`,
> `set1_curves.jsonl`, `set2_curves.jsonl` — absents de HEAD depuis la
> migration vers `parts/hist_*` (`migrate_hist_partitions.py`), le code les
> référence encore par leur nom d'origine mais `ov.open_curves()` redirige.
>
> **Reproduire la mesure** (5-10 min, ne touche à rien) :
> ```bash
> cd /tmp && rm -rf mesure
> git clone --bare --mirror https://github.com/Lucas987987/Tennis-edge.git mesure
> cd mesure && git count-objects -vH
> git rev-list --objects --all \
>   | git cat-file --batch-check='%(objecttype) %(objectsize:disk) %(rest)' \
>   | awk '$1=="blob"{s[$3]+=$2} END{for(f in s) printf "%10.1f Mo  %s\n", s[f]/1048576, f}' \
>   | sort -rn > /tmp/blobs.txt
> head -40 /tmp/blobs.txt
> ```
> ⚠️ Le clone **doit** être complet. Depuis un Codespace (cloné en
> `filter: blob:none`), `git rev-list --missing=allow-any` ne classe que les
> ~12 % de blobs présents localement et donne un palmarès **faux**. Essayé le
> 29/08 : le top 20 obtenu ainsi ne montrait aucun `curves_live`.

---
## Ce qui a coûté du temps le 12/09 (à lire AVANT de commencer)

**1. `filter-repo` supprime le remote `origin`.** C'est délibéré de sa part,
pour empêcher un force-push réflexe. Le message `NOTICE: Removing 'origin'
remote` défile au milieu de la sortie et se rate facilement. Deux tentatives
de push ont échoué sur `fatal: 'origin' does not appear to be a git
repository` avant qu'on comprenne. À faire systématiquement après le filtre :

```bash
git remote add origin https://github.com/Lucas987987/Tennis-edge.git
```

**2. Le `GITHUB_TOKEN` du Codespace n'a pas le scope `workflow`.** La boucle
de gel renvoie `HTTP 403` sur les 52 workflows, et `gh auth refresh` refuse
parce que la variable d'environnement prend le pas. La séquence qui marche :

```bash
unset GITHUB_TOKEN GH_TOKEN
gh auth login -h github.com -s workflow -w   # code à saisir sur github.com/login/device
gh auth status                               # vérifier 'workflow' dans les scopes
```

**3. Couper le cron Cloudflare NE SUFFIT PAS.** 20 workflows ont leur propre
`schedule:` — dont `steam_pipeline`, `fetch_book_curves`, `capture_watchdog`,
`archive_ticks`, `update_results`. Vérifier avant de croire au gel :

```bash
grep -l "schedule:" .github/workflows/*.yml
```

Corollaire utile : désactiver les workflows côté GitHub **suffit**, même si
le Worker Cloudflare continue d'appeler — un workflow désactivé reçoit
l'appel et ne fait rien. Pas besoin de toucher au dashboard Cloudflare.

Un workflow (`284757662`) renvoie `403` au `disable` et `422` à l'`enable` :
il est supprimé du dépôt mais encore référencé par l'API. Sans effet, ignorer.

**4. Sauver le chaud depuis un clone `--mirror` est impossible.** Un miroir
est *bare*, il n'a pas de working tree : `cp parts/live_* …` renvoie
`No such file or directory` et `/tmp/chauds` reste vide. La copie se fait
depuis `/workspaces/Tennis-edge`, après un `git pull`.

**5. Ne pas coller plusieurs commandes d'un bloc pendant un push.** Les
lignes en attente sont avalées par le processus en cours et le terminal se
désynchronise (affichage figé sur un fragment type `B/Receiving`). Une
commande, une Entrée. Si le terminal décroche : le fermer, en ouvrir un neuf.

---
## Vérifications qui font foi

Trois contrôles, dans cet ordre, **avant** le `push --force` :

```bash
git count-objects -vH            # size-pack dans la fourchette attendue
ls /tmp/chauds | wc -l           # ~30 fichiers, PAS 0
gh run list -R Lucas987987/Tennis-edge --status in_progress   # doit sortir vide
```

Et après le push, le seul qui prouve qu'il est passé :

```bash
git ls-remote origin refs/heads/main    # doit montrer le hash du clone purgé
```

`filter-repo` réécrit tous les hachages : comparer `git log --oneline -1` du
clone purgé et du distant est le test le plus direct. S'ils diffèrent, le
push n'a pas eu lieu, quoi qu'ait affiché le terminal.

---
## Le filtre — un seul passage, toutes les cibles

La v2 proposait trois étapes A/B/C à faire dans l'ordre. **Mauvaise idée** :
la fenêtre de gel s'ouvre une fois, autant tout prendre. C'est le filtre
appliqué le 12/09, validé, 4,2 Go sur 5,25 Go ventilés.

```bash
git filter-repo \
  --path book_curves_live.jsonl \
  --path set1_curves_live.jsonl \
  --path set2_curves_live.jsonl \
  --path book_curves.jsonl \
  --path set1_curves.jsonl \
  --path set2_curves.jsonl \
  --path-glob 'parts/live_*' \
  --path-glob 'parts/pm_ticks_*' \
  --path-glob 'parts/kx_ticks_*' \
  --invert-paths --force
```

Trois familles, trois niveaux de risque :

- **Risque nul** — `*_curves_live.jsonl` et les trois `*_curves.jsonl` plats :
  absents de HEAD, aucun fichier suivi touché. Les premiers sont régénérés
  par `curves_parts.py rebuild`, les seconds ont migré vers `parts/hist_*`.
- **Sauvegarde obligatoire** — `parts/live_*` et les ticks pm/kx : ces
  `--path-glob` les retirent AUSSI du working tree de HEAD. Sans la copie
  préalable (§2), tu perds les 3 derniers jours de partitions live et les
  ticks pas encore archivés en Release.

La réserve de la v2 sur `parts/live_*` (« à trancher, qui les lit au-delà de
3 jours ? ») **est levée** : `canal_clv.py` est passé en registre append-only
le 16/08 et lit `parts/hist_*`. Personne ne lit les live au-delà de
`LIVE_DAYS`. Le poste pèse 47 %, il n'y a plus de raison de l'épargner.

### Ne jamais purger
`closing_lines.json` (358 Mo au 12/09) : snapshots T-25/T-15/T-7/T-3, cœur
du calcul de CLV, **irrécupérables**. Son poids vient de sa réécriture
intégrale à chaque capture, pas d'un défaut.

`parts/hist_*` (523 Mo) : l'historique permanent depuis la migration. Lu par
`move_audit`, les pistes, `canal_clv`. Ne jamais mettre dans un filtre.

**Pourquoi une cérémonie** : c'est un force-push. Tout ce qui pousse pendant
la fenêtre serait perdu ou en conflit d'historique. Donc : on gèle, on purge,
on repousse, on dégèle. Aucune donnée de collecte n'est perdue : les
collecteurs rattrapent leur retard au premier cycle après réactivation.

---
## 0. Préparation (la veille, 5 min)
- [ ] Vérifier que l'archivage a tourné (Releases `ticks-2026-MM` peuplée).
- [ ] `pip install git-filter-repo` **et** `git filter-repo --version` :
      le paquet n'est pas présent par défaut dans un Codespace neuf.
- [ ] Scope `workflow` sur le CLI (voir piège n°2 plus haut).
- [ ] Sauvegarde froide : `git clone --mirror https://github.com/Lucas987987/Tennis-edge.git miroir`
      — un **miroir**, pas un zip du working tree : c'est le seul rollback
      possible après un force-push. À garder une semaine.
- [ ] Prévoir 60 min sans interruption. Ne pas commencer ce qu'on ne peut
      pas finir : entre le force-push et la restauration du chaud, le dépôt
      a un `parts/` amputé.

## 1. Geler les écrivains (T+0)
```bash
gh workflow list -R Lucas987987/Tennis-edge --limit 60 \
  | awk '{print $NF}' | while read id; do gh workflow disable "$id" -R Lucas987987/Tennis-edge; done
gh run list -R Lucas987987/Tennis-edge --status in_progress
```
Répéter la seconde commande jusqu'à `no runs found`. Le cron Cloudflare peut
rester actif : un workflow désactivé ne démarre pas.

## 2. Sauver le chaud (T+5 min) — depuis le WORKING TREE
```bash
cd /workspaces/Tennis-edge && git pull --no-rebase --no-edit
rm -rf /tmp/chauds && mkdir -p /tmp/chauds
cp parts/live_* parts/pm_ticks_* parts/kx_ticks_* /tmp/chauds/
ls /tmp/chauds | wc -l          # ~28-30 ; si 0, NE PAS CONTINUER
```
À refaire si des runs ont fini entre-temps : une copie antérieure au gel est
déjà incomplète.

## 3. Purger (T+10 min) — clone FRAIS, après le gel
```bash
cd /tmp && rm -rf purge && git clone --mirror https://github.com/Lucas987987/Tennis-edge.git purge && cd purge
# ... le filtre de la section précédente ...
git remote add origin https://github.com/Lucas987987/Tennis-edge.git   # filter-repo l'a retiré
git count-objects -vH
```
Un clone antérieur au gel est périmé : le repousser effacerait ce que les
collecteurs ont produit depuis.

## 4. Repousser (T+25 min)
```bash
git push --force --mirror origin
git ls-remote origin refs/heads/main     # doit montrer le hash du clone purgé
```
Compter 3 à 6 min pour ~1 Go. Les `remote: warning: File … is larger than
GitHub's recommended maximum file size of 50.00 MB` sur les `parts/hist_*`
sont informatifs, pas bloquants.

## 5. Restaurer le chaud (T+30 min) — enchaîner SANS PAUSE
```bash
cd /tmp && rm -rf frais
git clone --depth 1 https://github.com/Lucas987987/Tennis-edge.git frais && cd frais
ls parts/ | wc -l               # ~35 ; si c'est encore 63, le push n'est pas passé
cp /tmp/chauds/* parts/
git add parts && git commit -m "Partitions chaudes post-purge" && git push
```
Le `ls parts/` est le contrôle décisif : s'il montre encore les `live_*`,
c'est que le distant n'a pas changé et que `git status` ressortira
« nothing to commit » — symptôme trompeur qui fait croire à un problème de
`.gitignore` alors que le push a échoué.

## 6. Dégeler (T+35 min)
```bash
gh workflow list -R Lucas987987/Tennis-edge --limit 60 \
  | awk '{print $NF}' | while read id; do gh workflow enable "$id" -R Lucas987987/Tennis-edge; done
gh run list -R Lucas987987/Tennis-edge --limit 5
```
`capture_closing` doit repasser au vert au cycle suivant.

## 7. Après (le jour même)
- [ ] **Supprimer TOUS les Codespaces** sur github.com/codespaces, y compris
      celui qu'on vient d'utiliser. Ils portent l'ancien historique ; un
      `git pull` depuis l'un d'eux réintroduirait les Go purgés. C'est le
      seul vrai risque résiduel.
- [ ] Les hachages de tous les commits ont changé (47 160 réécrits le
      12/09). Le contenu est intact ; les références à un SHA dans des notes
      ou des issues sont caduques.
- [ ] La sentinelle du **lendemain** fait foi : GitHub met quelques heures à
      recalculer sa taille.
- [ ] Garder `miroir_*` une semaine, puis supprimer.

---
## Ce que la purge ne règle pas

Croissance mesurée entre le 29/08 (3,33 GiB) et le 12/09 (5,16 GiB) :
**~120 Mo/jour**. À ce rythme le seuil de 4 Go revient vers mi-octobre.

Le poste responsable est `parts/live_*` : ~70 Mo/jour de partitions
réécrites et commitées à chaque cycle. Elles ne peuvent pas être
gitignorées comme les `*_curves_live.jsonl` — ce sont des sources, pas des
dérivés, et sans commit elles disparaissent entre deux runs sur un runner
éphémère.

La sortie structurelle existe déjà dans le dépôt : le mécanisme de
`archive_ticks.py` (téléverser en Release, ne supprimer qu'après succès
confirmé). L'étendre aux partitions live — le runner télécharge la partition
du jour au démarrage, la réécrit, la téléverse — sortirait ~70 Mo/jour de
git définitivement et rendrait cette cérémonie exceptionnelle au lieu de
trimestrielle. **Chantier à part, à faire à froid.**

## Annulation (si quoi que ce soit cloche après l'étape 4)
Le miroir de l'étape 0 EST le dépôt complet :
`cd miroir && git push --force --mirror origin` restaure tout à l'identique.
C'est la raison pour laquelle la sauvegarde doit être un `--mirror` et pas
une archive du working tree : un zip ne contient pas l'historique.
