# V7.3 — Base des matchs (16/10/2026)

L'onglet **Base des matchs** du Lab montre maintenant **tous les matchs
enregistrés depuis juin**, de l'ouverture à la clôture. Aucun onglet n'a été
ajouté.

## Ce qu'on y trouve

### La liste des matchs

- **Recherche** par joueur ou par tournoi.
- **Filtres cumulables** : mois, circuit, alertes (H13–H18, publique,
  mouvement), lecture (sous-coté / sur-coté), courbes, résultat.

### La fiche d'un match

En touchant un match, on ouvre sa fiche :

- **La courbe Pinnacle** des deux joueurs, avec les alertes placées dessus.
- **Une table par joueur.** Chaque book y a sa cote à l'ouverture, à 24 h,
  6 h, 1 h, 10 min et à la clôture. S'y ajoutent :
  - Pinnacle juste ;
  - le meilleur prix jouable, net de commission, surligné ;
  - le meilleur prix FR.
- **Les alertes** : type, heure, book, cote, si elle a été envoyée, sa CLV et
  son P&L.
- **Aux horizons de décision** :
  - le meilleur prix jouable et le meilleur prix FR ;
  - la CLV et le P&L ;
  - la **lecture « matchs similaires passés »** telle que l'onglet « Matchs en
    direct » l'aurait affichée à ce moment-là. Elle n'utilise que les matchs
    commencés au moins 4 h avant.

Un match connu seulement par ses alertes, sans courbe collectée, a une fiche
réduite. Son heure de début est estimée.

### L'évaluation de tous les matchs

Elle se trouve en tête de l'onglet, dans un bloc à déplier.

1. **Les lectures, vérifiées après coup.** Elles sont comparées par verdict et
   par quintile de l'excès prédit, avec la corrélation entre l'excès prédit et
   l'excès réalisé.
2. **La clôture Pinnacle est-elle juste ?** On compare la probabilité annoncée
   (sans marge, puis brute) au taux de victoire réel, par tranche, par circuit
   et par surface. On prend le favori de chaque match.
3. **La CLV se transforme-t-elle en gains ?** On compare le ROI attendu
   (= CLV sans marge) au ROI réel, avec un z. C'est fait pour tous les matchs
   et pour chaque hypothèse du suivi officiel.

La même mesure « CLV → gains » apparaît aussi dans chaque profil « Matchs
similaires passés » de l'onglet Matchs en direct.

## Fichiers

Les fichiers sont produits par `explorer_matchs.py` dans le calcul quotidien,
en une seule lecture des partitions :

- `Tennis_Edge_Lab/live/registre/registre_AAAA-MM.json.gz`, un fichier par
  mois. Un mois clos ne change plus ; un fichier n'est réécrit que si son
  contenu change.
- `Tennis_Edge_Lab/live/registre/index.json`
- `Tennis_Edge_Lab/live/lectures_profils.json`

Le code est dans `lectures_profils.py` et `registre_matchs.py`. Une panne du
registre ne bloque jamais le reste de l'Explorateur.
