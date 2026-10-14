# Tennis Edge Lab V6.3.2 — affichage historique/prospectif

## Objectif

Affiche dans **Hypothèses prospectives V6.3** les statistiques de découverte
historiques `historical_context.roi_pct`, `roi_ci95`, `clv_mean_pct` et `clv_n`
qui sont **déjà présentes** dans le rapport publié. Les observations
prospectives `checkpoints[]` apparaissent sous une étiquette distincte et
restent `En attente` jusqu'à leur échéance.

La nouvelle vue mobile affiche une carte par hypothèse, au lieu d'une table
immense. Elle ne modifie **aucun calcul**, aucun gel ni collecteur.

## Trois limites de publication encore présentes

* V6 `bookmakers_sets_prospective.json` ancien (registre historique strict non alimenté) ;
* V6.1 `candidate_watch_v61_prospective.json` absent du site ;
* V6.1 archive exhaustive non hébergée sur Pages.

Ces états restent explicitement signalés dans le tableau de fraîcheur : cette
version **ne prétend pas** qu'ils sont réparés ou que les archives sont sur Pages.
Le texte précise que l'archive de contrôle peut être récupérée depuis les
artifacts du workflow complet tant qu'elle n'a pas expiré (90 jours).

## Installation (depuis la racine du dépôt GitHub Codespaces)

1. Ajouter `Tennis_Edge_Lab_V632_UI.zip` à la racine (comme les archives précédentes).
2. Exécuter dans Codespaces :

```bash
unzip -o Tennis_Edge_Lab_V632_UI.zip
python3 install_v632.py
node --check Tennis_Edge_Lab/research_v63.js
node --test Tennis_Edge_Lab/tests/test_v63_ui.js Tennis_Edge_Lab/tests/test_v632_ui.js Tennis_Edge_Lab/tests/test_freshness_ui.js
python3 -m unittest discover -s Tennis_Edge_Lab/tests -p 'test_publish_guard.py' -v
git diff --check
```

3. Si tous les tests passent, publier sur **une branche de PR**, pas directement sur `main` :

```bash
git add .github/workflows/pages.yml Tennis_Edge_Lab/research.html Tennis_Edge_Lab/research_v63.js Tennis_Edge_Lab/research_v632.css Tennis_Edge_Lab/freshness.js Tennis_Edge_Lab/tests/test_v632_ui.js install_v632.py README_V632.md
git commit -m "Lab V6.3.2: ROI et CLV historiques visibles, suivi prospectif distinct"
git push origin HEAD:refs/heads/lab-v632-roi-clv-20261014
```

Créer ensuite une PR de `lab-v632-roi-clv-20261014` vers `main`, attendre les
contrôles puis fusionner. GitHub Pages se déploiera automatiquement.

## Invariants

- Sources des valeurs historiques : rapport V6.3 officiel immuable.
- Aucune modification des manifestes V6.3, registres V6.2 ou preuves.
- Les contrôles prospectifs ne prennent jamais la valeur du contexte historique.
- CLV historique : moyenne et N disponibles ; **pas d'IC95 historique dans le
  rapport** (ne pas en inventer).
- Les mises à jour du moteur incrémental V6.3.1 ne sont pas modifiées.
