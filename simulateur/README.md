# Simulateur de matchs (21/10/2026)

Simule un match de tennis **point par point**, de façon exacte : au lieu de
jouer 5 000 matchs au hasard, il calcule la probabilité de chaque issue.

| Fichier | Rôle |
|---|---|
| `modele.py` | le moteur : jeu, tie-break, set, match ; victoire, sets, total de jeux, handicaps, tie-breaks |
| `notes.py` | force au service et au retour de chaque joueur, ajustée aux adversaires, sans regarder le futur |
| `donnees.py` | lecture des CSV Sackmann et jointure avec les cotes Pinnacle de tennis-data |
| `backtest.py` | le test : réglage sur 2023, jugement sur 2024 → janvier 2026 contre la clôture Pinnacle |
| `marches_sets.py` | le moteur contre les marchés « set 1 » (Pinnacle et books mous), 30 min avant le début |
| `profils_service.py` | profil de service et de retour de chaque joueur : % de 1re balle, aces, doubles fautes, points gagnés derrière la 1re et la 2e balle (→ `profils_service.json`) |
| `match_simule.py` | le match joué **20 000 fois en production**, point par point : feuille prévue, scores et scénario réellement tiré, rejouable par sa trace de points |
| `fiabilite.py` | note 0–100 et catégories A–D : données, désaccord Elo–simulation, stabilité et calibration antérieure |
| `ablation.py` | Elo, simulation, mélange de base et pipeline complet sur les mêmes pronostics figés, avec bootstrap par semaine |
| `evaluation_sorties.py` | log loss des sets, rang des scores, erreur des jeux et des statistiques, couverture réelle des intervalles à 80 % |
| `validation_fiabilite.py` | performances par niveau de note, IC d'exactitude et verdict contrôlé sur au moins 30 matchs par groupe |
| `roi_algo.py` | ROI comptable R1/R2 à mise fixe, cotes de clôture pré-match, IC95 et rapport JSON reproductible |
| `validation_vitrine.py` | contrôle bloquant des 20 000 simulations et rejeu de la trace vidéo avant publication |
| `stabilite_scores.py` | deux blocs indépendants de 20 000 tirages pour vérifier le score modal de la variante publiée |
| `surveillance_derive.py` | log loss, Brier et confiance sur 4, 8 et 12 semaines, globalement et par sous-groupe |
| `profils_robustes.py` | challengers contrôlés, avec validation obligatoire sur les profils de moins de 500 balles effectives |
| `matchs_similaires.py` | voisinage strictement pré-match, futur exclu, sans cote ni sélection par ROI ; contrôle descriptif de calibration |
| `styles_joueurs.py` | instantanés service–retour horodatés, challenger d'interaction et apport incrémental après contrôles Elo/surface/documentation |
| `etude_desaccords_marche.py` | étude privée appariée algorithme–marché, veto H14 non activé, recouvrement H13–H14 et audit des doublons de cotes |
| `recalibrage.py` | régression logistique, contraction hiérarchique et isotone en origine glissante ; direct et rejoué séparés |
| `dependances_points.py` | tests du point précédent, des tie-breaks, de la fatigue et de l’évolution entre sets sur les séquences ordonnées |
| `gouvernance.py` | périodes disjointes, traçabilité et une seule nouvelle promotion hebdomadaire |
| `recherche_externe.py` | croisement séparé avec les mouvements de marché et H13–H19, sans réinjection dans le modèle |
| `tests/` | invariants probabilistes, ancrage, traces vidéo, identités, surfaces, scores et sorties unifiées |
| `backtest_match_simule.py` | le test de la feuille simulée sur ATP/WTA 2024 → janvier 2026, avant l'heure (→ `rapport_match_simule.json`) |

Lancer le test : Actions → « Simulateur - test contre Pinnacle » → Run workflow.
Le résultat arrive dans `rapport_backtest.json` (et les notes des joueurs dans
`notes_joueurs.json`).

**Forme du jour** (21/10/2026) : sur 2 706 matchs réels, les matchs finissent en
2 sets bien plus souvent (63,7 %) que si chaque point était indépendant (54,7 %).
Le moteur ajoute un écart de forme par match (σ = 0,15, réglé sur juin–août,
vérifié sur septembre–octobre : 63,5 % prévus, 64,6 % réels).

**Verdict du test du 21/10/2026** : sur la victoire, le modèle statistique perd
contre Pinnacle (log loss 0,619 contre 0,592 ; paris −4,5 % à −7 %).

**Règle** : aucun pari sur ce modèle tant que le test ne montre pas qu'il
apporte quelque chose à Pinnacle. Données : archive des CSV de Jeff Sackmann
(CC BY-NC-SA 4.0, usage non commercial), arrêtée en juin 2026.

**Match simulé** (22/10/2026) : le moteur exact donne les probabilités ; la
simulation joue en plus chaque point (1re balle dans le court ? ace ? double
faute ?), au niveau de la variante indépendante affichée (Elo, simulation ou
combinaison) et avec la même forme du jour. Aucune cote n'entre dans ces trois
variantes. Sa probabilité de victoire retombe sur celle du moteur exact (test). Le
test `backtest_match_simule.py` compare la feuille prévue à la vraie, contre la
moyenne du circuit et contre deux « joueurs moyens » au même niveau. Lancer :
Actions → « Pronostic - test du modèle ».


## Validation et gouvernance (26/10/2026)

Le workflow hebdomadaire produit les rapports `rapport_evaluation_sorties.json`,
`rapport_validation_fiabilite.json`, `rapport_profils_robustes.json`,
`rapport_dependances_points.json`, `rapport_recherche_externe.json` et
`rapport_gouvernance.json`. Une métrique indisponible reste absente : elle n'est
jamais remplacée par zéro. Les scores sont rangés à partir de 1 et les
statistiques sont rattachées uniquement à la variante qui les a simulées.

Les profils candidats sont comparés au champion réellement publié. Un challenger
est choisi sur la période de découverte, puis doit confirmer chronologiquement,
améliorer la log loss d'au moins 0,001 et passer l'hystérésis de deux semaines.
La gouvernance finale limite en outre les promotions à une par semaine.

Les effets dynamiques entre points restent des candidats de recherche tant que
leur gain sur les points n'a pas aussi été validé sur le vainqueur. La recherche
de marché censure chaque cote au moment disponible et chaque signal à sa date de
signalisation. Sans volumes ni confirmation multi-bookmakers, ses résultats sont
exploratoires ; ils ne modifient jamais les probabilités indépendantes.

La vitrine quotidienne n'est publiée qu'après validation : chaque match du
catalogue doit avoir ses 20 000 tirages (par défaut), ses sorties complètes et
son scénario représentatif. La trace complète de chaque affiche est rejouée point par
point avant publication ; un seul match sans simulation bloque l'export. Le
navigateur ne recalibre pas une trace enregistrée et chaque relance rejoue ce
même scénario représentatif, jamais un tirage aléatoire différent. Une génération en
échec ou un ancien format sans scénario fait échouer le workflow au lieu de
laisser silencieusement l'ancien `algo/donnees.json` en ligne.

Pour la préversion Plus, la liste permet de rechercher une affiche, de filtrer
par circuit et d'ouvrir directement son détail et sa borne de simulation. Tous
les détails sont donc publics dans `algo/donnees.json`. Une future offre payante
nécessitera un service à accès contrôlé : masquer ces données dans le navigateur
ne constituerait pas une protection.

## Stabilité, dérive et profils pauvres (26/10/2026)

La variante publiée reçoit deux blocs de contrôle indépendants de 20 000 tirages
(`STABILITE_BLOCS=2` par défaut, `0` pour désactiver explicitement le contrôle).
Le score est **instable** si un bloc change de modal, **fragile** si le modal
reste identique mais que le top 1/top 2 est trop proche ou que sa fréquence varie
trop, et **stable** sinon. Les blocs ne remplacent jamais la simulation publiée
et ne déclenchent pas de hausse automatique du nombre de tirages.

`rapport_surveillance_derive.json` compare les fenêtres de 4, 8 et 12 semaines à
leurs périodes immédiatement précédentes. Les alertes exigent 30 matchs par
période et portent sur la dégradation conjointe de la log loss et du Brier, ou
sur l'écart entre confiance et exactitude. Les surfaces, circuits, formats et
niveaux de documentation sont isolés. Aucune alerte ne modifie le champion.

Le backtest des profils distingue moins de 100 et moins de 500 balles effectives.
L'adoption exige un gain global confirmé **et** au moins 30 matchs peu documentés,
sans dégradation de leur log loss au-delà de 0,001 ; le Brier est publié pour
chaque sous-groupe. Le contexte figé conserve aussi le poids des données propres
au joueur dans le taux de service, afin de distinguer estimation et prior.

## ROI et vérité empirique des notes (26/10/2026)

`rapport_roi_algo.json` conserve les règles R1/R2 fixées le 23/10 : une unité
sur le vainqueur annoncé, ou une unité lorsque probabilité × cote atteint 1,05.
La cote est la dernière clôture Pinnacle fiable capturée avant le début. Le
rapport indique les paris, gains nets, ROI, cote moyenne et IC95 ; aucune
conclusion n'est affichée avant 30 paris. Le marché ne sert qu'à l'évaluation.

La note de fiabilité n'est pas une probabilité de victoire. Son contrôle compare
les notes correctes/solides aux notes fragiles/prudentes, avec 30 matchs minimum
dans chaque groupe et quatre semaines appariées. Les notes sont **confirmées**
uniquement si le contraste bootstrap atteint 95 % et si la corrélation note/perte
est négative ; elles sont **contredites** sous 5 %, et **non concluantes** sinon.
Chaque niveau publie aussi l'exactitude, son IC de Wilson et l'écart à
l'exactitude attendue. Aucun verdict ne modifie automatiquement la note.

Depuis le 27/10/2026, la note intègre aussi `performance_circuit` : perte du
modèle sur les pronostics antérieurs du même circuit, diminuée de l'entropie
attendue. Ainsi, un circuit aux matchs plus équilibrés n'est pas pénalisé pour sa
seule réussite brute plus faible ; en revanche, une contre-performance supérieure
à 0,05 sur au moins 30 matchs plafonne la note à 64 et interdit `A_solide`. Les
champs `note_avant_composante_circuit` et `note_avant_plafond_circuit` conservent
la comparaison avec l'ancienne formule. Les notes déjà figées ne sont jamais
réécrites après les résultats.

## Amélioration contrôlée des sorties et des familles (27/10/2026)

`reglage_match_simule.py` ne juge plus les aces et la première balle comme un
bloc indissociable. `tau_f`, `ace_facteur` et `jeux_delta` sont appris sur
l'archive, évalués séparément sur les feuilles postérieures, puis ensemble si
plusieurs composantes passent. Une combinaison rejetée ne peut pas être activée
sous prétexte que ses composantes isolées étaient bonnes. Le réglage des jeux
modifie les deux serveurs avant le réancrage de la probabilité de victoire ;
il ne constitue donc pas une correction indépendante du scénario affiché.

`backtest_match_simule.py` publie `ablation_familles` : Elo avec et sans surface,
profils bruts, service seul, retour seul, service–retour ajusté, sans récence et
sans surface. Toutes les variantes portent sur les mêmes matchs et sont ventilées
par circuit, surface, BO3/BO5 et documentation. Les taux de styles affichés après
coup ne sont pas injectés rétroactivement : `styles_joueurs.py` reconstruit leur
interaction avant chaque match et la teste séparément après contrôles. Le format
BO5 reste une donnée nécessaire au moteur et est contrôlé par sous-groupe.

L'ajustement actif accepte un prior `N0` propre à la deuxième balle (`w2j`),
choisi sur 2023 par la log-vraisemblance des seconds services, puis évalué dans
le backtest ultérieur. L'adoption des composantes ajustées exige le gain global
et l'absence de dégradation supérieure à 0,002 sur les groupes peu documentés
d'au moins 100 matchs. Les exports de profils et les facteurs utilisent le même
prior : il ne s'agit pas d'un réglage isolé dans un rapport.

La validation des notes ajoute les coupures par circuit, surface et documentation,
les défaites du favori et une corrélation sur la perte résiduelle après prise en
compte de la difficulté annoncée. `evaluation_sorties.py` ventile également sets,
scores, jeux, statistiques et couvertures par niveau de fiabilité et documentation.
Cela ne réécrit jamais une note figée après le résultat.

L'apprentissage continu exige désormais un gain de log loss d'au moins 0,001 sur
une période de jugement nouvelle et un Brier non dégradé. Les challengers qui ne
franchissent pas ces gardes restent rejetés. Aucun de ces mécanismes n'utilise le
marché comme entrée du modèle indépendant.

## Suivi public de la fiabilité circuit et audit des profils (27/10/2026)

La version de note est identifiée par `version_fiabilite = "circuit_v1"` et sa
date d'activation. La vitrine suit séparément les seuls matchs **nouvellement
enregistrés** après cette activation et portant cette version. Recalculer la note
d'un match déjà journalisé ne le fait pas entrer dans ce suivi. Le taux affiché
reste indisponible tant qu'aucun de ces matchs n'est résolu : la note ne change
pas le favori et ne crée donc pas, à elle seule, un nouveau taux de réussite.

Le détail d'un match expose l'effectif antérieur du circuit, l'exactitude réelle
et attendue, la perte résiduelle et le plafond éventuel. Le bilan historique et
ses probabilités figées restent séparés de cette cohorte prospective.

`qualite_donnees.py` audite `profils_service.json` : nombre de profils, surfaces,
balles de service effectives après pondération, couverture à 200/500 balles et
contrôles structurels des numérateurs/dénominateurs. Ce descriptif reproductible
ne prouve ni l'exactitude externe ni la supériorité sur PythiaTennis ou un autre
fournisseur ; cette dernière exigerait les mêmes matchs et des données comparables.


## Désaccords externes et redondance H13–H14 (27/10/2026)

Lancer manuellement :

```bash
python simulateur/etude_desaccords_marche.py . --archive /tmp/sackmann
```

Le rapport est **privé et agrégé** (`rapport_etude_desaccords_marche.json`) : il
n'est ni publié dans le Lab ni commité par le workflow. Les cotes sont celles du
premier pronostic figé, jamais une clôture future présentée comme disponible à
la décision. Algorithme et marché sont jugés par log loss et Brier sur les mêmes
matchs, avec bootstrap par semaine ISO et seuils fixés sans optimisation.

Le veto H14 n'est évalué que si le pronostic existait déjà à la détection, avec
identité et côté vérifiés. Les populations conservée et écartée restent
distinctes : leurs métriques ne sont pas présentées comme un gain apparié. H13
et H14 sont rapprochés par UID et joueur sur leur période commune ; ils ne
constituent jamais deux confirmations indépendantes. H14 demeure **NON VALIDÉE**
et le veto n'est pas activé.

Le contrôle incrémental des styles apprend sur 2024 puis fige les coefficients
pour 2025–2026. Elo, surface, circuit, service–retour et documentation restent
dans les deux modèles ; seule l'interaction de styles est ajoutée au challenger.
Aucun résultat de ce rapport ne modifie les règles gelées ou le champion actif.

`Tennis_Edge_Lab/courbes_cotes.py` supprime seulement les répétitions de la même
paire horodatage–cote dans les lectures du Lab. Les horodatages différents et
les cotes conflictuelles sont conservés. Le producteur Telegram, absent de ce
checkout, n'est pas prétendu corrigé par cette modification.
