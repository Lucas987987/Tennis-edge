# move_audit.py tué par l'OOM killer — détecté par l'observateur externe (30/08/2026)

    cp move_audit_oom/scripts/*.py scripts/
    cp move_audit_oom/.github/workflows/*.yml .github/workflows/

    python tests/test_pure_functions.py      # doit afficher 13/13

    git add -A
    git commit -m "move_audit.py : ne garder que les 5 champs utiles à build_index au lieu des enregistrements complets -- le script se faisait tuer par l'OOM killer, moves_detail_hist.csv figé à 32h"
    git pull --no-rebase --no-edit && git push

---

## L'observateur externe a fait exactement son travail

Créé le 29/08 pour détecter ce que `steam_pipeline` ne peut pas constater
sur lui-même. Son run du 30/08 à 14h29 :

    ✅ pipeline_status.md          : 8h
    ❌ moves_detail_hist.csv       : 32h (seuil 30h)
    ✅ set_results.json            : 24h
    ✅ polymarket_studies_report.md : 4h
    ✅ verdicts_geles.json         : présent

**L'abaissement du seuil de 36h à 30h (fait la veille, audit v13 §BH) est
ce qui a rendu ce cas visible** -- à 36h, ces 32h seraient passées
inaperçues.

## La cause, trouvée en testant sur les vraies données

`move_audit.py` se fait **tuer par l'OOM killer du noyau** (« Killed », pas
une exception Python). Ligne 120 : `_records.append(r)` accumulait
l'ENREGISTREMENT COMPLET de chaque ligne -- courbes de prix incluses,
l'essentiel du volume -- alors que `mk.build_index()`, seul consommateur de
cette liste, n'utilise que 5 champs légers (voir sa docstring : uid,
home/home_team, away/away_team, commence_time, fixture_id).

Le `|| true` dans `steam_pipeline.yml` rendait cet échec totalement
silencieux : le workflow restait vert, `moves_detail_hist.csv` figeait, et
rien ne le signalait -- jusqu'à l'observateur externe.

**Même mécanisme de panne** que celui qui m'avait fait refuser le chargeur
unique `index_book()` (point 4 du rapport consolidé) : un SIGKILL du noyau
n'est pas interceptable, aucun repli n'est possible. Sauf qu'ici le
problème existait déjà en production, il n'était juste pas visible.

## Le correctif, et sa garantie

`_records.append()` ne conserve plus que les 7 champs réellement utilisés
(les 5 de build_index + `tournament` utilisé dans `nat_rows`).

**Vérifié avant livraison** : le script tourne maintenant jusqu'au bout sur
les mêmes 12 partitions qui le tuaient, et sa sortie est **strictement
identique** à l'ancien fichier -- `diff` renvoie 0 ligne de différence sur
les 976 lignes. Le correctif ne change aucun résultat, il permet juste au
script de finir.

## Correctif secondaire : le diagnostic de l'observateur était trompeur

Il concluait « steam_pipeline ne tourne probablement plus » -- faux dans ce
cas précis : le pipeline tournait (`pipeline_status.md` frais à 8h), c'est
une étape À L'INTÉRIEUR qui échouait. Le message distingue maintenant les
deux cas (tous les témoins périmés = workflow mort ; certains frais et
d'autres non = étape silencieuse), avec le cas réel du 30/08 cité en
exemple.

## Tests : 13/13 (inchangé)
