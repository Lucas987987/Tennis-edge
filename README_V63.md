# Tennis Edge Lab V6.3

## Inventaire et registre actif

L'audit V6.1 conserve l'inventaire exploratoire exhaustif (17 023 pistes sur
l'instantané de référence), avec ses pages JSONL et ses archives compressées
bookmakers/match/set 1/set 2. Cet inventaire n'est pas réduit au registre de
suivi prospectif.

V6.3 limite à 60 le nombre d'hypothèses actives simultanément : 20 par marché
par défaut. Les places non pourvues sont redistribuées de façon équilibrée et
la redistribution est inscrite dans le manifeste append-only. Les sélections
éliminent les populations redondantes et favorisent la diversité des
bookmakers, horizons, favoris/outsiders et familles de critères.

Le score déterministe utilise uniquement la couverture des données, l'effectif,
les jours distincts, les variables disponibles, la simplicité des règles et
une prime de diversité. ROI historique, victoires, p-values, résultats
prospectifs et CLV comme mesure de rentabilité sont explicitement exclus.
Chaque sélection conserve ses critères, ses sources et ses empreintes avant
les observations futures.

Les gels restent immuables et append-only. Les échéances 30/60/90 jours sont
conservées; après la troisième échéance, une hypothèse est archivée sans
réécriture et sa place peut être réattribuée.

## Statistiques prospectives

Les tests de Holm sont limités aux familles préenregistrées par marché,
famille de critères, cohorte de gel et échéance. Six familles fixes, trois
marchés, trois échéances et les cohortes successives consomment ensemble un
budget alpha maximal de 0,05 via `1/[k(k+1)]`. L'inventaire exploratoire et la
procédure de sélection historique restent descriptifs; seules les observations
strictement postérieures au gel alimentent l'évaluation prospective.

## Sauvegarde et publication

Les audits planifiés créent automatiquement un artifact complet, conservé
90 jours. Sur `workflow_dispatch`, `preview_v63=true` déclenche le même cycle
sans publication durable. L'artifact contient les registres, manifestes,
empreintes, preuves sélectionnées, rapports et archives exhaustives. Le
workflow télécharge ensuite l'artifact dans un dossier temporaire isolé et
vérifie l'empreinte de l'artifact, chaque fichier, les chaînes des registres,
les preuves gzip, les comptes des archives et les pages/manifeste avant de
continuer.

La publication durable n'est possible qu'avec `publish_v63=true`; elle ne
publie que le registre compact, le manifeste append-only, les preuves des
hypothèses retenues et leur rapport prospectif dérivé pour le site. Un échec
de sauvegarde ou de restauration interrompt le workflow avant toute
publication.

H13–H18, les trois gels V4, les workers et les autres collecteurs ne sont pas
modifiés. Aucune donnée live n'est ajoutée.

## Vérifications locales

```bash
python3 -m unittest discover -s Tennis_Edge_Lab/tests -v
node --test Tennis_Edge_Lab/tests/*.js
git diff --check
```
