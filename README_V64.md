# Tennis Edge Lab V6.4 — classement économique ROI+ ET CLV+

Ce paquet **ne modifie aucun registre V6.3**, aucune hypothèse gelée ni aucun collecteur.

## Sélection et scores

L'inventaire exhaustif V6.1 est **reconstruit au lancement** et ses trois archives gzip sont vérifiées contre le manifeste SHA-256. La source n'est pas l'ancienne sélection V6.3 limitée à 60.

**Éligibilité obligatoire :** ROI historique strictement positif ; CLV moyen historique strictement positif ; au moins 80 matchs uniques, 20 jours distincts, 50 CLV ; données pré-match vérifiées, preuve de population complète, règle de 1 à 3 dimensions et coupes temporelles disponibles. Quasi-doublons Jaccard >=0,85 supprimés *dans un même marché* après classement. Pas de quota ATP/WTA/match/set 1/set 2.

Score (0–100, heuristique descriptive) : 40 % ROI positif normalisé à 30 %, 25 % CLV normalisé à 5 %, 15 % logarithme du volume de matchs jusqu'à 2 000, 10 % jours jusqu'à 120 et 10 % simplicité (1/nombre de critères). Le Top robustesse donne un bonus **descriptif** pour une borne basse ROI IC95 positive et deux demi-périodes ROI positives. Aucune de ces mesures ne constitue une probabilité future.

Top 10, Top 20, Top 50, Top ROI, Top CLV, Top robustesse et sélection complète paginée, avec filtres marché.

## Installation Codespaces

1. Déposez le ZIP à la racine de `Tennis-edge`.
2. Exécutez :

```sh
unzip -o Tennis_Edge_Lab_V64_Economic.zip
python3 install_v64.py
python3 -m unittest discover -s Tennis_Edge_Lab/tests -p test_v64.py -v
node --test Tennis_Edge_Lab/tests/test_v64_ui.js
node --check Tennis_Edge_Lab/research_v64.js
git diff --check
```

3. Commit/push **sur une branche séparée** puis fusion via PR vérifiée. Les fichiers déjà présents sur le dépôt principal et les collecteurs restent intacts.
4. GitHub Actions > `Tennis Edge Lab V6.4 - sélection économique ROI+ CLV+` > `Run workflow` > `mode=preview`. Laissez le traitement historique terminer et téléchargez l'artifact JSON pour vérifier nombre et Tops.
5. **Seulement si la prévisualisation convient** : relancez `mode=publish`. Le workflow refuse d'écraser un snapshot V6.4 déjà enregistré, n'ajoute que deux fichiers V6.4 et vérifie les gels V6.3 avant le push.

## Attention : données et biais

La V6.4 utilise volontairement le ROI et le CLV **historiques pour choisir et classer**. Cela introduit un biais de sélection : une forte performance passée peut être due au hasard. Il ne faut pas considérer le Top 10 comme un classement validé hors échantillon. Les échéances à J+30/60/90 sont préenregistrées comme métadonnées, mais **le suivi prospectif automatisé V6.4 n'est pas encore implémenté**. La V6.3 conserve son suivi indépendant.

Aucun compteur prévisionnel ROI/CLV n'est inventé. Si toutes les pistes sont rejetées, le job échoue explicitement au lieu de publier une liste factice.
