# RUNBOOK — Purge de l'historique git (`git filter-repo`)
### À exécuter un dimanche matin creux · durée ~30 min · fenêtre de coupure ~15 min

**Objectif** : retirer de l'HISTORIQUE les blobs de ticks (pm/kx) et les
doublons brut/gz — ramener le dépôt de ~2,6+ Go à ~400-500 Mo. Le working
tree et les Releases (archives `ticks-YYYY-MM`) ne sont PAS touchés.

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
la sentinelle de dimanche prochain fera foi.

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
- [ ] `python scripts/repo_sentinel.py` -> doit afficher < 1 Go.
- [ ] Garder `miroir_*.zip` une semaine, puis supprimer.

## Annulation (si quoi que ce soit cloche à l'étape 3)
Le miroir de l'étape 0 EST le dépôt complet :
`cd miroir && git push --force --mirror origin` restaure tout à l'identique.
