# Explorateur v2 (V6.9) — notes

## Ce qui change
- **Nouveau jeu « Tous les matchs »** (`Tennis_Edge_Lab/live/explorateur_matchs.json.gz`) :
  une ligne par match suivi depuis juin (ATP, WTA, Challenger, Grand Chelem),
  par côté et par horizon de décision (24 h, 6 h, 1 h, 10 min), seulement si
  Pinnacle cote les deux côtés à cet horizon.
  - Construit chaque jour par `Tennis_Edge_Lab/explorer_matchs.py` dans
    « Lab - calcul quotidien », après le rapatriement R2 de l'historique figé
    (`hist_r2.py pull`, `R2_HIST_MATERIALIZE=1`).
  - Trois prix d'entrée au choix : Pinnacle, meilleur book jouable (hors Pinnacle,
    cote de moins de 30 min, commission Betfair déduite), meilleur opérateur ANJ.
  - CLV Pinnacle (dé-margination puissance contre la clôture) et P&L pour chacun.
  - Clôture et mouvement horizon→clôture : affichés, jamais filtrables.
- **Filtres cumulatifs** (3 jeux) : plusieurs valeurs cochées = OU, plusieurs
  critères = ET, plages min/max pour les nombres (bornes incluses ; une ligne
  sans valeur est exclue). Puces supprimables, « Découper par » (y compris en
  5 tranches pour un critère numérique), « Comparer avec le reste », préréglages.
- **Garde-fous** inchangés : compteur de découpes k et seuil α/k, alerte n < 30,
  CLV Pinnacle principal avec IC95 groupé par jour, note rouge « ROI seul »,
  part de mois CLV+. Sur « Tous les matchs », un match compte jusqu'à 4 fois
  (un par horizon) : choisir un seul horizon pour des effectifs indépendants.
- **Préparer le gel** sérialise critères, plages et prix d'entrée ;
  `explorer_gel.py` accepte les jeux `alertes` et `matchs` et ne compte que les
  décisions postérieures au gel (dès le jour UTC suivant). Les gels V6.7
  existants restent valides (même identifiant).

## Étapes pour Lucas (Codespaces, à la racine du dépôt)
```bash
unzip -o lab_livraison4.zip
python -m unittest discover -s Tennis_Edge_Lab/tests
for f in Tennis_Edge_Lab/tests/*_ui.js; do node --test "$f"; done
git add -A && git commit -m "Lab V6.9 : Explorateur v2 (filtres cumulatifs, jeu Tous les matchs)" && git push
```
Puis, dans GitHub → Actions : lancer **« Lab - calcul quotidien »** une fois
(il reconstruit `explorateur_matchs.json.gz` avec tout l'historique R2), puis
attendre le déploiement Pages.

## Limites connues
- La collecte des courbes est en pause jusqu'au 27/10 : peu de nouveaux matchs d'ici là.
- Résultats connus pour environ 2 décisions sur 3 (set_results, sinon paire de joueurs).
- Polymarket n'est pas inclus (optionnel, jugé trop lourd pour l'instant).
