# RUNBOOK — Purge de l'historique git (`git filter-repo`)
### À exécuter un dimanche matin creux · durée ~30 min · fenêtre de coupure ~15 min

**Objectif** : réduire la taille de l'HISTORIQUE. Le working tree et les
Releases (archives `ticks-YYYY-MM`) ne sont PAS touchés.

> ### ⚠️ RÉVISÉ LE 29/08/2026 — les cibles d'origine étaient les mauvaises
>
> La version initiale de ce runbook (25/08) visait `pm_ticks_*`, `kx_ticks_*`
> et `*.zip`, et annonçait « ~2,6 Go → 400-500 Mo ». Cette estimation était
> antérieure à toute mesure de l'historique. **Mesure faite le 29/08 sur un
> clone `--mirror` complet** (138 059 objets, `size-pack: 3.33 GiB`) :
>
> | Catégorie | Poids (top 25) | % du pack | Statut |
> |---|---|---|---|
> | `parts/live_*` | 683 Mo | 20,0 % | purgées à 3 j du working tree, blobs éternels |
> | **`*_curves_live.jsonl`** | **592 Mo** | **17,4 %** | **MORT** — gitignorés, absents de HEAD |
> | ticks pm/kx *(cible d'origine)* | 393 Mo | 11,5 % | archivés en Releases |
> | `closing_lines.json` | 169 Mo | 5,0 % | **ACTIF ET CRITIQUE — ne pas toucher** |
> | `set*_curves.jsonl` | 165 Mo | 4,8 % | absents de HEAD, à qualifier |
> | **Total top 25** | **2 002 Mo** | **58,7 %** | |
>
> Ces chiffres sont un **plancher** : ils ne portent que sur les 25 plus gros
> chemins. Le reste du pack (~1,4 Go) n'est pas ventilé.
>
> Conséquence : les ticks, seule cible du runbook d'origine, ne pèsent que
> 11,5 % du top 25. Purger uniquement ce que prévoyait la v1 ne ramènerait
> **pas** le dépôt à 400-500 Mo.
>
> **Reproduire la mesure** (5-10 min, ne touche à rien) :
> ```bash
> cd /tmp && rm -rf mesure
> git clone --bare --mirror https://github.com/Lucas987987/Tennis-edge.git mesure
> cd mesure && git count-objects -vH
> git rev-list --objects --all \
>   | git cat-file --batch-check='%(objecttype) %(objectsize:disk) %(rest)' \
>   | awk '$1=="blob"{s[$3]+=$2} END{for(f in s) printf "%10.1f Mo  %s\n", s[f]/1048576, f}' \
>   | sort -rn | head -25
> cd /tmp && rm -rf mesure
> ```
> ⚠️ Le clone **doit** être complet. Depuis un Codespace (cloné en
> `filter: blob:none`), `git rev-list --missing=allow-any` ne classe que les
> ~12 % de blobs présents localement et donne un palmarès **faux**. Essayé le
> 29/08 : le top 20 obtenu ainsi ne montrait aucun `curves_live`.

---
## Ordre d'attaque recommandé

### Étape A — `*_curves_live.jsonl` (~592 Mo, risque quasi nul)
Le meilleur rapport gain/risque, et de loin. Ces trois fichiers sont déjà
dans `.gitignore` (depuis la découverte de la croissance à 0,5 Go/jour),
**absents de HEAD**, et régénérés à chaque run par `curves_parts.py rebuild`.
Le filtre ne peut donc toucher aucun fichier suivi : pas de sauvegarde de
« ticks chauds » à orchestrer, pas de risque de perdre de la collecte récente.

```bash
git filter-repo \
  --path book_curves_live.jsonl \
  --path set1_curves_live.jsonl \
  --path set2_curves_live.jsonl \
  --invert-paths --force
```
Contrôle : `git count-objects -vH` doit montrer ~2,7-2,8 GiB (contre 3,33).

### Étape B — ticks pm/kx (~393 Mo), seulement si A ne suffit pas
C'est le filtre de la v1 ci-dessous. Il exige la sauvegarde des ticks chauds
non encore archivés (voir §2).

### Étape C — `parts/live_*` (~683 Mo) : À TRANCHER, PAS À PATCHER
Le plus gros poste, mais **une décision de fond, pas un nettoyage**. Ces
partitions sont purgées du working tree après `LIVE_DAYS=3`, donc plus
personne ne les lit au-delà de 3 jours — mais leurs blobs restent dans
l'historique pour toujours. Deux options :
  * les traiter comme les `*_curves_live.jsonl` (gitignorer, régénérer) ;
  * les garder versionnées et accepter la croissance.
Ne pas trancher sous pression un soir de purge. Vérifier d'abord qui les
lit réellement au-delà de 3 jours (`canal_clv.py` en dépend, cf. sa note
d'en-tête).

### Ne jamais purger
`closing_lines.json` (169 Mo) : snapshots T-25/T-15/T-7/T-3, cœur du calcul
de CLV, **irrécupérables**. Son poids vient de sa réécriture intégrale à
chaque capture, pas d'un défaut.

**Pourquoi une cérémonie** : c'est un force-push. Tout ce qui pousse pendant
la fenêtre serait perdu ou en conflit d'historique. Donc : on gèle, on purge,
on repousse, on dégèle. Aucune donnée de collecte n'est perdue : les
collecteurs rattrapent leur retard au premier cycle après réactivation.

---
## 0. Préparation (la veille, 5 min)
- [ ] Vérifier que l'archivage a tourné (Releases `ticks-2026-08` peuplée).
- [ ] Sur une machine/codespace : `pip install git-filter-repo`.
- [ ] Sauvegarde froide : `gh repo clone Lucas987987/Tennis-edge miroir -- --mirror`
      puis `zip -r miroir_$(date +%F).zip miroir` — à garder 1 semaine.

## 1. Geler les écrivains (T+0)
```bash
# a. Couper le déclencheur Cloudflare (dashboard Workers -> désactiver le cron)
# b. Désactiver TOUS les workflows qui poussent :
gh workflow list --repo Lucas987987/Tennis-edge --limit 60 \
  | awk '{print $NF}' | while read id; do gh workflow disable "$id" -R Lucas987987/Tennis-edge; done
# c. Attendre la fin des runs en cours :
gh run list -R Lucas987987/Tennis-edge --status in_progress
```

## 2. Purger (T+3 min)
```bash
git clone --mirror https://github.com/Lucas987987/Tennis-edge purge && cd purge
git filter-repo \
  --path-glob 'parts/pm_ticks_*' \
  --path-glob 'parts/kx_ticks_*' \
  --path-glob '*.zip' \
  --invert-paths --force
# Contrôle AVANT de pousser :
git count-objects -vH        # size-pack attendu : ~400-500 Mo
```
⚠️ Ce filtre retire AUSSI les partitions pm/kx du working tree de HEAD.
Les ticks des 7 derniers jours (pas encore archivés) doivent être
sauvegardés d'abord : depuis un clone normal,
`cp parts/pm_ticks_* parts/kx_ticks_* /tmp/ticks_chauds/` — et re-commités
à l'étape 4. (Alternative conservatrice : remplacer les deux path-glob par
`--path-glob 'parts/pm_ticks_2026-08-1*'` etc. pour ne purger que l'ancien.)

## 3. Repousser (T+10 min)
```bash
git push --force --mirror origin
```
GitHub recalcule sa taille sous quelques heures (le reflog serveur expire) —
la sentinelle du LENDEMAIN fera foi (branchée en quotidien dans
health_check.yml depuis le 29/08, 7h37 UTC).

## 4. Dégeler (T+12 min)
```bash
# a. Re-committer les ticks chauds sauvegardés (clone FRAIS obligatoire) :
git clone --depth 1 https://github.com/Lucas987987/Tennis-edge && cd Tennis-edge
cp /tmp/ticks_chauds/* parts/ && git add parts && git commit -m "Ticks chauds post-purge" && git push
# b. Réactiver les workflows :
gh workflow list -R Lucas987987/Tennis-edge --limit 60 \
  | awk '{print $NF}' | while read id; do gh workflow enable "$id" -R Lucas987987/Tennis-edge; done
# c. Réactiver le cron Cloudflare.
# d. Vérifier le premier cycle : Actions -> capture_closing vert, collecteurs verts.
```

## 5. Après (le jour même)
- [ ] Tous les codespaces existants sont OBSOLÈTES (ancien historique) :
      les supprimer sur github.com/codespaces, repartir de neufs (légers !).
- [ ] `python scripts/repo_sentinel.py` -> doit afficher une baisse nette.
      (L'objectif « < 1 Go » de la v1 supposait la purge des trois postes A+B+C ;
      l'étape A seule vise ~2,8-2,9 Go. GitHub recalcule sa taille sous
      quelques heures : la sentinelle du lendemain fait foi, pas celle du jour même.)
- [ ] Garder `miroir_*.zip` une semaine, puis supprimer.

## Annulation (si quoi que ce soit cloche à l'étape 3)
Le miroir de l'étape 0 EST le dépôt complet :
`cd miroir && git push --force --mirror origin` restaure tout à l'identique.
