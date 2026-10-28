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
| `styles_descriptifs.py` | bilans publics contre six profils service–retour, global/surface, effectifs, IC de Wilson et derniers matchs ; descriptif seulement |
| `styles_global.py` | second avis global figé, journalisé avec le champion réellement publié ; aucune probabilité active modifiée |
| `styles_valeur.py` | test hors échantillon de ces bilans comme variables candidates après Elo et service–retour ; aucune activation automatique |
| `etude_styles_seuls.py` | trois prévisions utilisant exclusivement les bilans de styles, contre une référence neutre à 50 % ; diagnostic seulement |
| `etude_matrice_styles.py` | matrice des 21 paires avec le bilan global figé, IC de Wilson et bootstrap par semaine ; aucune sélection post hoc |
| `etude_pistes.py` | ablation commune des cinq familles calendrier, tournoi, Elo dynamique, mains/H2H et matchs serrés ; recherche seulement |
| `pistes_observations.py` | socle point-in-time et orientation alphabétique ; aucun résultat du même jour n’est supposé connu |
| `variables_pre_match.py` | fatigue, absences, mains, H2H, tie-breaks, sets décisifs et balles de break contractés |
| `pression_v2.py` | challenger de résidus Elo/points ordinaires avec demi-vie 365 jours et contraction surface/circuit ; jamais actif automatiquement |
| `etude_pression_v2.py` | comparaison appariée contrôle/V1/V2 ; 2025–2026 reste un diagnostic réutilisé, pas une confirmation nouvelle |
| `evolution_statistiques.py` | trajectoires descriptives service, retour et pression sur fenêtres de 180 jours, moyennes exactes de jeux et tranches d’échange, par surface et avec effectifs |
| `charting_echanges.py` | fréquence et réussite sur 1–3, 4–6, 7–9 et 10+ frappes, au total/service/retour ; profils pré-match contractés pour la recherche |
| `etude_echanges_atp_wta.py` | apport incrémental des tranches sur ATP/WTA couverts, contre le contrôle et les variables Match Charting existantes ; diagnostic seulement |
| `conditions_tournoi.py` | conditions résiduelles estimées sur les seules éditions antérieures et contractées vers la surface |
| `elo_recherche.py` | petite grille Elo dynamique isolée du classement actif |
| `etude_circuits.py` | comparaison de deux algorithmes ATP/WTA et Challenger/ITF au meilleur algorithme partagé |
| `etude_desaccords_marche.py` | étude privée appariée algorithme–marché, veto H14 non activé, recouvrement H13–H14 et audit des doublons de cotes |
| `recalibrage.py` | régression logistique, contraction hiérarchique et isotone en origine glissante ; direct et rejoué séparés |
| `dependances_points.py` | tests du point précédent, des tie-breaks, de la fatigue et de l’évolution entre sets sur les séquences ordonnées |
| `gouvernance.py` | périodes disjointes, traçabilité et une seule nouvelle promotion hebdomadaire |
| `recap_apprentissage.py` | synthèse hebdomadaire lisible des apprentissages, décisions, performances, alertes et état du champion ; lecture seule |
| `gouvernance_candidats.py` | empreintes des challengers figés et confirmation réservée aux futurs pronostics réellement nouveaux |
| `hierarchie.py` | challenger service–retour à partage partiel et incertitude dynamique, sans séparation des circuits |
| `distribution_exacte.py` | distribution exacte des scores set par set, forme du jour et tie-breaks, sans remplacer les simulations vidéo |
| `contexte_optionnel.py` | connecteurs validés pour horodatages et données physiques réelles ; aucune imputation |
| `etude_evolutions.py` | ablation appariée des challengers hiérarchique, incertitude et petit modèle non linéaire |
| `etude_charting.py` | valeur Match Charting sur les seuls matchs couverts, avec priors strictement antérieurs |
| `recherche_externe.py` | croisement séparé avec les mouvements de marché et H13–H20, sans réinjection dans le modèle |
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

Après la gouvernance, `recap_apprentissage.py` réunit ces résultats dans
`recap_apprentissage.md` et `recap_apprentissage.json`. La synthèse indique les
effectifs d’apprentissage et de jugement, les groupes adoptés ou en attente,
l’avant/après des facteurs, les performances récentes, le recalibrage direct et
rejoué, la dérive, les promotions et l’empreinte du champion. Les populations
restent séparées et une mesure absente n’est jamais remplacée par zéro. Le
module est en lecture seule : il n’entraîne rien, ne promeut aucun candidat et
ne déduit aucun gain de ROI. Rejouer :

```bash
python simulateur/recap_apprentissage.py --racine .
```

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

## Bilans descriptifs contre les styles adverses (27/10/2026)

Le workflow quotidien exécute `styles_descriptifs.py` après les profils et avant
les pronostics. Le classement adverse utilise uniquement nos statistiques de
service et de retour disponibles **avant chaque match**, avec au moins 500 balles
effectives : grand serveur, serveur attaquant, retourneur pressant, contreur,
profil équilibré ou indéterminé. Il ne prétend pas reconnaître le lift, le jeu à
plat ou la longueur des rallyes, que ces données ne mesurent pas directement.
Le résultat est ajouté au bilan seulement après ce classement ; abandons,
matchs incomplets et résultats postérieurs à la référence sont exclus.

La fiche publique affiche victoires/matchs et effectifs, globalement et sur la
surface du match, avec un IC de Wilson à 95 % et les cinq derniers matchs du
bilan global. Moins de 10 matchs est signalé comme très faible documentation,
moins de 30 comme faible, moins de 100 comme intermédiaire. Un effectif élevé ne
prouve pas à lui seul un avantage causal : adversaires, époque et niveau peuvent
différer.

Ce bloc est fusionné par UID dans `vitrine.py`, après la création des sorties du
modèle. Il ne modifie ni probabilité, ni note, ni scénario, ni journal, ni règle
gelée. Il ne réutilise ni les catégories de matchup-tennis.fr ni une cote de
marché. L'artefact intermédiaire `styles_descriptifs.json` est régénéré et ignoré
par Git ; seule sa fusion dans `algo/donnees.json` est publiée. Sans heure
historique fiable, les résultats du même jour ne sont jamais supposés connus.

## Valeur prédictive des bilans de styles (28/10/2026)

`styles_valeur.py` transforme chaque bilan pré-match en logit contracté vers
50 % avec 20 matchs de prior. Le contrôle conserve Elo général/surface, surface,
circuit, service–retour pur et documentation. Deux challengers seulement sont
comparés : bilan global, puis bilan global + surface. Le choix est fait sur 2024,
puis figé pour la confirmation à partir de 2025 ; les matchs et l'orientation
sont identiques dans tous les modèles.

Sur 8 000 matchs (2 153 en découverte, 5 847 en confirmation), le candidat
global + surface est choisi sur découverte. Son gain de confirmation est de
0,000089 de log loss et 0,000039 de Brier, avec IC95 bootstrap par semaine de
[-0,000459 ; +0,000641] pour la log loss. L'exactitude passe de 68,00 % à
67,88 %. Le bilan global seul ne gagne pas non plus de log loss en confirmation.
Le signal est donc trop faible et trop incertain pour devenir une entrée du
champion. Aucune variable n'est activée et aucun sous-groupe n'est retenu après
plusieurs comparaisons. Rejouer :

```bash
python simulateur/styles_valeur.py /tmp/sackmann . --maximum 8000
```

### Profils seuls, sans les autres facteurs

`etude_styles_seuls.py` répond à une question distincte : les bilans contre les
styles adverses contiennent-ils de l'information **sans Elo, sans service–retour
pur, sans circuit, sans marché et sans aucune autre variable explicative** ?
Trois régressions logistiques ridge 1.0 sont ajustées sur 2024 puis figées :
bilan global seul, bilan de surface seul, ou les deux. Leur référence commune
est une probabilité neutre de 50 %. La surface sert uniquement à choisir le
bilan correspondant, jamais de covariable supplémentaire.

Sur les mêmes 8 000 matchs et le même diagnostic historique réutilisé de
2025–2026 (5 847 matchs), les résultats sont :

| Profils seuls | Log loss | Gain contre 50 % | Brier | Gain de Brier | Exactitude |
|---|---:|---:|---:|---:|---:|
| Neutre 50 % | 0,693147 | — | 0,250000 | — | non classante à 50 % |
| Bilan global | 0,676174 | +0,016973 | 0,241750 | +0,008250 | 59,16 % |
| Bilan de surface | 0,679195 | +0,013952 | 0,243156 | +0,006844 | 58,27 % |
| Global + surface | 0,676071 | +0,017076 | 0,241697 | +0,008303 | 59,07 % |

L'IC95 bootstrap par semaine du gain de log loss contre le neutre est
[+0,012143 ; +0,021878] pour le global et [+0,012248 ; +0,022100] pour la
combinaison. Le signal brut des profils est donc réel dans ce diagnostic. En
revanche, ajouter la surface au global n'améliore la log loss que de 0,000103,
avec un IC95 de [-0,000076 ; +0,000277] : le bilan global porte presque toute
l'information. Les deux bilans globaux sont
documentés pour les deux joueurs dans 67,25 % de la confirmation ; les bilans de
surface dans 63,13 %. Les autres cas restent contractés vers 50 %, sans être
retirés de la population appariée.

Ce résultat ne contredit pas le test incrémental précédent : un bilan contre un
style contient aussi la force générale du joueur et la qualité moyenne de ses
adversaires. Il peut donc bien prévoir seul tout en n'ajoutant presque rien après
les autres facteurs. La victoire de Joint ne sert ni au réglage ni à la
sélection. La période 2025–2026 n'est pas une nouvelle confirmation prospective ;
aucune variable n'est activée et le champion reste inchangé.

Le bilan global seul est néanmoins inscrit comme `styles_adverses_global_v1`
dans `candidats_algorithmes.json`. Le rapport conserve son modèle complet
(coefficients, moyennes et écarts de standardisation) pour figer exactement le
challenger. Cette inscription ne change aucune probabilité publiée : une promotion
exige toujours un apport incrémental apparié au champion sur au moins 1 000
nouveaux pronostics figés et huit semaines ISO, avec Brier non dégradé. Rejouer :

```bash
python simulateur/etude_styles_seuls.py /tmp/sackmann . --maximum 8000 --bootstrap 2000
```

### Matrice exhaustive des paires de styles

`etude_matrice_styles.py` applique le **bilan global seul figé sur 2024** aux 21
paires non orientées formées par les cinq styles réels et `indetermine`. Chaque
paire publie ses effectifs, semaines, log loss, Brier, exactitude avec IC95 de
Wilson, ainsi que les gains contre 50 % et leurs IC95 bootstrap par semaine ISO.
Aucune paire n'est masquée ou rangée selon son résultat.

Sur le diagnostic réutilisé 2025–2026, les 21 paires sont observées, avec 54 à
824 matchs et 36 à 74 semaines. Dix ont un IC95 de gain de log loss entièrement
positif. Parmi les paires de styles réels :

| Paire | n | Log loss | Brier | Exactitude [IC95 Wilson] | Gain log loss [IC95 bootstrap] |
|---|---:|---:|---:|---:|---:|
| Grand serveur × équilibré | 603 | 0,657792 | 0,233088 | 60,53 % [56,57 ; 64,35] | +0,035355 [+0,013004 ; +0,056948] |
| Serveur attaquant × contreur | 129 | 0,613308 | 0,212674 | 66,67 % [58,15 ; 74,22] | +0,079839 [+0,043619 ; +0,111566] |
| Serveur attaquant × équilibré | 362 | 0,663159 | 0,236026 | 60,22 % [55,10 ; 65,13] | +0,029988 [+0,005958 ; +0,056202] |
| Contreur × équilibré | 522 | 0,675735 | 0,241522 | 56,13 % [51,84 ; 60,33] | +0,017412 [+0,003990 ; +0,031204] |
| Équilibré × équilibré | 824 | 0,679950 | 0,243399 | 58,50 % [55,10 ; 61,81] | +0,013197 [+0,001283 ; +0,024149] |

Le signal n'est donc pas uniforme. Quatre paires ont un gain ponctuel négatif,
mais leur IC95 traverse zéro. Serveur attaquant × contreur illustre aussi le
risque de sélection : son gain était seulement +0,000624 sur la découverte 2024,
contre +0,079839 dans le diagnostic. Contreur × équilibré est positif dans les
deux périodes (+0,008205 puis +0,017412), mais la découverte est en échantillon
et la confirmation historique est réutilisée : ce n'est toujours pas une preuve
prospective indépendante.

Les 21 lignes et tous les IC figurent dans `rapport_matrice_styles.md` et le
détail des deux périodes dans `rapport_matrice_styles.json`. **Aucune paire n'est
sélectionnée ou activée** après ces comparaisons multiples. Rejouer :

```bash
python simulateur/etude_matrice_styles.py /tmp/sackmann . --maximum 8000 --bootstrap 2000
```

### Mise en place comme second avis journalisé

`styles_global.py` met en production **le suivi**, pas une nouvelle règle du
champion. `styles_descriptifs.py` calcule avant chaque match les deux taux
globaux contractés, leur écart de logits, les effectifs et la paire de styles.
`modele_styles_global.json` conserve exactement le modèle global appris sur 2024 ;
la matrice ne crée aucun bonus ou coefficient particulier pour un duel.

Après chaque génération, `pronostics_du_jour.py` fige une ligne par UID dans
`simulateur/journal_pronostics/styles_global_v1.jsonl`, déjà couvert par la
publication quotidienne du dossier `journal_pronostics`. Chaque ligne contient :

- la probabilité du champion dans la variante réellement publiée
  (`combinaison`, sinon `simulation`, sinon `stats`) ;
- le second avis `styles_global`, avec orientation alphabétique de l'apprentissage
  rétablie avant de revenir au joueur home réel ;
- les variables, la paire, les empreintes du modèle et des bilans figés.

Seuls les matchs postérieurs au gel du 28 octobre 2026 entrent dans la cohorte.
Les doublons sont ignorés, les anciens pronostics ne sont pas réécrits et les
résultats sont rattachés par `set_results.json`, sans injection manuelle. Le
suivi compare ensuite champion et second avis globalement et par paire dès 30
résultats. **Cette comparaison de deux modèles indépendants ne prouve pas à elle
seule un apport incrémental** : elle sert à mesurer les désaccords futurs avant
une éventuelle règle de combinaison séparément figée.

Le second avis et ses variables restent hors de `algo/donnees.json` et ne
modifient ni probabilité, ni note, ni simulation, ni score. Les 20 000 tirages,
le médoid et la trace vidéo sont inchangés.

## Cinq familles de variables pré-match (28/10/2026)

`etude_pistes.py` compare les cinq familles sur **16 000 matchs identiques** : 4 306 en découverte sur 2024 et 11 694 en confirmation de 2025 à juin 2026. Le contrôle contient Elo général/surface, service–retour pur, surface, circuit et documentation. L’orientation alphabétique est indépendante du résultat. Les coefficients sont appris sur 2024 puis figés ; les variantes Elo et les composantes de la combinaison sont choisies sur 2024 seulement. Le marché n’est jamais lu.

Les résultats d’une même date sont versés seulement à la date suivante et les profils service–retour attendent la fin du tournoi. **Limite importante : `tourney_date` est la date de début du tournoi.** Les jours de repos, les fenêtres de 7/14/30 jours et les enchaînements sont donc des proxys prudents, non des durées exactes entre matchs. Les conditions d’un tournoi excluent toujours l’édition courante. Les taux de H2H, mains et matchs serrés sont fortement contractés ; aucune variable n’est interprétée causalement.

| Challenger | Log loss confirmation | Gain de log loss | Gain de Brier | Exactitude | Verdict |
|---|---:|---:|---:|---:|---|
| Contrôle | 0,583017 | — | — | 68,79 % | référence |
| Elo, adaptation surface ×1,25 | 0,582366 | +0,000651 | +0,000270 | 68,86 % | positif, sous le seuil de 0,001 |
| Calendrier/fatigue/absence | 0,581495 | +0,001523 | +0,000670 | 68,72 % | IC95 du gain [-0,001096 ; +0,003836], non confirmé |
| Conditions de tournoi | 0,582516 | +0,000502 | +0,000233 | 68,84 % | IC95 [-0,000037 ; +0,001108], non confirmé |
| Gauchers/droitiers et H2H | 0,582374 | +0,000644 | +0,000104 | 68,68 % | IC95 [-0,000557 ; +0,001794], non confirmé |
| Matchs serrés/pression | 0,580839 | +0,002178 | +0,000708 | 68,53 % | gain global confirmé, exactitude non améliorée |
| Combinaison choisie sur 2024 | 0,579143 | +0,003875 | +0,001490 | 68,86 % | gain global confirmé, réserves ciblées |

Les IC sont des bootstraps par semaine ISO avec 2 000 répétitions. Pour « matchs serrés », l’IC95 du gain de log loss est [+0,000770 ; +0,003590]. Le gain est de +0,002845 en 2025 et +0,000714 en 2026. Pour la combinaison, l’IC95 est [+0,000524 ; +0,006840], avec +0,004746 en 2025 et +0,001962 en 2026. Les deux années sont donc positives, mais **2026 ne franchit pas à elle seule le seuil de 0,001 pour la famille matchs serrés**.

Les contrôles ciblés interdisent une lecture triomphale : la combinaison dégrade la log loss WTA de 0,005487 et celle des défaites du favori de 0,007076 ; la famille matchs serrés dégrade aussi la WTA, le BO5 et les défaites du favori. Le Challenger et les profils peu documentés passent les tolérances fixées, mais cela ne compense pas ces réserves. **Aucun challenger n’est activé** : la combinaison peut seulement être soumise à une gouvernance ultérieure, sans promesse de taux de réussite ou de ROI.

Sur la confirmation, les deux mains sont connues dans 54,40 % des matchs, un H2H antérieur existe dans 25,00 %, une édition antérieure du tournoi dans 45,25 %, et la durée des deux derniers matchs dans 88,11 %. Les historiques de tie-breaks, sets décisifs, adversaires proches et balles de break dépassent 92 %. Le rapport détaille la couverture de chaque source et la fréquence non nulle de chaque variable. Un zéro contracté n’est pas confondu avec une donnée manquante.

Rejouer :

```bash
python simulateur/etude_pistes.py /tmp/sackmann . --maximum 16000 --bootstrap 2000
```

Les fichiers `elo_recherche.py`, `variables_pre_match.py`, `conditions_tournoi.py`, `pistes_observations.py` et `etude_pistes.py` ne sont importés par aucune composante de production. `rapport_pistes_amelioration.json` conserve toutes les variantes Elo, coefficients de découverte, sous-groupes, contrôles de convergence et verdicts ; `champion_actif_modifie` reste `false`.

## Deux algorithmes par grand circuit : test et rejet (28/10/2026)

`etude_circuits.py` teste la proposition de créer un algorithme ATP/WTA et un algorithme Challenger/ITF. **Les historiques ne sont jamais coupés** : Elo, service–retour, calendrier, H2H et pression continuent à utiliser tous les circuits et leurs transitions. Seuls les coefficients et les variables retenues peuvent différer. Pour chaque groupe, le candidat est choisi sur 2024 parmi contrôle, Elo dynamique, familles isolées et combinaison éligible, puis figé pour 2025–2026.

Le comparateur exigeant est le **meilleur algorithme partagé choisi selon la même règle**, pas seulement l’ancien contrôle. Sur les mêmes 16 000 matchs :

| Population | Log loss partagé | Log loss deux algorithmes | Gain du local | Verdict |
|---|---:|---:|---:|---|
| ATP/WTA, 1 649 confirmations | 0,590472 | 0,594819 | **-0,004347** | dégradation |
| Challenger/ITF, 10 045 confirmations | 0,577283 | 0,577947 | **-0,000664** | dégradation |
| Ensemble, 11 694 confirmations | 0,579143 | 0,580326 | **-0,001183** | dégradation |

Sur l’ensemble, le Brier passe de 0,198568 à 0,199049. L’exactitude monte légèrement de 68,86 % à 68,97 %, mais ce faible écart ne compense pas la dégradation conjointe de la log loss et du Brier. L’IC95 du gain global de log loss est [-0,002582 ; +0,000215].

La séparation des seuls coefficients de contrôle ne suffit pas non plus : gain de -0,001162 sur ATP/WTA et +0,000352 sur Challenger/ITF, sous le seuil de 0,001. Contre l’algorithme partagé, le local ATP/WTA dégrade les deux années et surtout la WTA (-0,008611). Le local Challenger/ITF gagne +0,000132 en 2025 mais perd -0,002408 en 2026 : le résultat n’est pas reproduit.

**Verdict : ne pas créer deux algorithmes actifs.** Le modèle partagé avec indicateurs de circuit et historiques inter-circuits reste préférable. Les ventilations par circuit restent utiles pour la surveillance et la gouvernance. Aucun challenger n’est activé et aucun gain de ROI n’est déduit de cette étude.

Rejouer :

```bash
python simulateur/etude_circuits.py /tmp/sackmann . --maximum 16000 --bootstrap 2000
```

`rapport_algorithmes_circuits.json` conserve les candidats de découverte, les trois comparaisons — séparation seule, algorithme local contre contrôle partagé et contre meilleur partagé — ainsi que les ventilations annuelles, circuits, surfaces, documentation et défaites du favori.

## Évolutions algorithmiques figées (28/10/2026)

Le manifeste `candidats_algorithmes.json` fige les paramètres et leurs empreintes. La période 2025–2026, déjà utilisée par plusieurs évaluations, est désormais explicitement un **diagnostic réutilisé**, pas une confirmation vierge. Une promotion éventuelle exige au moins 1 000 nouveaux pronostics figés après le 28 octobre 2026, sur huit semaines ISO, appariés au champion et résolus ensuite. Toute modification d’un candidat impose une nouvelle version et remet cette confirmation à zéro.

Sur les mêmes 16 000 matchs, le contrôle conserve une log loss de 0,583017 sur les 11 694 matchs de diagnostic. Les gains sont positifs quand le challenger améliore le contrôle :

| Challenger | Gain de log loss | Gain de Brier | IC95 du gain de log loss | Verdict |
|---|---:|---:|---:|---|
| Partage hiérarchique service–retour | -0,001723 | -0,000565 | [-0,002461 ; -0,000936] | dégradation, rejeté |
| Incertitude dynamique | +0,000017 | +0,000020 | [-0,000080 ; +0,000115] | effet négligeable |
| Hiérarchie + incertitude | -0,001891 | -0,000663 | [-0,002703 ; -0,001117] | dégradation, rejetée |
| Petits arbres résiduels | +0,000714 | +0,000218 | [+0,000206 ; +0,001173] | signal robuste mais sous le seuil de 0,001 |

La hiérarchie dégrade notamment les profils de moins de 500 balles et de moins de dix matchs Elo. Le challenger non linéaire passe les contrôles ciblés, mais son gain absolu reste insuffisant. **Aucun n’est activé.** Ces résultats ne démontrent ni une amélioration future du taux de réussite ni une amélioration du ROI.

`distribution_exacte.py` complète le moteur existant par la distribution exacte des scores complets, avec forme du jour et balles de break spécifiques. Douze configurations BO3/BO5 ont été comparées au moteur de victoire : écart maximal de 2,23×10⁻¹⁶ et masses normalisées. Les 20 000 simulations restent utilisées pour la vidéo, les statistiques, le tirage rejouable et le médoid. Cette équivalence mathématique n’est pas présentée comme une amélioration prédictive.

Match Charting est évalué uniquement quand les deux joueurs ont des relevés antérieurs : 5 726 matchs sur 16 000 (35,79 %). Sur les 3 565 matchs couverts du diagnostic, le gain est de +0,000488 de log loss et +0,000242 de Brier, mais l’IC95 de log loss [-0,000782 ; +0,001772] franchit zéro. Le circuit Challenger et le gazon se dégradent ; 2026 est quasiment neutre. La couverture est de 93,06 % ATP, 88,48 % WTA, 28,52 % Challenger et 19,18 % ITF : aucune généralisation automatique aux matchs non couverts et aucune activation.

Rejouer les études et la validation technique :

```bash
python simulateur/etude_evolutions.py /tmp/sackmann . --maximum 16000 --bootstrap 2000
python simulateur/etude_charting.py /tmp/sackmann /tmp/mcp . --maximum 16000 --bootstrap 2000
python simulateur/validation_distribution_exacte.py . --simulations 20000
```

`contexte_optionnel.py` accepte des horodatages ISO avec fuseau et des mesures physiques datées. Les doublons, dates incohérentes, valeurs négatives et observations futures sont refusés ou exclus. En l’absence de source réelle, rien n’est interpolé : `tourney_date` reste un proxy explicite. Aucune mesure physique n’entre dans le modèle actif.

Aucun secret, identifiant privé ou contenu R2 privé n’a été demandé ou consulté. Le marché ne devient pas une entrée du modèle indépendant ; les recherches marché/H13–H20 restent séparées ou servent à l’évaluation externe.

## Pression V2 et trajectoires des joueurs (28/10/2026)

`pression_v2.py` remplace les bilans bruts cumulés par des résidus : résultat moins probabilité Elo pré-match pour les tie-breaks, sets décisifs et adversaires proches ; performance sur balle de break moins niveau sur les points ordinaires pour le service et le retour. La demi-vie est de 365 jours. Les mesures de surface et de circuit sont contractées vers le résidu global, avec les mêmes priors figés que la V1.

Sur 4 306 matchs de découverte en 2024, la V2 gagne +0,001167 de log loss contre le contrôle, mais perd -0,001698 contre la V1. Sur les 11 694 matchs du diagnostic historique réutilisé 2025–2026, elle gagne seulement +0,000448 contre le contrôle, avec un IC95 [-0,000453 ; +0,001348], et perd -0,001730 contre la V1. Son exactitude est de 68,53 %, identique à la V1 et inférieure au contrôle (68,79 %). **La V2 n’est donc ni confirmée ni activée.** Ce diagnostic ne constitue pas une confirmation prospective et ne prouve aucun gain de vainqueurs ou de ROI.

`evolution_statistiques.py` produit un rapport descriptif indépendant. Il compare les 180 derniers jours aux 180 jours précédents, globalement et par surface, puis fournit une trajectoire par fenêtres glissantes. Les statistiques comprennent première balle, aces, points gagnés derrière les deux services, doubles fautes, retours, balles de break, tie-breaks et sets décisifs. Chaque taux conserve son propre dénominateur ; une comparaison insuffisamment documentée ne produit aucune variation chiffrée. Ces taux bruts ne sont pas ajustés à la force adverse et ne deviennent pas automatiquement des entrées du modèle.

Rejouer :

```bash
python simulateur/etude_pression_v2.py /tmp/sackmann . --maximum 16000 --bootstrap 2000
python simulateur/evolution_statistiques.py /tmp/sackmann . --maximum-joueurs 20
python simulateur/evolution_statistiques.py /tmp/sackmann . --joueurs "Harriet Dart" "Janice Tjen"
```

## Tranches d’échange et jeux moyens par match (28/10/2026)

`charting_echanges.py` exploite les tableaux `Rally` du Match Charting Project. Pour chaque joueur, il conserve les tranches **1–3, 4–6, 7–9 et 10+ frappes**, avec le nombre de points, leur fréquence et le taux de points gagnés. Les relevés sont disponibles au total, au service et au retour. La catégorie 10+ étant ouverte, aucune moyenne exacte de frappes n’est déduite de ce tableau agrégé. Les profils de recherche utilisent une demi-vie de 365 jours, des relevés strictement antérieurs et une contraction de surface vers le profil global ; ils restent extérieurs au champion.

Le rapport descriptif compare les 180 derniers jours aux 180 jours précédents, globalement et par surface. Une variation de réussite exige au moins 50 points dans chaque période pour la tranche concernée ; une variation de fréquence exige au moins 200 points au total dans chaque période. Les effectifs restent visibles et l’absence de relevé n’est jamais imputée. La couverture Match Charting n’étant pas aléatoire, ces résultats ne sont pas généralisés aux matchs non couverts.

`evolution_statistiques.py` calcule aussi, à partir des scores, les moyennes exactes de **jeux totaux, gagnés et perdus par match**, avec les effectifs et les mêmes comparaisons temporelles et par surface. Par exemple, un score de 7–6, 6–4 représente 23 jeux au total, 13 gagnés et 10 perdus pour le vainqueur.

Le test prédictif est limité aux matchs ATP/WTA pour lesquels les deux joueurs ont des relevés antérieurs. La couverture est de **90,83 %** : 2 653 matchs couverts sur 2 921. Sur 2024, les coefficients sont appris puis figés ; le diagnostic 2025–2026 porte sur 1 501 matchs couverts et a déjà été réutilisé par la recherche. Il ne constitue donc pas une confirmation prospective.

| Modèle apparié | Log loss | Brier | Exactitude |
|---|---:|---:|---:|
| Contrôle | 0,594146 | 0,205471 | 66,56 % |
| Match Charting existant | 0,593152 | 0,204951 | 67,09 % |
| Tranches seules | 0,596695 | 0,206524 | 65,89 % |
| Match Charting existant + tranches | 0,595637 | 0,206026 | 66,09 % |

Les tranches seules perdent **−0,002549** de log loss contre le contrôle ; leur ajout au Match Charting existant perd **−0,002486**. L’IC95 du gain combiné contre l’existant est **[−0,006647 ; +0,001550]**. Le résultat est donc non confirmant : les tranches restent utiles pour décrire les joueurs, mais **ne modifient pas les pronostics**. Le challenger reste en diagnostic avec `activation: false`, sans promesse d’amélioration des vainqueurs ou du ROI.

Rejouer l’étude et les rapports descriptifs :

```bash
python simulateur/etude_echanges_atp_wta.py /tmp/sackmann /tmp/mcp . --maximum 16000 --bootstrap 2000
python simulateur/evolution_statistiques.py /tmp/sackmann . --charting /tmp/mcp --maximum-joueurs 20
python simulateur/evolution_statistiques.py /tmp/sackmann . --charting /tmp/mcp --joueurs "Harriet Dart" "Janice Tjen"
```

Le workflow `evolutions_algorithmes.yml` exécute l’étude ATP/WTA et joint `/tmp/mcp` au rapport d’évolution. Il publie `rapport_echanges_atp_wta.json` et `evolution_statistiques_joueurs.json` comme artefacts de diagnostic, sans activation automatique.
