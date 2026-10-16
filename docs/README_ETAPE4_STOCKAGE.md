# Stockage — étape 4 (16/10/2026)

Suite des étapes 1 à 3 (`README_MIGRATION_R2.md`, `README_ETAPE2_STOCKAGE.md`,
`docs/README_ETAPE3_STOCKAGE.md`). Règles inchangées :
- **aucune réécriture d'historique, aucun `git push --force`** ;
- **rien n'est supprimé dans R2 ni dans les Releases** ;
- chaque étape a son retour arrière.

| | quoi | gain git |
|---|---|---|
| A | `parts/hist_*` **figé** → R2 seul | **−450 Mo** dans chaque checkout complet |
| B | ticks des **Releases** → R2 (copie vérifiée) | prérequis du dépôt neuf |
| C1 | `closing_lines.json` : fenêtre chaude 3 → **2 jours** | ~−135 Mo bruts / jour |
| C2 | rapport V6.1 (42,5 Mo) → **`.json.gz` (2,7 Mo)** | −40 Mo dans HEAD et à chaque mise à jour |
| C3 | `odds_alerts_log.jsonl` → **partitions mensuelles** | ~−30 Mo bruts / jour |

---

## A. Historique des courbes (`parts/hist_*`) → R2

**Pourquoi.** ~500 Mo dans le dépôt. Les partitions des semaines et mois clos
ne changent plus jamais : `fetch_book_curves` n'écrit que dans celle de la
semaine courante.

**Comment** (`scripts/hist_r2.py`, workflow « Historique courbes → R2 (migration) ») :

**1. Qu'est-ce qu'une partition figée ?**
- Sa période (semaine `AAAA-Wnn` ou mois `AAAA-MM`) est **antérieure** à la
  période courante.
- Marge de 6 h le lundi : un run lancé dimanche soir peut encore écrire.
- La semaine en cours reste **toujours** dans git.

**2. Copie dans R2 avant tout retrait de git.**
- Clé `parts/hist/<fichier>`, manifeste `parts/hist/_manifest.json` avec
  empreintes, mêmes conventions qu'à l'étape 1.
- La copie est **re-téléchargée et comparée (SHA-256)** avant tout
  `git rm --cached`.
- La copie horaire de `courbes_r2.yml` (`parts/<fichier>`, sans empreinte)
  continue et reste une 2ᵉ copie.

**3. Les fichiers retirés de git** sont listés dans un bloc géré de
`.gitignore`. Un `git add -A` ne peut donc pas les remettre quand un lecteur
les a rapatriés.

**4. Doublons `.jsonl` + `.jsonl.gz` d'une même semaine** :
- **identiques** : seul le `.gz` part (canonique) ;
- **différents** : les deux partent.

Sur le dépôt, W37 set1/set2 sont « **inclus** » : le `.jsonl` est le début du
`.gz`. Aujourd'hui, `load_partitions` lit donc ces 827 lignes **deux fois**.
La migration garde les deux fichiers, donc **les chiffres des études ne
bougent pas**. Corriger ce double comptage est une décision séparée, à
prendre en connaissance de cause.

**5. Lecteurs.**
- `oddspapi_v5` (`iter_hist_lines`, `hist_partitions`, `load_partitions`,
  `open_curves`), `restore_curves` et les études à glob direct
  (`calibration_books`, `clv_vs_median_offline`, `pistes_common`,
  `partitioned_store`) rapatrient depuis R2 ce qui manque, **si**
  `R2_HIST_MATERIALIZE=1`.
- Cette variable et les secrets R2 sont posés dans **les 25 workflows** qui
  lisent l'historique.
- `courbes_alertes` et `steam_pipeline` (les plus fréquents) ont un **cache
  par semaine** : ~450 Mo téléchargés une fois par semaine, pas à chaque run.
- `lab_quotidien` fait un `hist_r2.py pull`.
- Les collecteurs et `capture_closing` n'en ont pas besoin et **ne
  téléchargent rien**.

**6. En Codespace**, pour une étude locale : `python scripts/hist_r2.py pull`.
Il faut les secrets R2 dans les secrets Codespaces ; sans eux, seule la
semaine courante est présente.

## B. Ticks des Releases → R2

`scripts/ticks_releases_r2.py`, workflow « Ticks Releases → R2 ».
- Source : `parts/ARCHIVE_INDEX.json`, soit 70 fichiers et 434 Mo, dans
  `ticks-2026-08`, `-09` et `-10`.
- Chaque asset est téléchargé (`gh release download`), contrôlé (gzip
  lisible), copié en `parts/ticks/<fichier>` (même disposition que les
  collecteurs), puis re-téléchargé et comparé (SHA-256).
- Si R2 a déjà une version plus complète, elle n'est **jamais écrasée**.
- Progression dans `parts/RELEASES_R2_STATE.json` (committé).
- L'étape `inventaire` liste clairement les **releases absentes**. Les tags
  `ticks-2026-08` et `ticks-2026-09` n'apparaissent pas dans le dépôt ; si
  l'inventaire le confirme, ces fichiers n'ont plus de source.

## C1. `closing_lines.json` : fenêtre chaude ramenée à 2 jours

**Pourquoi pas plus.** Sortir `absent_count` et `history` du fichier chaud ne
réduirait pas le volume committé : le fichier change de toute façon à chaque
capture, à cause des cotes des matchs à venir. Cela toucherait en revanche la
clôture par disparition et `merge_json_state`. Trop risqué pour un gain nul.

**Ce qui est fait (sûr).** La fenêtre chaude passe à **2 jours**. Mesuré sur
le fichier réel : **0,99 → 0,47 Mo**. Les matchs dont la CLV n'est pas réglée
restent chauds quel que soit leur âge. Seul cas limite : un match reporté de
plus de 2 jours repart d'une entrée neuve, l'ancienne restant dans l'archive.
Réglable par la variable d'environnement `CLOSING_HOT_DAYS`.

## C2. Rapport V6.1 compressé

- `candidate_watch_v61_prospective.json` (42,5 Mo) devient
  `candidate_watch_v61_prospective.json.gz` (2,7 Mo). L'écriture est
  déterministe et le fichier n'est réécrit que si son contenu change.
- `publish_guard` republie pour le site **le `.json` décompressé et le `.gz`**.
- `research_v61.js` lit le `.gz` (DecompressionStream) et se replie sur le
  `.json`.
- Les autres rapports ne changent pas de format.

## C3. `odds_alerts_log.jsonl` → partitions mensuelles

- Même méthode que `clv_history` (`scripts/jsonl_parts.py`,
  `scripts/alerts_store.py`) : `odds_alerts_log/odds_alerts_log_AAAA-MM.jsonl`,
  ordre identique octet pour octet, 8 Mo maximum par fichier.
- Les 6 scripts lecteurs (et ceux qui les importent), l'écrivain (`odds_movement`) et le Lab
  (`clv_source`, `compatibility_v652`) passent par le même code.
- Vérifié sur le fichier réel : 5 mois, 3 291 lignes identiques.

---

## Ce que Lucas fait, dans l'ordre

### Jour J — appliquer (Codespaces, ~10 min)
```bash
git switch -c feat/stockage-etape4
# téléverser r2_livraison4.zip à la racine du dépôt, puis :
unzip -o r2_livraison4.zip && rm r2_livraison4.zip
git rm -q Tennis_Edge_Lab/live/candidate_watch_v61_prospective.json   # remplacé par le .json.gz
python -m unittest discover -s tests && python -m unittest discover -s Tennis_Edge_Lab/tests
for f in Tennis_Edge_Lab/tests/*_ui.js; do node --test "$f"; done
git add -A && git commit -m "Stockage étape 4 : historique et Releases vers R2, alertes mensuelles, V6.1 compressé"
git push -u origin feat/stockage-etape4
```
Puis Pull Request → **Merge** (normal). C1 et C2 sont alors actifs.

### Jour J — historique (~15 min)
1. « Historique courbes → R2 (migration) », étape **`inventaire`**. Lire le
   tableau : ~54 fichiers figés, ~450 Mo, et les 2 doublons W37
   « DÉBUT du .gz ».
2. Même workflow, étape **`migrer`** (5-10 min, ~450 Mo envoyés). Le log doit
   afficher `Bilan : N partition(s) retirée(s) de git … 0 gardée(s)`, puis
   `✅ PUSH OK`.
3. Étape **`verifier_complet`** : `0 anomalie(s)`.

### J+1 — contrôler les lecteurs
- Logs « Courbes live + alertes » et « Steam Pipeline » :
  `Historique : N partition(s) reprise(s) du cache` ou `rapatriée(s)`.
- Les sorties ne doivent pas bouger : par exemple, le nombre de lignes de
  `moves_detail_hist.csv` et les compteurs du track record dans
  `pipeline_status.md`.
- Ensuite, chaque lundi, relancer `migrer`, ou créer la variable
  **`HIST_R2_AUTO=true`** (lancement automatique le lundi à 06:13 UTC).

### Jour J — Releases (3 runs de ~5 min, ou automatique)
1. « Ticks Releases → R2 », étape **`inventaire`**. Noter les
   `RELEASES ABSENTES` (probablement `ticks-2026-08` et/ou `-09`).
2. Étape **`copier`**, max = **30**, deux ou trois fois jusqu'à
   `0 restant(s)`. Ou variable **`TICKS_RELEASES_AUTO=true`** : 10 par jour.

### Jour J — alertes (5 min, puis J+3)
1. « Alertes — partitionner odds_alerts_log (migration) » → **`migrer`**.
   Le log doit afficher `✅ 3 2xx lignes … retrouvées à l'identique`.
2. 30 min plus tard, **`verifier`**. Si ❌, une capture lancée avant a encore
   écrit l'ancien fichier : relancer `migrer`.
3. **J+3**, avec `verifier` ✅ : **`supprimer_ancien`**.

## Retour arrière
| quoi | action |
|---|---|
| historique | workflow « Historique courbes → R2 », étape **`annuler`** : re-télécharge, vérifie, remet tout dans git et vide le bloc `.gitignore` |
| Releases | rien à annuler : copie seule, Releases intactes |
| alertes | « Alertes — … », étape **`annuler`** : reconstitue `odds_alerts_log.jsonl` |
| fenêtre closing | variable d'environnement `CLOSING_HOT_DAYS: '3'` dans `capture_closing.yml`, ou revert de la PR |
| rapport V6.1 | revert de la PR (le `.json` d'origine reste dans l'historique git) |

## Coût R2 (offre gratuite : 10 Go, 1 M opérations A, 10 M opérations B par mois)

**Stockage.**
- +0,45 Go d'historique et +0,43 Go de ticks des Releases.
- Avec l'existant (courbes_r2, ticks et live de l'étape 1, archives V6.4),
  on estime environ **2,5 Go** au total.
- L'historique gagne ~50-80 Mo par semaine quand `fetch_book_curves` tourne.

**Opérations.**
- Migrations, une seule fois : ~300 opérations au total.
- Lecture courante : un GET du manifeste par script lecteur, soit
  ~3-5 k opérations B par jour (~150 k par mois, 1,5 % du gratuit).
- Téléchargement complet de l'historique : une fois par semaine par
  workflow mis en cache.
- La sortie de données de R2 est gratuite.

---

## « Nouveau dépôt propre » — liste de déclenchement mise à jour

Toutes les cases, mesurables :

| # | critère |
|---|---|
| 1 | `R2_PRIMARY=on` depuis ≥ 7 jours, 7 « R2 — vérifier partitions » verts de suite |
| 2 | `git ls-files parts \| grep -cE 'pm_ticks\|kx_ticks\|live_'` = **0** |
| 3 | **Historique** : `hist_r2 verifier_complet` ✅ **et** `git ls-files parts \| grep -c hist_` ≤ 3 (seulement la semaine courante) |
| 4 | **Releases** : `ticks_releases_r2 inventaire` sans `a_copier`, chaque fichier `copie` ou `r2_plus_complet` ; releases absentes listées et acceptées par écrit |
| 5 | Ligne 📦 du Health Check < **400 Mo bruts par jour**, 3 jours de suite |
| 6 | Taille serveur (`repo_size_status.json`) : **+< 0,02 Go par jour** sur 7 jours |
| 7 | `supprimer_ancien` faits pour clv, registres de marchés et alertes ; `closing_store verify` ✅ |
| 8 | Inventaire écrit des liens externes (worker principal, worker joueurs, `index.html`, Pages) |
| 9 | Health Check sans ❌ pendant 3 jours |

Déroulé, URL et retour arrière : `README_ETAPE2_STOCKAGE.md` §4.

Pour l'historique, le dépôt neuf partira sans `parts/hist_*` figé, puisque R2
le sert déjà. Ce sera ~450 Mo de moins dans le premier commit.
