# Correctifs ter — 04/09/2026

## Ce que je NE peux pas faire

`scripts/canal_public.py` doit être restauré depuis votre historique git.
Je n'ai jamais vu son code : le réécrire produirait un script qui ressemble
au bon sans en être un — paliers, juste prix, anti-doublon, formulation
neutre exigée par le cadrage du canal. Sur un canal Telegram qui a des
abonnés, ce n'est pas un risque acceptable.

  Onglet Code -> un commit d'avant aujourd'hui -> scripts/canal_public.py
  -> « Copy raw file » -> recréer le fichier.

Envoyez-le moi ensuite, je vérifie qu'il est complet avant que vous le posiez.

## Ce que je corrige : ce qui a laissé la panne invisible

### `scripts_manquants()` — contrôle d'intégrité, bloquant sous --strict

Vérifie que tout `scripts/X.py` cité par un workflow existe. Sur votre dépôt,
il retourne aujourd'hui exactement `['canal_public.py']`.

Pourquoi ceci bloque `--strict` alors que l'alerte Polymarket en a été
retirée ce matin : ce n'est pas le résultat d'exécution d'un autre workflow,
c'est un défaut STRUCTUREL du dépôt, vérifiable sans rien lancer et réparable
par la personne qui lit le rapport.

**Angle mort corrigé dans la foulée.** Ma première version cherchait
`scripts/X.py` par expression régulière. Or `polymarket_studies.yml` lance
ses quatre études par `for s in a b c d; do python scripts/${s}.py; done` :
la regex n'y voit que `scripts/${s}.py`. Le contrôle aurait été aveugle
exactement là où le dépôt utilise une indirection. Les boucles sont
maintenant résolues, et un test le vérifie (14/14).

### `canal_public_log.jsonl` entre dans les livrables surveillés

Il n'était surveillé par RIEN, alors que c'est la seule trace de ce que
reçoivent les abonnés et la source du track record aligné sur la publication
(`paper_journal_canal.py`). Classé 'externe' : jugé sur présence, taille et
fraîcheur < 24 h, comme `resultats_derived.json`. Un producteur mort se voit
désormais en une journée au lieu de jamais.

## Ce que je ne touche pas, volontairement

**Les 23 scripts orphelins.** La moitié sont des études exploratoires
légitimes (`cascade_study`, `segments_study`, `shadow_sizing_study`...) :
supprimer du code de recherche que vous êtes seul à pouvoir juger n'est pas
une correction, c'est une décision. Un `scripts/etudes/` séparé serait plus
propre, mais c'est 23 déplacements de fichiers depuis mobile pour un gain
d'hygiène — à faire quand vous serez devant un clavier, pas maintenant.

**L'historique git (3,48 Go le 29/08, alarme à 4,0).** La sentinelle vient de
recouvrer la vue ; sa première mesure tombe demain matin. Si elle dépasse le
seuil, la seule issue est un `git filter-repo`, opération à froid impossible
depuis mobile. À préparer avant d'y être contraint, pas à improviser.

## Vérifications

- détecteur testé sur le dépôt réel : `['canal_public.py']`, rien d'autre
- testé sur un dépôt jouet : trouve l'absent direct ET l'absent en boucle,
  ignore les scripts présents, ignore les boucles sans `scripts/$var.py`
- `--strict` bloque quand le script manque, se tait dès qu'il est restauré
- 14/14 tests ; le nouveau échoue si l'on revient à la version naïve
