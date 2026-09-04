# Audit complémentaire — 04/09/2026, soir

Deux angles morts structurels, plus le mien.

## 1. health_check surveillait la fraîcheur par MTIME

`closing_lines.json` était contrôlé avec un seuil de 6 h... sur son mtime.
En CI, le mtime de tout fichier suivi par git est celui du **checkout**.
Mesuré sur votre dépôt au run de 18h43 :

    closing_lines.json   mtime = 18:43:52   <- date du checkout
    capture_state.json   last_capture_at = 18:40:17   <- la vraie capture

Cette section répondait donc ✅ quoi qu'il arrive — y compris si la capture
s'était arrêtée une semaine plus tôt. Le filet quotidien du projet ne
retenait rien. C'est le diagnostic qui avait donné `_age_interne_h()` dans
pipeline_status ce matin ; health_check était resté sur l'ancien mode.

`closing_lines.json` passe sous surveillance par **horodatage interne**
(`capture_state.json['last_capture_at']`). `backtest_tennis.csv` reste au
mtime : chargé à la main, seuil de 48 h, le décalage est absorbé.

## 2. Il ne surveillait pas l'API dont tout dépend

Section « Quota des clés API » : six clés `ODDS_API_KEY_1..6` de
**the-odds-api**, que plus aucun script de production n'utilise (reste
`games_markets.py`, orphelin). Si ces secrets n'existent pas, `check_key`
renvoie `None` et la section est vide en silence.

Pendant ce temps, **rien** ne surveillait OddsPapi/RapidAPI — l'API sur
laquelle repose toute la capture. Ajouté, pour 0 requête supplémentaire
(tout est déjà dans `capture_state.json`) :

- alerte si aucune capture depuis 6 h (`CAPTURE_MAX_H`)
- consommation du jour sur le budget de 938 req/jour, alerte à 90 %
- rappel des passages par déclencheur

Sortie sur vos données réelles :

    ✅ dernière capture il y a 0.4h
    ✅ requêtes OddsPapi aujourd'hui : 194/938 (21%)
    ℹ️ passages : repository_dispatch=4

Testé aussi en dégradé : capture vieille de 9 h -> ❌ ; quota à 93 % -> ❌.

## 3. Mon instrumentation du déclencheur ne pouvait pas conclure

Le compteur `passages_par_declencheur` posé ce matin s'incrémente juste
avant l'écriture de `capture_state.json`. Or un passage du cron `*/5` qui
trouve une capture de moins de 4 minutes fait `return` **avant** cette
écriture. Les passages du cron court-circuités n'apparaissaient donc nulle
part, et le compteur ne pouvait pas distinguer :

- « GitHub ne délivre pas le cron `*/5` »   (le vrai suspect)
- « le cron passe et se range poliment »

c'est-à-dire exactement les deux hypothèses qu'il devait départager.
Nouveau compteur `schedule_court_circuite`, écrit sans toucher aux champs
qui appartiennent au run qui capture.

État actuel de vos compteurs : `repository_dispatch: 4`, aucun `schedule`.
Demain matin, la lecture devient univoque :

- `schedule_court_circuite` proche de 288 -> le cron passe, le worker
  aussi, tout va bien et la cadence de 10 min vient d'ailleurs
- `schedule_court_circuite` autour de 100-150 -> GitHub étale le cron ;
  seul le worker peut tenir 5 min
- presque zéro -> le cron n'est pas délivré du tout

## Ce que j'ai vérifié sans rien trouver

- aucun autre livrable `.jsonl` surveillé (le piège `json.load` du soir ne
  concernait que `canal_public_log.jsonl`)
- aucun autre `json.load` sur un `.jsonl` dans les scripts
- budget API : 194/938 à 18h40, aucune tension
- `requirements.txt` bien utilisé par les 3 workflows qui installent
- 50 workflows sur les majeures Node 24, YAML et permissions valides
- aucune partition en zone rouge

## Toujours en attente de vous

`scripts/canal_public.py` reste absent. Le canal n'a rien publié depuis
10h48 ce matin. Je ne peux pas le réécrire sans l'avoir vu.
