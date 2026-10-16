# Stockage — étape 3 (16/10/2026)

Suite de `README_MIGRATION_R2.md` et `README_ETAPE2_STOCKAGE.md`. Mêmes
règles : **aucune réécriture d'historique, aucun `git push --force`**, et
chaque changement est réversible par un workflow.

## 1. Registres de marchés Polymarket / Kalshi en ajout seul

**Le problème.** Les deux collecteurs réécrivent leur registre en entier à
chaque run :
- `polymarket_markets.json` : 3,4 Mo, ~2 800 marchés ;
- `kalshi_markets.json` : 1,6 Mo, ~4 000 marchés.

Mesure 24 h : 80 versions de chacun, ~275 Mo + ~130 Mo bruts. Or un run
n'ajoute que quelques marchés. Le filtre de l'étape 2 (`json_churn`) n'y
change presque rien : presque chaque run Polymarket apporte un marché nouveau.

**Qui lit ces fichiers ?** Vérifié dans `scripts/`, `Tennis_Edge_Lab/`, les
workflows, `index.html` et `workers/` : **seuls les deux collecteurs**. Aucun
worker ne les lit sur raw.githubusercontent : le worker de capture ne lit que
`*_collector_state.json`, `capture_state.json` et `active_tournaments.json`.

**La nouvelle forme** (`scripts/market_registry.py`) :

| fichier | dans git ? | contenu |
|---|---|---|
| `registres_marches/<fournisseur>_base.jsonl` | oui, écrit **une fois** | l'instantané de migration (tous les marchés connus) |
| `registres_marches/<fournisseur>_AAAA-MM-JJ.jsonl` | oui, ajout seul | une ligne par marché **nouveau** ou dont un champ stable change (joueurs, horaire…) |
| `registres_marches/.volatil_polymarket.json` | **non** (.gitignore) | `liquidity`, `volume`, `discovered_at` des marchés vus pendant le run |

- `load()` rend **la même liste qu'avant** : mêmes marchés, même ordre de
  première apparition, la dernière version d'un marché l'emporte. Vérifié sur
  les deux fichiers réels.
- Les champs volatils ne sont plus mis à jour dans git. Aucun lecteur ne s'en
  sert.
- Un fichier par jour : chaque version committée fait quelques dizaines de Ko.
- **Avant le workflow de migration, rien ne change** : les collecteurs
  écrivent leur JSON comme avant.

## 2. `clv_history` : partition courante limitée à 8 Mo

La partition du mois courant (17 Mo, ~35 Mo en fin de mois) est réécrite à
chaque run de `fetch_clv`. Elle tourne désormais en `_2`, `_3`… dès 8 Mo.
L'ordre des lignes est conservé (test dédié). Aucune action n'est
nécessaire : l'effet est automatique au prochain run.

---

## Ce que Lucas fait, dans l'ordre

### Étape 0 — Appliquer la livraison (Codespaces)
```bash
git switch -c feat/stockage-etape3
# téléverser r2_livraison3.zip à la racine du dépôt (glisser-déposer), puis :
unzip -o r2_livraison3.zip && rm r2_livraison3.zip
git status                                   # vérifier la liste des fichiers
python -m unittest discover -s tests && python -m unittest discover -s Tennis_Edge_Lab/tests
git add -A && git commit -m "Stockage étape 3 : registres de marchés en ajout seul, clv 8 Mo"
git push -u origin feat/stockage-etape3
```
Il faut lire `OK` deux fois. Puis Pull Request → **Merge** (normal).

### Étape 1 — Migrer les registres (5 min, puis un contrôle 30 min plus tard)
1. **Actions → « Registres marchés — ajout seul (migration) »**, étape =
   `migrer`.

   Le log doit afficher :
   `✅ 2 7xx marchés de l'ancien fichier retrouvés` (polymarket),
   `✅ 3 9xx …` (kalshi), puis `✅ PUSH OK`.
2. **30 min plus tard**, quand chaque collecteur a fait un run, même workflow
   avec `verifier` :
   - ✅ partout : c'est fini ;
   - ❌ avec `ÉCARTS` : un collecteur parti avant la migration a encore écrit
     l'ancien fichier. Relancer `migrer` (il ne rattrape que ce qui manque),
     puis `verifier`.
3. Dans les logs des collecteurs, chercher
   `📒 registre : N ligne(s) ajoutée(s)` (Polymarket). Les commits ne
   contiennent plus `polymarket_markets.json` ni `kalshi_markets.json`, mais
   un petit `registres_marches/…_AAAA-MM-JJ.jsonl`.
4. **Au moins 3 jours plus tard**, avec `verifier` ✅ : lancer
   `supprimer_ancien`. Il revérifie puis retire les deux vieux JSON, qui
   restent dans l'historique git.

### Retour arrière
- Workflow « Registres marchés … », étape = `annuler`. Il réécrit les deux
  JSON depuis le registre et retire `registres_marches/` ; les collecteurs
  reprennent l'ancien format au run suivant.
- Ensuite seulement, Revert de la PR si voulu. Jamais de force-push.

---

## 3. Croissance : mesure des dernières 24 h et projection

Mesure du 15/10 20:50 UTC (`croissance_depot.py` sur origin/main, 24 h,
687 commits) : **~3,1 Go bruts**.

Méthode : versions × taille actuelle, d'où une sous-estimation pour
`closing_lines.json`, qui pesait 9,5 Mo avant 20:43.

| # | source | mesuré / jour | après tout ce qui est en place | comment |
|---|---|---|---|---|
| 1 | `parts/pm_ticks_*` | 533 Mo | **0** | R2_PRIMARY=on |
| 2 | `parts/live_match/set1/set2_*` | 743 Mo | **0** | R2_PRIMARY=on |
| 3 | `parts/kx_ticks_*` | 320 Mo | **0** | R2_PRIMARY=on |
| 4 | `clv_history.jsonl` | 333 Mo | **0** | plus écrit ; supprimer_ancien ≥ 18/10 |
| 5 | `polymarket_markets.json` | 275 Mo | **~2 Mo** | registre (cette étape) |
| 6 | `closing_lines.json` | 270 Mo (×1,05 Mo) | **~270 Mo** | déjà allégé ; reste n°1 |
| 7 | `resultats_derived.json` | 218 Mo | **~30-60 Mo** (estimé) | json_churn, actif depuis 20:39 |
| 8 | `kalshi_markets.json` | 131 Mo | **< 1 Mo** | registre (cette étape) |
| 9 | `clv_history/*` | 100 Mo | **~25 Mo** | rotation à 8 Mo (cette étape) |
| 10 | `Tennis_Edge_Lab/live/candidate_watch_v61_prospective.json` | 42 Mo (1×) | 42 Mo | à traiter |
| 11 | `odds_alerts_log.jsonl` | 42 Mo | 42 Mo | à traiter |
| 12 | `matches_oddspapi.json` / `live_odds.json` | 16 + 11 Mo | idem | volontairement inchangés (lus en raw / petits) |

**Projection : ~3,1 Go → ~450 Mo bruts par jour**, soit −85 %. Avant la
migration de `closing_lines`, la vraie base dépassait 5 Go bruts par jour. En
volume réellement stocké par git (après compression delta), les fichiers en
ajout seul ne coûtent presque rien.

### Prochaines cibles proposées (pas faites ici)
1. **`closing_lines.json`** (~270 Mo par jour) :
   - Cause : chaque capture réécrit ~1 Mo, car `absent_count` change sur
     tous les matchs chauds.
   - Piste : sortir `absent_count` et `history` des matchs commencés vers un
     fichier séparé, ou réduire la fenêtre chaude à 2 jours.
   - Gain : −40 à −60 %.
   - Pourquoi pas ici : touche la logique de clôture par disparition et
     `merge_json_state`.
2. **`candidate_watch_v61_prospective.json`** (42 Mo, réécrit chaque jour
   par le Lab) :
   - Piste : le publier compressé (`.json.gz`, comme `explorateur_*.json.gz`)
     ou en partitions.
   - Gain : ~−90 %.
   - Pourquoi pas ici : Pages et le Lab le lisent ; il faut adapter le front.
3. **`odds_alerts_log.jsonl`** (1,5 Mo × 27) : journal en ajout seul, à
   partitionner par mois comme `clv_history`.
   - Gain : ~−80 % bruts.
   - Pourquoi pas ici : ~15 lecteurs (études, Lab) à migrer.
4. **`resultats_derived.json`** : si json_churn ne suffit pas (lire la ligne
   📦), ne le régénérer que quand `resultats_oddspapi.json` ou
   `set_results.json` changent.

---

## 4. « Nouveau dépôt propre » — critères de déclenchement, tous mesurables

Le plan détaillé est dans `README_ETAPE2_STOCKAGE.md` §4. On ne le lance que
lorsque **toutes** ces cases sont cochées :

| # | critère | où le lire |
|---|---|---|
| 1 | `R2_PRIMARY=on` depuis **≥ 7 jours** sans retour en `double` | Settings → Variables (noter la date) |
| 2 | **7 runs consécutifs verts** de « R2 — vérifier partitions » en mode on | Actions |
| 3 | Plus aucune partition ticks/live dans git : `git ls-files parts \| grep -cE 'pm_ticks\|kx_ticks\|live_'` = **0** | Codespace |
| 4 | Ligne 📦 du Health Check : **< 600 Mo bruts par jour, 3 jours de suite**, sans `parts/pm_ticks`, `parts/kx_ticks` ni `parts/live_` dans le top | Telegram |
| 5 | Taille serveur stable : `repo_size_status.json`, **+< 0,02 Go par jour** sur 7 jours | `repo_size_status.json` (taille_go) |
| 6 | `clv_history.jsonl` et les anciens JSON de marchés supprimés (`supprimer_ancien` faits) ; `closing_store verify` ✅ | Actions |
| 7 | Données des Releases (`ticks-2026-08/09/10`) présentes **et vérifiées** dans R2 (`r2_partition_batch` verify), ou décision écrite de les laisser dans l'archive | rapport du workflow |
| 8 | Inventaire écrit des liens externes : worker principal (URLs raw, repository_dispatch), worker joueurs, `index.html`, Pages | ce dossier docs/ |
| 9 | Health Check sans ❌ workflow pendant **3 jours** | Telegram |

Tant qu'une case manque, la situation reste saine : la croissance est
contenue et le dépôt actuel continue de fonctionner.
