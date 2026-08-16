# Panne du push — cause identifiée et corrigée

## Bonne nouvelle d'abord

**Le pipeline a entièrement fonctionné.** Les 14 étapes ont tourné, tout a été produit :

| Livrable | Résultat |
|---|---|
| `set_results.json` | 1824 entrées (+62) |
| `moves_detail_hist.csv` | **830 lignes** |
| `moves_detail.csv` | 59 lignes |
| `canal_clv_detail.csv` | 19 lignes |
| `barometre_hebdo.md` | créé |
| `pipeline_status.json` / `.md` | créés |

Le commit local a réussi : `[main a9f3077] steam journal — 7 files changed, 1362 insertions(+)`.

**Seul le push a échoué.** Le travail n'est pas perdu, il est dans l'historique local du runner — mais un runner GitHub est détruit à la fin du job, donc ce commit-là est bien perdu. Il sera simplement recalculé au prochain run.

---

## La cause exacte

```
error: Your local changes to the following files would be overwritten by merge:
	scripts/__pycache__/oddspapi_v5.cpython-311.pyc
	scripts/__pycache__/steam_alert.cpython-311.pyc
Aborting
```

Enchaînement complet :

1. Trois fichiers `.pyc` sont **suivis par git** dans `scripts/__pycache__/`. Ils ont été ajoutés avant que `.gitignore` ne les couvre — et `.gitignore` **n'a aucun effet sur un fichier déjà suivi**. C'est le piège classique.
2. `capture_closing.yml` tourne toutes les 5-10 minutes avec `git add -A` (ligne 91). Comme les `.pyc` sont suivis, il republie une version neuve à chaque cycle.
3. `steam_pipeline` démarre, exécute Python, régénère ses propres `.pyc` localement — non commités, car sa liste `git add` est explicite.
4. `git merge origin/main` refuse d'écraser ces modifications locales et **abandonne**.
5. La branche locale reste en retard → `git push` rejeté en non-fast-forward.

Ce n'est donc pas un incident ponctuel : **tant que `capture_closing` continue de republier des `.pyc` toutes les 10 minutes, `steam_pipeline` ne pourra jamais pousser.** Ça explique aussi le run précédent, qui avait échoué exactement de la même façon sans qu'on puisse le voir.

Note au passage : l'instrumentation a payé immédiatement. Sans l'`exit 1` sur le push et sans `pipeline_status`, ce run se serait affiché en vert avec zéro fichier modifié, exactement comme les précédents.

---

## Correctif — deux parties, la première est indispensable

### 1. Détacher les `.pyc` (une seule fois, à la main)

Aucun workflow ne peut faire ça proprement : un `git rm --cached` depuis un runner créerait un conflit « supprimé par nous / modifié par eux » au merge suivant. À lancer une fois depuis un clone local :

```bash
git rm -r --cached scripts/__pycache__
git commit -m "Détache les .pyc du suivi git (bloquaient le merge puis le push)"
git push
```

À partir de là, `.gitignore` reprend son effet et le `git add -A` de `capture_closing` cesse de les réintroduire.

### 2. Déployer les 22 workflows ci-joints

- **`PYTHONDONTWRITEBYTECODE: '1'`** au niveau *workflow* (portée : toutes les étapes de tous les jobs) — plus aucun `.pyc` n'est généré, la classe entière de panne devient impossible.
- **Nettoyage défensif** avant toute opération git : suppression des `__pycache__` et `*.pyc` du disque, pour les runners ayant encore des reliquats.

Les 39 workflows du repo restent valides en YAML (vérifié).

---

## À vérifier après déploiement

Relance `Steam Pipeline` et regarde `pipeline_status.md` **sur GitHub**. Si le fichier apparaît avec un horodatage frais, le push fonctionne. Trois ❌ sont attendus et normaux :

- `resultats_derived.json` — produit uniquement par `Opening Value` et `Calibration Buckets`, pas par ce pipeline
- `paper_trades_set2.jsonl` — aucun pari set 2 dénoué à ce jour
- rien d'autre ne devrait être en ❌ ou ⏳

---

## Rappel du point en attente

`parts/hist_book_2026-W33.jsonl` est à 97,7 Mo (gelé, sans danger immédiat) et `parts/` pèse 634 Mo avec environ +80 Mo par semaine. `purge_old_partitions()` ne filtre que `parts/live_*`, jamais `parts/hist_*`. Décision à prendre avant un mois : sortir l'historique de git, ou compresser les partitions anciennes.
