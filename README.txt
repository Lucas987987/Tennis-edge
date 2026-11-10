Tennis Edge — modification interface des matchs
1. Importer ce ZIP avec « Appliquer un paquet », puis fusionner la PR.
2. Actions > « Tennis Edge - Appliquer interface matchs » > Run workflow.
3. Attendre la publication habituelle du site.

Modifications ciblées dans algo/index.html :
- cartes + radar juste après les informations de fiabilité du duel, avant les boutons;
- tiroir des matchs terminés en haut;
- filtre LIVE fondé uniquement sur LIVE.par_uid (matchs confirmés en direct).

Le script s'arrête si le code source ne correspond plus à la version inspectée.
Il n'altère ni les calculs de simulation ni les données.
