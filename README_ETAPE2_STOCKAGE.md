# Stockage — étape 2 (16/10/2026)

Suite de `README_MIGRATION_R2.md`. Ce que fait cette étape :
- alléger `closing_lines.json`, la première source de croissance ;
- ne plus committer les JSON dont seul un horodatage a changé ;
- mesurer la croissance chaque jour ;
- poser, **par écrit seulement**, le plan du « nouveau dépôt propre ».

Mêmes règles qu'avant :
- **aucune réécriture d'historique, aucun `git push --force`** ;
- chaque changement est réversible en une action.

Mesure du 15/10 (24 h, nouvelles versions × taille) :

| fichier | versions | volume brut / jour |
|---|---|---|
| `closing_lines.json` | 275 × 9,5 Mo | **~2,6 Go** |
| `polymarket_markets.json` | 87 × 3,4 Mo | ~300 Mo |
| `resultats_derived.json` | 247 × 1,0 Mo | ~250 Mo |
| `kalshi_markets.json` | 87 × 1,6 Mo | ~140 Mo |
| `odds_alerts_log.jsonl` | 29 × 1,5 Mo | ~45 Mo |
| `matches_oddspapi.json`, `live_odds.json` | ~256 × 50-70 Ko | ~30 Mo |

---

## 1. `closing_lines.json` : un fichier chaud + des archives mensuelles

**Pourquoi il pèse autant.** Il est réécrit en entier à chaque capture. Pire :
chaque passage incrémente `absent_count` sur **tous** les matchs absents, même
ceux joués il y a deux mois. Chaque version diffère donc partout.

**Ce qui change.** Le fichier est découpé en deux :

- **`closing_lines.json`** (même format qu'avant) ne garde que les matchs
  **chauds** :
  - à venir, ou commencés depuis moins de **3 jours** ;
  - ou dont la CLV n'est pas encore réglée (`fetch_clv` peut encore les
    traiter, y compris ceux qu'il rouvrirait de lui-même).

  Sur le fichier réel, cela fait **206 matchs, 1,06 Mo au lieu de 9,5 Mo**.
- **`closing_lines/closing_lines_AAAA-MM.jsonl`** reçoit les autres : une
  ligne par match, écrite une fois, en ajout seul.
  - Mois = mois du début du match.
  - Les sorties sont groupées : environ **une écriture d'archive par jour**,
    pas une par capture.

**Tous les lecteurs** passent par
`closing_store.load_all()` : 19 scripts, steam_alert, canal_clv et move_audit
via `curves_common`, et le Lab. Il rend **le même dict qu'avant**, dans le même
ordre : archives + fichier chaud, le chaud l'emporte. La rétention reste à
60 jours, celle des deux anciennes purges.

Différences avec l'ancien comportement :
- Un match de plus de 60 jours est **archivé** au lieu d'être supprimé.
  `load_all(max_age_days=None)` les rend tous.
- `absent_count` cesse de grandir sur les matchs archivés, ce qui est voulu.
  Aucun lecteur ne s'en sert.

**Les écrivains** (`capture_closing`, `fetch_clv`, `purge_data`) chargent le
fichier chaud et font la bascule eux-mêmes.
- L'archive est écrite **avant** le fichier chaud : un crash entre les deux
  laisse au pire un doublon, jamais un trou.
- **Avant le workflow de migration, rien ne change** : même purge, même fichier.

Le dict reconstitué a été vérifié sur le vrai fichier : **identique**, ordre
des clés compris (1 960 matchs).

**Conflits de merge.** `merge_json_state.py` fusionne toujours les deux
versions du fichier chaud. Une fusion peut y ramener un match déjà archivé :
il repartira au prochain lot, et l'archive n'est pas doublée (une ligne
strictement identique n'est jamais réécrite). Les archives sont en
`merge=union` dans `.gitattributes`.

## 2. JSON qui changent pour rien : choix fichier par fichier

| fichier | qui le lit | choix | pourquoi |
|---|---|---|---|
| `kalshi_markets.json` | le collecteur Kalshi seul (registre des tickers) | **(a) commit seulement si le contenu utile change** | Entre deux runs, seul `updated_at` change. Il reste ~4 commits par jour (garde-fou de 6 h). |
| `polymarket_markets.json` | le collecteur Polymarket seul | **(a)**, champs ignorés : `liquidity`, `volume`, `discovered_at`, `updated_at` | Les nouveaux marchés sont toujours committés : ils servent à lire les ticks. Gain partiel ; étape suivante possible : registre en ajout seul ou dans R2. |
| `resultats_derived.json` | Lab, Pages, études | **(a)**, champs ignorés : `generated_at`, `updated` | Régénéré à chaque run des courbes live (~240 par jour), souvent sans nouveau résultat. |
| `matches_oddspapi.json` | **lu depuis raw.githubusercontent.com** par `index.html` et le worker joueurs | **inchangé** | Il doit rester dans git et frais. Il est petit (~70 Ko). |
| `live_odds.json` | passe de la capture aux courbes live | **inchangé** | ~48 Ko, ~12 Mo par jour. Le passer dans R2 ajouterait un risque de retard sur les alertes pour un gain minime. Candidat plus tard. |
| `odds_alerts_log.jsonl` | études, Lab | **inchangé** | Journal en ajout seul : les deltas git sont déjà efficaces. |

**Comment fonctionne (a).** `scripts/json_churn.py gate`, juste avant chaque
commit des collecteurs et des courbes live, compare la version git et la
nouvelle **sans les champs volatils**. Si elles sont identiques, le fichier
sort du commit et reprend sa version git.

Le garde-fou de fraîcheur : si la version git a **plus de 6 h**, on committe
quand même. Tout fichier inconnu, illisible ou vraiment modifié part dans le
commit comme avant.

> ⚠️ À vérifier à la main : le **worker Cloudflare principal** (son code
> n'est pas dans le dépôt) lit-il un de ces fichiers sur raw.githubusercontent ?
> Si oui, et s'il a besoin d'un horodatage frais, mettre `JSON_CHURN=off`.

## 3. Mesure quotidienne de la croissance

`scripts/croissance_depot.py` tourne dans « Health Check » chaque matin. Sur
les dernières 24 h, il compte les nouvelles versions de chaque fichier et les
multiplie par leur taille ; les partitions datées sont regroupées. Le résultat
va dans `croissance_depot.json` et dans le message Telegram :

> 📦 croissance 24 h : 3 210 Mo bruts (912 commits), top : closing_lines.json 2 610 Mo (275×), …

C'est un majorant (avant la compression de git), mais le classement est le
bon. Coût : ~10 s (historique récupéré sans les contenus).

---

## Ce que Lucas fait, dans l'ordre

### Étape 0 — Appliquer la livraison (Codespaces)
```bash
git switch -c feat/stockage-etape2
unzip -o r2_livraison2.zip -d /tmp/l2 && git apply --3way /tmp/l2/stockage_etape2.patch
python -m unittest discover -s tests && python -m unittest discover -s Tennis_Edge_Lab/tests
git add -A && git commit -m "Stockage étape 2 : closing_lines chaud + archives, json_churn, croissance"
git push -u origin feat/stockage-etape2
```
Il faut lire `OK` deux fois. Puis, sur github.com : Pull Request → **Merge**
(normal). Si `git apply` signale un conflit, s'arrêter et m'envoyer le message.

Juste après le merge :
- `json_churn` est **actif** : dans les logs des collecteurs, chercher
  `json_churn — 1 fichier(s) retiré(s) du commit`.
- `closing_lines.json` **ne change pas encore**.

### Étape 1 — Migrer `closing_lines` (5 min)
1. **Actions → « Closing — alléger closing_lines (migration) » → Run
   workflow**, étape = `migrer`.
2. Dans le log, chercher
   `✅ dict complet identique (1 9xx matchs, …)` puis `✅ PUSH OK`.
3. Contrôles dans la journée :
   - les runs « Capture Closing Lines » restent verts ;
   - une fois par jour, leur log affiche
     `[closing_store] N match(s) archivé(s) -> closing_lines/` ;
   - « Deploy Pages » et le Lab restent verts.
4. À tout moment : même workflow avec `verifier` (aucun commit).

### Étape 2 — Lire la croissance (le lendemain matin)
Le message Telegram du Health Check contient la ligne `📦 croissance 24 h`.
Après la migration, `closing_lines.json` doit passer de ~2,6 Go à
~0,3-0,4 Go bruts par jour.

### Variables (optionnelles, Settings → Variables)
- `JSON_CHURN` = `off` pour désactiver le filtre de l'étape 2.
- Rien d'autre à créer : pas de secret, rien dans Cloudflare.

## Retour arrière

| quoi | action | effet |
|---|---|---|
| filtre JSON | variable `JSON_CHURN` = `off` | Dès le run suivant, tout est committé comme avant. |
| closing_lines | workflow « Closing — … » étape = `annuler` | Réécrit `closing_lines.json` complet (60 jours) et retire `closing_lines/` (son contenu reste dans l'historique git). Les écrivains reprennent l'ancien comportement. |
| tout le code | **Revert** de la PR sur github.com (d'abord `annuler` si la migration a tourné) | Jamais de force-push. |

---

## 4. PLAN (à ne PAS exécuter maintenant) — « nouveau dépôt propre »

L'historique déjà accumulé (5,24 Go) ne rétrécira jamais, puisqu'on ne
réécrit rien. Le moment venu, on repart d'un dépôt neuf qui contient **l'état
actuel sans l'historique lourd**. L'ancien est gardé intact, en lecture seule.

### Prérequis (tous verts, au moins 2 semaines)
1. `R2_PRIMARY=on` stable, vérification R2 verte chaque jour.
2. `closing_lines` migré ; `clv_history` en partitions mensuelles, ancien
   fichier supprimé (`supprimer_ancien`).
3. Les données des **Releases** (`ticks-2026-08/09/10`) copiées et vérifiées
   dans R2 (`r2_partition_batch`), car les releases restent dans l'ancien
   dépôt.

   Les tags `ticks-2026-08` et `-09` sont absents du dépôt : vérifier d'abord
   que ces releases existent encore.
4. Décider pour `parts/hist_*` (~600 Mo dans HEAD) : rester dans git, ou sortir
   vers R2 comme les ticks. `courbes_r2.py` les copie déjà, et
   `restore_curves` lit R2 en premier.
5. Inventaire des liens externes :
   - le code du **worker Cloudflare principal** (URLs raw, `repository_dispatch`) ;
   - le worker joueurs (`raw.githubusercontent.com/<o>/<r>/main/…`) ;
   - `index.html` (`matches_oddspapi.json` en raw) ;
   - Pages ;
   - les liens Telegram.

### Le principe qui garde toutes les URL
1. Renommer l'**ancien** dépôt (`Tennis-edge` → `Tennis-edge-archive-2026`).
2. Créer un **nouveau** dépôt nommé `Tennis-edge`.

Les URL `raw.githubusercontent.com/Lucas987987/Tennis-edge/main/…`, Pages
(`lucas987987.github.io/Tennis-edge`) et les cibles `repository_dispatch`
pointent alors vers le nouveau dépôt **sans rien modifier** dans les workers.
La redirection automatique de GitHub vers l'ancien nom disparaît, c'est voulu.

### Déroulé (un dimanche matin, ~45 min)
1. **Geler** : désactiver le cron du worker Cloudflare, désactiver les
   workflows (Actions → chaque workflow → Disable), attendre la fin des runs.
2. **Instantané** : dans un Codespace sur l'ancien dépôt, à jour :
   ```bash
   git archive HEAD | tar -x -C /tmp/neuf
   ```
   Exclure ce que R2 détient (`parts/pm_ticks_*`, `parts/kx_ticks_*`,
   `parts/live_*`, éventuellement `parts/hist_*`). Noter le SHA d'origine.
3. **Renommer** l'ancien dépôt (Settings → General → Repository name).
4. **Créer** le nouveau `Tennis-edge`, vide, puis depuis `/tmp/neuf` :
   ```bash
   git init && git add -A && git commit -m "Import depuis Tennis-edge-archive-2026 @ <SHA>"
   git remote add origin <nouveau> && git push -u origin main
   ```
   C'est un dépôt vide : push normal, aucun force.
5. **Reconfigurer le nouveau dépôt** :
   - Secrets à recréer à la main : `RAPIDAPI_KEY`, `TELEGRAM_*`, `R2_*`,
     `ODDS_API_KEY_*`, `GH_TOKEN`… (lister ceux de l'ancien dépôt).
   - Variables : `R2_PRIMARY=on`, `JSON_CHURN`.
   - Pages : source = GitHub Actions. Environnement `github-pages`.
   - Protection de branche si elle existait.
   - Jetons fine-grained (worker Cloudflare, `GH_TOKEN`) : **ajouter le nouveau
     dépôt** à leur liste (un jeton cible un dépôt par son identifiant, pas par
     son nom).
6. **Dégeler** : réactiver les workflows et le cron du worker. Vérifier le
   premier cycle : capture, collecteurs, Pages, Telegram.
7. **Archiver** l'ancien : Settings → **Archive this repository** (lecture
   seule ; historique, releases et branches restent consultables).

### Retour arrière
Rien n'est détruit. Il suffit de :
1. renommer le nouveau dépôt de côté ;
2. **désarchiver** l'ancien et lui rendre le nom `Tennis-edge` ;
3. réactiver ses workflows et le cron du worker.

Toutes les URL reviennent à l'ancien.

### Ce que l'on perd (et assume)
- L'historique git ancien n'est plus dans le dépôt actif ; il reste dans
  l'archive.
- Les Codespaces, les numéros d'issues et de PR repartent de zéro.
- Les Releases restent dans l'archive : prérequis 3.
