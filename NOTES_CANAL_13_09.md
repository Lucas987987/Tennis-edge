# Correctif canal — 13/09/2026

## Le symptôme

Message publié le 12/09 pour la journée du 11/09 :

    2 matchs signalés (3 écarts) · 0 se sont refermés (0%)
    Le plus net  : bet365 3.25 → 3.25 sur Daniil Glinka (+0%)
    Le moins bon : bet365 3.25 → 3.25 sur Daniil Glinka (+0%)

Deux anomalies visibles : les deux extrêmes désignent la même ligne, et
l'écart 22bet sur Arthur Weber (annoncé 6,1 % puis 9,5 %) n'apparaît nulle
part alors qu'il compte dans les 3.

## La cause

`canal_clv.load_closes()` et `canal_suivi.load_closes()` parcourent une
cascade de sources et gardaient **le premier résultat trouvé** :

    if k not in closes:            # priorité à la 1re source
        closes[k] = (pts[-1][1], origine)

La première source est `book_curves_live.jsonl`, une fenêtre **glissante**
reconstruite à chaque cycle. Quand elle ne couvre pas la fin de la fenêtre
pré-match d'un match, son dernier point est plus ANCIEN que celui des
partitions — et c'est pourtant lui qui était retenu. La fraîcheur d'une
source ne dit rien de sa complétude.

Vérifié sur les partitions de ticks : l'écart 22bet sur Weber a été mesuré
`2.694 → 2.694`, soit 0 %. Le prix a réellement fini à **2.32 avant le coup
d'envoi, soit +16 %**. Deux lignes fausses sur trois dans ce message, et dans
le sens qui dessert le canal.

Second défaut, dans `canal_suivi` seulement : sa cascade est lue avec un
`open()` brut. Depuis la migration de `book_curves.jsonl` vers `parts/hist_*`,
le deuxième maillon ne donnait plus rien — il ne restait qu'une seule source,
la fenêtre glissante.

## Les correctifs

1. **Point pré-match le plus tardif** (les deux scripts) : on compare
   l'horodatage du dernier point de chaque source et on garde le plus récent,
   quelle que soit la source qui le fournit.
2. **`canal_suivi` passe par `ov.open_curves`**, comme `canal_clv` et
   `move_audit` — les partitions redeviennent accessibles.
3. **Garde de complétude** (`MARGE_MIN`, défaut 60 min) : aucun écart n'est
   mesuré, et surtout **aucune ligne n'est gelée au registre**, avant le coup
   d'envoi + marge. Le gel de `canal_clv` est définitif : ne rien geler coûte
   un jour, geler faux coûte pour toujours. Ce n'était pas la cause du cas
   Weber (le match avait commencé 4 h avant la publication), c'est une
   assurance bon marché.
4. **Prix inchangé distingué** : 71 lignes sur 226 sont à exactement 0 %, dont
   27 sur bet365 — des opérateurs qui ne retouchent jamais leur prix. Le
   message le dit désormais explicitement. **Le taux publié ne change pas** :
   il reste calculé sur tous les matchs. Sortir les prix figés du dénominateur
   remonterait le pourcentage affiché, et c'est un choix éditorial à assumer,
   pas un effet de bord d'un correctif technique.
5. **Extrêmes identiques** : quand toutes les valeurs sont égales, une seule
   ligne « Tous à X % — par exemple … » au lieu de deux lignes jumelles.
6. **`NOW_OVERRIDE`** dans les deux scripts : une règle qui dépend de l'heure
   ne se teste pas si l'heure n'est pas injectable.

## Vérification

`verifier_canal.sh` passe en deux temps. Le test fonctionnel rejoue le cas
réel du 11/09 avec une source `live` tronquée en tête de cascade et les
partitions derrière : le code corrigé retient 2.32, le code re-bugué retient
2.694 — exactement la valeur publiée à tort.

## Ce qui reste à décider

Le registre `canal_clv_detail.csv` contient des lignes **gelées avec une
valeur tronquée**, et la règle du projet est de ne jamais les retoucher. Les
corriger serait une réécriture du registre public ; les laisser, c'est
conserver des mesures fausses dans l'historique publié. C'est une décision
éditoriale, pas technique — je ne l'ai pas prise. Un diagnostic préalable
utile : recompter les 71 lignes à 0 % en repassant par les partitions, pour
savoir combien sont de vrais prix figés et combien des troncatures.
