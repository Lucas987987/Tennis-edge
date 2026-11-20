# Tennis Edge Lab V6.2 — Registre compact et validation prospective

## Périmètre

- **Match, set 1, set 2, exclusivement pré-match**.
- Les calculs existants V4/V6/V6.1, les alertes et leurs registres restent inchangés.
- La recherche exhaustive V6.1 reste disponible ; V6.2 compacte uniquement les
  **gels admis** (pas de quota hebdomadaire ou arbitraire).
- Déduplication par recouvrement exact de matchs (Jaccard >= 0,85), à périmètre
  identique marché/bookmaker/horizon/choix, avec priorité à la couverture plutôt
  qu'au ROI historique.
- Registre JSONL compact lié par SHA-256 et preuves par matchs en shards
  `.jsonl.gz`, vérifiés avant chaque utilisation. Aucun résultat rétrospectif
  ne devient une validation prospective.
- Validation hors échantillon par familles prédéfinies **match/set1/set2**,
  tests Holm à chaque échéance, contrôle des trois looks (30/60/90 jours),
  allocation d'alpha par cohortes temporelles non bornées
  (0,05 / 3 marchés / 3 échéances / [k(k+1)]).

## Installation (Codespaces, branche dédiée)

1. Dans le dépôt Tennis-edge sur Codespaces, depuis un état de travail propre,
   exécuter :

   ```bash
   git fetch origin main
   git switch -c feature/tennis-edge-lab-v6-2-compact origin/main
   ```

2. Uploader `Tennis_Edge_Lab_V6.2_Compact.zip` dans la racine du dépôt et exécuter :

   ```bash
   unzip -o Tennis_Edge_Lab_V6.2_Compact.zip -d .
   python3 install_v62.py
   python3 -m unittest discover -s Tennis_Edge_Lab/tests -v
   git diff --check
   git status --short
   ```

3. Examiner les modifications. **Ne pas** utiliser `git add .` :
   sélectionner explicitement seulement le module V6.2, ses tests,
   et `.github/workflows/lab_autonomous.yml`. Ne pas ajouter le ZIP, les
   archives transitoires ou des données de production.

4. Soumettre une Pull Request, vérifier les tests CI et procéder à la fusion
   seulement après validation humaine. Ce package ne crée aucun commit ni push.

## Mise en service progressive

- `preview_v62=false`, `publish_v62=false` : exécution actuelle inchangée.
- `preview_v62=true`, `publish_v62=false` sur `main` : analyse réelle,
  contrôle des preuves et artifact GitHub Actions **90 jours**, sans publier le
  nouveau registre.
- Après vérification des métriques, `publish_v62=true` : publication de la chaîne
  compacte V6.2, de ses preuves `.gz` et du rapport prospectif.
- Pour automatiser ensuite quotidiennement : créer la variable GitHub Actions
  de dépôt `LAB_V62_AUTOMATED=true` après validation et audit du premier gel.
  Avant cela, la V6 actuelle continue à fonctionner automatiquement.

## Limitations explicites

Les **archives exhaustives** du calcul sont sauvegardées dans un artifact GitHub
Actions de 90 jours, pas pour une rétention perpétuelle. La base source du dépôt
reste intacte ; les preuves des **gels sélectionnés** sont conservées durablement
dans le registre Git (sauf suppression manuelle ultérieure). Pour garantir une
conservation permanente de l'intégralité des archives quotidiennes, prévoir
ultérieurement un stockage objet à versions immuables (S3/R2) ou équivalent.
Ce package ne prétend pas disposer de cet espace ni de ses identifiants.

Les 26 040 gels V6.1 antérieurs n'ont pas été publiés ; ils seront reconstruits
sur la prochaine exécution à partir des archives sources et regroupés en V6.2.
La date du gel prospectif reste celle de la nouvelle exécution, jamais la date
des matchs historiques.

Aucune rentabilité ne peut être considérée validée avant des résultats
**réellement futurs**, suffisants et corrigés pour comparaisons multiples.
