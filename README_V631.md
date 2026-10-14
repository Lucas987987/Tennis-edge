# Tennis Edge Lab V6.3.1 — cache incrémental et suivi quotidien

## Objectif

Ne pas relancer chaque jour le moteur exploratoire des 160 313 segments. Réutiliser un cache **par partition** des ancres de cote déjà lues, construit par le lecteur V5, puis ne reconstruire que les partitions dont les octets ont changé. Les calculs des 60 règles gelées reposent sur les observations postérieures au gel et les mêmes critères de la V6.3 : aucun ROI historique dans la sélection.

## Comportement

- Recherche historique exhaustive : **dimanche, 05h20 UTC**, par le workflow existant `lab_autonomous.yml`.
- Suivi prospectif : **quotidien, 04h20 UTC**, par le nouveau `lab_incremental_v631.yml`, sérialisé avec la recherche exhaustive par le même groupe de concurrence.
- Si la partition est inchangée et le parseur inchangé, elle est rechargée depuis un cache d'ancres vérifié par SHA-256 de l'entrée.
- Si une partition est ajoutée, corrigée, retirée ou si le lecteur V5 change, le cache correspondant est recalculé et les conflits sont recomposés globalement ; `set_results.json` et les circuits sont relus à chaque passage.
- Publication : **uniquement** `Tennis_Edge_Lab/live/candidate_watch_v62_prospective.json`. Ne touche pas aux chaînes `candidate_selection_v63.jsonl`, `candidate_watch_v62.jsonl`, `v62_evidence/`.
- Les évaluations statistiques restent conditionnées aux échéances préenregistrées J+30/J+60/J+90.
- La cache GitHub Actions accélère le traitement mais **n'est pas un archivage permanent** : si elle est évincée, les partitions sont reparsées depuis Git sans changer les règles gelées. L'audit publié, les preuves et les sources restent la référence ; les artifacts complets existants sont conservés 90 jours. Le stockage permanent R2 doit être validé séparément avant activation d'écritures.

## Installation depuis Codespaces/mobile

Téléverser le ZIP **à la racine** de `Tennis-edge`, puis lancer :

```bash
unzip -o Tennis_Edge_Lab_V631_Incremental.zip
python3 install_v631.py
python3 -m unittest discover -s Tennis_Edge_Lab/tests -p 'test_incremental_v631.py' -v
git diff --check
git add .github/workflows/lab_autonomous.yml .github/workflows/lab_incremental_v631.yml Tennis_Edge_Lab/incremental_v631.py Tennis_Edge_Lab/tests/test_incremental_v631.py install_v631.py README_V631.md
git commit -m "Lab V6.3.1: cache historique et suivi prospectif incrémental"
git push origin main
```

**Ne pas lancer la découverte intégrale juste pour amorcer le cache.** Lancer le workflow `Tennis Edge Lab V6.3.1 - suivi prospectif incrémental` en mode manuel : il créera le cache sur sa première exécution. Ce premier passage peut être long. Confirmer que l'étape rapporte `frozen=60`, `active=60`, `cache_rebuilt>0`, puis au deuxième passage `cache_reused>0` et `cache_rebuilt=0` en l'absence de nouvelles partitions.

## Vérification de parité (contrôle optionnel, coûteux)

Une comparaison des observations produites avec les observations du lecteur V5 historique est disponible :

```bash
python3 Tennis_Edge_Lab/incremental_v631.py audit --root . --cache /tmp/tennis-edge-incremental-v631
```

Cette commande est volontairement coûteuse : elle relit les sources dans l'implémentation historique. Une différence stoppe le contrôle au lieu de réécrire les règles.

## Limites

Le premier calcul sur un cache absent relit les partitions ; les étapes de regroupement des observations et le calcul des seuls contrôles prospectifs ne sont pas évités, car les corrections de résultat et les jointures croisées doivent rester cohérentes. Ce n'est pas une promesse de temps fixe ou de suppression totale des lectures historiques.
