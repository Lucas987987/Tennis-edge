# Verdicts EN DIRECT des hypothèses gelées (16/10/2026)

## La décision

Une hypothèse gelée (H13 à H18, H16-B, H14) se juge désormais **sur les alertes en direct** :

1. au moment de la détection, `h*_signal.py` écrit **une ligne complète** dans `h*_signal_log.jsonl` (match, joueur, côté, tournoi/circuit, heure de détection et de signal, début du match, book et cote d'entrée, cote au moment du signal, Pinnacle à l'ouverture / à la détection / au signal, ampleur, délai, écart, envoyé ou non et pourquoi, doublon et alerte d'origine, règle et empreinte de la règle). Ces champs ne sont **jamais modifiés** ;
2. plus tard, `scripts/suivi_direct.py` **ajoute** seulement le résultat, la clôture Pinnacle (deux côtés), la CLV Pinnacle et le P&L au prix journalisé, dans `suivi_direct/resultats.json` ;
3. il écrit `verdicts_direct.json`, lu par `validation_report.py`, le récap Telegram quotidien (`h13_recap.py`), les messages d'alerte (ligne « Suivi »), le Lab et la page Worker « Tennis Edge ».

La reconstruction (`moves_detail_hist.csv`) **ne juge plus** : elle apparaît en ligne « contrôle » et dans l'onglet Réconciliation du Lab.

## Règles de comptage

* un pari par (hypothèse, match, côté) = la **première** détection ;
* seules les détections **strictement après** la date de gel comptent ;
* un doublon entre hypothèses compte pour **chaque** hypothèse (une détection H15 déjà couverte par H13 est une détection H15, marquée « non envoyée ») ;
* résultat : `set_results.json` par uid exact, sinon index des matchs par **paire** de joueurs ± 1 jour, jamais par le seul nom d'un joueur ;
* CLV Pinnacle : clôture sans marge (méthode puissance), entrée nette de commission. Elle est calculée sur toutes les détections dont la clôture est connue, même si le résultat ne l'est pas encore ;
* pts = taux de gain − seuil de rentabilité (moyenne de 1/cote nette).

## H14 : nouveau canal, échantillon qui commence maintenant

H14 n'avait aucun canal en direct. `scripts/h14_signal.py` (canal privé) applique les constantes gelées de `validation_report.py` (mouvement Pinnacle > 5 % **à la détection**, 8 à 24 h avant le match). Il est lancé en dernier dans `courbes_alertes.yml` et ne renvoie pas un match déjà envoyé par un autre canal : ce doublon est journalisé et compté pour H14. **Son échantillon en direct commence au déploiement** ; la date de gel (02/10/2026) ne change pas, et aucune détection passée n'est reconstituée.

## Corrections faites dans les canaux

* Tous les canaux journalisent avec le même module (`scripts/journal_direct.py`, schéma 2). Avant, H13 n'enregistrait ni le côté ni les doublons, et aucun canal n'enregistrait Pinnacle à l'ouverture ni l'écart.
* **H15** acceptait une cote égale à 3,10, alors que le validateur l'exclut. La borne est désormais exclue.
* L'anti-doublon était purgé 3 jours après le signal : un match détecté plus de 3 jours avant son début pouvait être journalisé deux fois. Il est désormais purgé 2 jours après **le début du match**.
* En DRY_RUN ou sans jeton Telegram, la ligne indique « non tenté », pas un faux échec.

## Installation pas à pas (un seul paquet, depuis le téléphone)

`lab_livraison6b.zip` contient **tout** ce qui n'est pas encore sur main : la réconciliation (ex-livraison 5), les verdicts en direct, la garde et l'onglet « Matchs en direct ». Ne pas installer `lab_livraison5` ni `lab_livraison6` à part.

1. Codespaces, à la racine du dépôt, sur une **branche** : `unzip -o lab_livraison6b.zip`, puis `git status`.
2. Lancer les tests : `python -m unittest discover -s Tennis_Edge_Lab/tests`, puis `cd tests && python -m unittest discover -s .`, puis `node --test Tennis_Edge_Lab/tests/*_ui.js workers/tennis-edge-db/test_worker.mjs`.
3. Committer, pousser, ouvrir une PR et fusionner.
4. Actions → **Steam pipeline** → *Run workflow*. Cela crée `verdicts_direct.json` (garde comprise) et relance `validation_report.py`.
5. Actions → **Lab - calcul quotidien** → *Run workflow*. Cela met à jour l'Explorateur, la Réconciliation et la capture du Worker.
6. Le workflow **Courbes live + alertes** tourne seul. Dès son prochain passage, il écrit `direct_matchs.json` (onglet « Matchs en direct ») et fait tourner le canal H14.
7. **Worker Cloudflare** `tennis-edge-db` : coller `workers/tennis-edge-db/worker.js`, puis *Déployer* ; **supprimer le déclencheur cron** (voir plus bas).
8. Vérifier `https://tennis-edge-db.tennis-edge.workers.dev/` (cartes « verdicts en direct ») et l'onglet « Matchs en direct » du Lab.

### Détail Cloudflare

   * *Paramètres → Déclencheurs → Cron* : **supprimer** le déclencheur (plus d'ingestion D1).
   * *Paramètres → Variables* : `GH_OWNER` = `Lucas987987`, `GH_REPO` = `Tennis-edge` (déjà présentes ; facultatives, ce sont les valeurs par défaut).
   * Les liaisons D1 (`DB`) et R2 (`R2`) ne sont plus utilisées. On peut les laisser ou les retirer. La base D1 peut être gardée comme archive ou supprimée.
   * `archiverCourbes` est supprimé : il cherchait `parts/live_*.jsonl` alors que les partitions sont en `.jsonl.gz`, et `scripts/r2_parts.py` / `courbes_r2.py` copient déjà les partitions dans R2 depuis GitHub Actions.
   * `INGEST_TOKEN` et la route `/ingest` n'existent plus.
   * `/api/verif` donne l'âge de `verdicts_direct.json`, qui est mis en cache 60 s.

## Garde de verrouillage (approuvée le 16/10/2026)

Aucun verdict ne peut être **verrouillé** dans `verdicts_geles.json`, ni **déclaré** (page Worker, récap Telegram, Lab) tant que plus de **10 %** des détections post-gel d'une hypothèse n'ont pas de résultat, et ce quel que soit n. Seules comptent les détections **dont le match a commencé** : un match à venir ne peut pas encore avoir de résultat. Le statut affiché est alors « en attente de résultats (X % sans résultat) ».

Les verdicts en direct portent de nouveaux noms (« … (direct) »). Les verdicts déjà verrouillés sur la reconstruction restent dans le fichier, mais sortent de la famille Holm.

**Résolution des résultats** (`suivi_direct.py`), dans cet ordre :

1. `set_results.json` par uid exact du journal ;
2. sinon, par uid exact du match Pinnacle (clv_history) ;
3. sinon, par **paire exacte** de joueurs, de la veille du début jusqu'à **7 jours après** (matchs reportés, dates de règlement décalées). On garde le premier résultat à partir du jour du match. Jamais par le seul nom d'un joueur.

## API `/api/hypotheses` (compatible)

Mêmes champs qu'avant (`genere_le`, `hypotheses[].code`, `gele_le`, `cible`, `out_of_sample.n/gains/taux/seuil/ecart/ic95/roi/pnl/clv_moyen/verdict`, `replication`, `avancement`, `restant`, `reference_in_sample`). Ajouts : `n_detectees`, `n_envoyees`, `n_doublons`, `n_denouees`, `clv_pin_moyen`, `clv_pin_ic95`, `clv_n`, `controle_reconstruction` et `source`.

`clv_moyen` est désormais la **CLV Pinnacle** ; l'ancien Worker y mettait la CLV du même book.

## Onglet « Matchs en direct » (Lab)

* **Données** (lues par le navigateur sur `raw.githubusercontent.com`, rafraîchies toutes les 2 min 30, avec « mis à jour il y a X min ») :
  * `direct_matchs.json`, écrit par `scripts/direct_matchs.py` à chaque passage de *Courbes live + alertes*, quelques dizaines de Ko, réécrit seulement s'il change. Il contient les matchs de −3 h à +24 h, Pinnacle à l'ouverture et dernier prix d'avant-match, le dernier prix de chaque book, le circuit et la surface, les alertes déjà parties (H*, PUBLIC, MOUVEMENT) et les drapeaux des books ;
  * `live_odds.json` et `matches_oddspapi_meta.json`, écrits par la capture : ils donnent les cotes courantes les plus fraîches, jamais pour un match commencé.
* **Par match** : délai avant le début ; Pinnacle courant et juste (méthode puissance) ; mouvement depuis l'ouverture ; meilleur prix jouable et meilleur prix FR (prix de moins de 30 min, commission déduite) avec leur écart au prix juste ; nombre de books ; alertes ; liens vers les fiches joueurs et le face-à-face.
* **Matchs similaires passés** (jeu « Tous les matchs ») :
  * horizon le plus proche (24 h, 6 h, 1 h, 10 min), circuit, surface, cote Pinnacle ±10 %, sens et ampleur du mouvement, écart du meilleur jouable, alerte avant ;
  * critères relâchés un à un, dans l'ordre affiché, jusqu'à n ≥ 30.
  * **Verdict** : il porte sur la CLV Pinnacle **en excès** de celle des matchs de même horizon et de même cote, parce que la cote Pinnacle contient sa marge. Il est jugé au seuil α/k partagé avec l'Explorateur.
  * Seuls des champs connus avant la décision servent à comparer ; la logique est testée contre une référence Python (`direct_profils.py`).
