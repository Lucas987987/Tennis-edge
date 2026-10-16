# Lab V7.1 — Réconciliation : verdicts en direct ↔ reconstruction ↔ Worker

> **Mise à jour du 16/10/2026** : les verdicts se rendent sur les alertes **en direct** (voir `README_VERDICTS_DIRECT.md`). « Détections (suivi officiel) » = journal `h*_signal_log.jsonl` + `verdicts_direct.json` ; la reconstruction `moves_detail_hist.csv` devient un **contrôle**. L'onglet Réconciliation compare désormais direct ↔ reconstruction ↔ Worker ; les raisons « reconstruction seule » et « direct seule » remplacent « détectée non envoyée » / « envoyée hors détections ». Le reste de ce document décrit la V7.0.

## Pourquoi

Trois chiffres différents circulaient pour la même hypothèse :

| Source | Où on la voit | Ce qu'elle compte |
|---|---|---|
| **Worker D1** | page Tennis Edge (cartes « suivi officiel ») | agrégats `out_of_sample` de l'API `/api/hypotheses` (base D1) |
| **Détections (suivi officiel)** | Lab, onglet Hypothèses gelées / Explorateur | lignes de `moves_detail_hist.csv` retenues par les règles gelées de `scripts/validation_report.py`, matchs réglés après la date de gel |
| **Alertes envoyées** | Lab, Explorateur (ex-« Nos alertes ») | messages Telegram réellement partis (`h*_signal_log.jsonl`, `envoye=true`, sans doublon) |

Ce ne sont pas les mêmes paris : le canal en direct et la reconstruction a posteriori (`move_audit`) ne retiennent pas toujours le même match, le même joueur ni le même prix.

## Ce que fait le Lab

* `Tennis_Edge_Lab/reconciliation.py` (tâche quotidienne) écrit `live/reconciliation_hypotheses.json` et le jeu `live/explorateur_detections.json.gz`.
* **Worker** : chiffres recopiés **sans recalcul** depuis la capture `/api/hypotheses` (`live/worker_hypotheses_capture.json`, conservée si l'API est en panne). L'onglet prend la capture horaire de Pages si elle est plus récente. Le Worker ne publie que des agrégats : l'écart Worker ↔ GitHub se lit par hypothèse, pas ligne à ligne.
* **Suivi officiel** : mêmes règles que le validateur (`autoresearch.official_definitions`, aucune réimplémentation). À chaque calcul, n et nombre de gains sont comparés aux fonctions `*_watch` de `validation_report.py` ; une différence bloque la publication.
* **Rapprochement** : uid du match + joueur (nom normalisé), à défaut paire de joueurs + date à ±1 jour.

## Raisons des écarts

Détectée mais pas envoyée : doublon (avec l'alerte d'origine), envoi échoué, hypothèse sans canal (H14), avant la mise en service du canal, autre joueur signalé en direct, délai < 5 min, détectée après coup (absente du journal live), **inexpliqué** si une règle incluse (H16-B ⊂ H16, H18 ⊂ H16 et H17) a envoyé le match en direct.

Envoyée mais absente des détections : pas encore dans la reconstruction, absente de la reconstruction (aucun mouvement retenu), reconstruction sur l'autre joueur, hors période de gel, prix/seuil différent (direct vs reconstruction), données incomplètes, **inexpliqué** sinon.

## Où le voir

* Onglet **Réconciliation** : tableau par hypothèse (Worker / suivi officiel / envoyées / communes / inexpliqués), entonnoir, ROI – pts – CLV Pinnacle des populations (suivi officiel, envoyées, communes, détectées non envoyées, envoyées hors détections) et liste des écarts (⚠ rouge = inexpliqué).
* **Explorateur** : jeu par défaut **Détections (suivi officiel)** (référence des verdicts, mêmes n que le validateur, filtres « Alerte envoyée » et « Raison de non-envoi ») ; **Alertes envoyées** à côté. En découpant par hypothèse, chaque ligne rappelle le n de l'autre population.

« pts » côté Lab = taux de gain − seuil de rentabilité (moyenne de 1/cote). Côté Worker, le champ publié est recopié tel quel.

## Installation

`unzip -o lab_livraison5.zip` à la racine du dépôt. Tests : `python -m unittest discover -s Tennis_Edge_Lab/tests` et `node --test Tennis_Edge_Lab/tests/test_v70_reconciliation_ui.js`. Lancement manuel : `python Tennis_Edge_Lab/reconciliation.py . --worker Tennis_Edge_Lab/worker_hypotheses.json`.
