# Retrait du cron GitHub + filet de sécurité — 04/09/2026

## 3 fichiers

| fichier | action |
|---|---|
| `.github/workflows/capture_closing.yml` | remplacer — le cron `*/5` est retiré |
| `.github/workflows/capture_watchdog.yml` | **créer** |
| `scripts/watchdog_capture.py` | **créer** |

## Pourquoi le cron part

Le compteur `passages_par_declencheur` posé ce matin a tranché : sur toute la
période d'observation, **uniquement `repository_dispatch`, pas un seul
`schedule`**. GitHub ne délivrait tout simplement pas le cron `*/5`.

Ce n'était donc pas un second déclencheur. C'était un faux filet de sécurité,
et c'est le pire genre : on croyait avoir une redondance là où il n'y avait
qu'un déclencheur unique.

## Pourquoi il faut un remplaçant

`watchdog_collecteurs.py` surveille Kalshi et Polymarket. **Personne ne
surveillait `capture_closing`**, parce qu'on supposait le cron en secours.
Or c'est le cœur du dispositif : sans capture, pas de closing lines, donc pas
de CLV, donc plus rien à valider.

`capture_watchdog.yml` tourne toutes les heures. Si aucune capture depuis
30 min : alerte Telegram **et** relance de `capture_closing.yml` par
`workflow_dispatch`. Le run passe en rouge — un watchdog qui se déclenche
doit se voir dans l'onglet Actions sans ouvrir un log.

Un cron horaire est acceptable là où le `*/5` ne l'était pas : un watchdog
livré avec 20 min de retard fait toujours son travail, une capture livrée
avec 20 min de retard a perdu son closing. C'est le seul usage où
l'irrégularité des crons GitHub est tolérable.

Testé : 4 min -> code 0 · 29 min -> code 0 · 95 min -> code 1 + relance +
alerte · `capture_state.json` absent -> code 1 (retard supposé maximal, même
parti pris que `watchdog_collecteurs.py`).

## Ce qui reste inexpliqué — et c'est côté worker

Vous dites que le worker passe toutes les 5 minutes. Ce serait 12 runs par
heure. Vous en comptez **6 ou 7**, et le compteur donne 8 passages entre
18h40 et 19h32. Les deux chiffres concordent : **les runs qui démarrent vont
au bout, il en démarre simplement la moitié.**

Le problème n'est donc pas dans le dépôt — il est entre le worker et
l'API GitHub. Trois pistes, par ordre de vraisemblance :

1. **Le `decide()` du worker filtre.** Le commentaire de
   `_envoyer_rapport_quotidien_telegram` note déjà un écart de 3,5x entre le
   budget théorique (~540 req/j selon le modèle de `decide()`) et le réel
   (~150 req/j). Si `decide()` ne dispatche que lorsqu'il juge utile, la
   cadence de 5 min est celle du cron du worker, pas celle des dispatches.
2. **Le cron Cloudflare n'est pas à 5 min** (`*/10` ? un `decide()` qui saute
   un tour sur deux ?).
3. **Des appels `POST /dispatches` échouent** sans que personne ne le voie —
   un 401/403/422 côté worker ne laisse aucune trace dans GitHub.

Ce qui trancherait : `wrangler tail` sur le worker pendant 30 min, ou un
compteur de réponses HTTP côté worker (un dispatch réussi renvoie **204**).
Si vous voyez 6 exécutions du worker par heure -> piste 2. Si vous en voyez
12 mais 6 dispatches -> piste 1. Si 12 dispatches mais 6 runs -> piste 3, et
là c'est un vrai bug GitHub à documenter.

## Note

Le garde-fou `SEUIL_CRON_SECOURS_MIN` de `capture_closing.py` devient
dormant : `GITHUB_EVENT_NAME` ne vaudra plus jamais `schedule`. Je le laisse
en place — il ne coûte rien et reprendrait son rôle si un cron était
réintroduit un jour. Le compteur `schedule_court_circuite` reste pour la
même raison ; s'il n'apparaît jamais, c'est normal et c'est la preuve que le
retrait était justifié.
