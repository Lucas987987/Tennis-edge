# Garde « échec bruyant » sur curves_parts.rebuild — 13/09/2026

## Le défaut

`rebuild(market)` sans aucune partition `parts/live_<market>_*.jsonl` :

- écrivait un fichier plat **vide**,
- retournait `0`,
- **ne signalait rien**.

Le pipeline enchaînait alors sur des courbes inexistantes. Aucune alerte
émise, aucun CLV mesurable, et rien dans les logs pour dire que la fenêtre
d'entrée avait disparu. Cinq workflows appellent ce `rebuild` :
`steam_pipeline`, `courbes_alertes`, `book_index`, `elo`, `steam_diag`.

C'est le même mode de panne que celui trouvé ce matin sur le canal : une
source tronquée qui produit un résultat d'apparence normale. Là-bas c'était
un « 0 % » publié ; ici ce serait un cycle sans alerte, indistinguable d'un
marché calme.

## Le correctif

Deux gardes, toutes deux levées par `AUTORISER_VIDE=1` :

1. **Zéro partition trouvée** → `SystemExit` avec le motif cherché et les
   causes usuelles (cache non restauré, checkout partiel, purge trop
   agressive).
2. **Partitions présentes mais zéro point retenu** → même traitement. Autre
   symptôme du même mal : partitions tronquées, ou toutes hors fenêtre de
   rétention.

Un fichier plat vide n'est jamais un état légitime en production : les
partitions sont écrites à chaque cycle de capture. Zéro partition veut dire
que quelque chose a disparu, pas que le marché est calme.

`AUTORISER_VIDE=1` couvre les cas réellement vides : premier démarrage,
tests, rejeu sur un dépôt neuf.

## Vérification

    # sans partition -> doit sortir en erreur
    mkdir -p /tmp/vide/parts && cd /tmp/vide
    python3 <depot>/scripts/curves_parts.py rebuild ; echo $?     # attendu : 1

    # échappatoire explicite
    AUTORISER_VIDE=1 python3 <depot>/scripts/curves_parts.py rebuild ; echo $?   # attendu : 0

    # dépôt réel -> inchangé
    cd <depot> && python3 scripts/curves_parts.py rebuild ; echo $?              # attendu : 0

Mesuré sur le dépôt au 13/09 : 2772 / 1598 / 1190 courbes reconstruites,
4 partitions par marché, exit 0. Comportement nominal inchangé.

## Ce que ce correctif prépare

Il est le prérequis du chantier de sortie des partitions live hors de git.

**Diagnostic.** `purge_data.purge_old_partitions()` supprime déjà
`parts/live_*` au-delà de `LIVE_DAYS=3`. Le projet accepte donc de les
perdre : ce ne sont pas des archives mais un **cache glissant de 3 jours**,
dont le seul rôle est d'alimenter `rebuild`. L'historique permanent est
ailleurs — `oddspapi_v5.py` écrit `parts/hist_<market>_<semaine>.jsonl`.

**Conséquence.** Les 2 469 Mo d'historique git occupés par `parts/live_*`
(47 % du dépôt avant purge) correspondent à un cache de ~210 Mo. On a
versionné éternellement toutes les versions intermédiaires d'un fichier
jeté au bout de trois jours.

**Direction.** Le cache GitHub Actions, pas une Release : `archive_ticks`
existe pour PRÉSERVER, or ici il n'y a rien à préserver. 10 Go par dépôt,
gratuit, hors historique git. Les partitions sortent du dépôt, le runner
les restaure au démarrage, les réécrit, sauvegarde le cache.

**Reste à trancher avant d'écrire** : sur cache manquant, le pipeline doit
échouer — c'est décidé — et cette garde est précisément le mécanisme qui le
fera. Restent à vérifier la cadence de sauvegarde du cache (clé glissante +
`restore-keys`) et l'effet sur les cinq workflows concernés.
