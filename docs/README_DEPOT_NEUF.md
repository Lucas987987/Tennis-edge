# Dépôt neuf — le kit (16/10/2026)

**But.** Le dépôt pèse plus de 5 Go à cause de l'historique : chaque ancienne
version de chaque fichier est gardée. Supprimer des fichiers ne rend jamais
cette place. On repart donc d'un dépôt **neuf**, qui contient l'état actuel
en un seul commit, soit environ 250 Mo une fois que R2 sert les partitions.

L'ancien dépôt est seulement **renommé**. Tout y reste : historique,
Releases, secrets. Rien n'est réécrit, rien n'est forcé.

**Tout se fait depuis le téléphone.** Le workflow s'appelle **« Dépôt neuf »**
(Actions → Dépôt neuf → Run workflow) et a une étape par lancement.

**Les secrets sont recopiés automatiquement.** Le workflow de l'ancien dépôt
les lit et les écrit dans le nouveau. Personne ne voit les valeurs, ni toi,
ni Claude, ni les journaux : seuls les noms s'affichent.

---

## 0. Une fois, à l'avance : le jeton `PAQUET_TOKEN`

Photo de profil → Settings → Developer settings → Fine-grained tokens →
`paquet` → **Edit**. Les permissions suivantes doivent être en
**Read and write** :

- Actions
- Administration
- Contents
- Pages
- Pull requests
- Secrets
- Variables
- Workflows

Repository access : *Only select repositories* → `Tennis-edge`. On ajoutera
le nouveau dépôt à l'étape 3.

## 1. Quand on est prêt : « controle »

Lecture seule. On peut le lancer autant de fois qu'on veut, dès maintenant.
Il répond **🟢 PRÊT** ou **⛔ PAS ENCORE PRÊT**, avec la liste des points
bloquants :

| point | attendu |
|---|---|
| `R2_PRIMARY` | `on` |
| « R2 — vérifier partitions » | 7 runs verts sur les 7 derniers |
| partitions `parts/` | aucune « absent_r2 » ni « different » : tout ce qui sort de git est dans R2 |
| `clv_history.jsonl` | supprimé (`supprimer_ancien` fait) |
| Releases → R2 | 0 fichier restant à copier |

Il affiche aussi :
- les **noms** des secrets et des variables qui seront copiés ;
- la taille estimée du dépôt neuf.

Calendrier prévu :
- **18/10** : CLV `supprimer_ancien` ;
- **19/10** : registres `supprimer_ancien` ;
- **vers le 23/10** : `R2_PRIMARY` passe à `on` ;
- **vers le 30/10** : 7 vérifications vertes en mode `on`, puis
  « controle » répond PRÊT.

## 2. Le jour J (environ 45 min, de préférence tôt le matin)

| # | où | quoi |
|---|---|---|
| a | `Tennis-edge` | Dépôt neuf → **geler**, confirmation `GELER`. Il désactive tous les workflows sauf « Dépôt neuf » et « Appliquer un paquet », puis attend la fin des runs en cours. |
| b | `Tennis-edge` | Settings → General → Repository name : **`Tennis-edge-archive-2026`** → Rename. |
| c | github.com → **New repository** | Nom **`Tennis-edge`**, **Public**, rien d'autre : **pas** de README, **pas** de licence, **pas** de .gitignore. |
| d | jeton `PAQUET_TOKEN` | **Edit** → Repository access : ajouter le nouveau `Tennis-edge` (garder l'archive). |
| e | `Tennis-edge-archive-2026` | Dépôt neuf → **copier**, confirmation `COPIER`, cible `Lucas987987/Tennis-edge`. |
| f | `Tennis-edge-archive-2026` | Dépôt neuf → **verifier**. Tout doit être ✅. |
| g | `Tennis-edge-archive-2026` | Dépôt neuf → **degeler**, confirmation `DEGELER`. |
| h | 15 min plus tard | Dépôt neuf → **verifier** encore une fois. On doit voir les premiers runs, dont ceux déclenchés par le worker Cloudflare (`repository_dispatch`). |

Ce que fait **copier**, dans l'ordre :
1. refuse si le nouveau dépôt n'est pas vide, ou si l'ancien n'est pas gelé ;
2. recopie les secrets, sauf `GITHUB_TOKEN` qui est automatique, et les variables ;
3. recopie le réglage « jeton automatique en écriture » ;
4. prend un instantané de l'état actuel, sans les partitions que R2 contient déjà ;
5. le pousse en **un commit** marqué `[skip ci]` : aucun workflow « au push » ne part (tests, Pages, déploiements, installateur) ;
6. met en pause, dans le nouveau dépôt, les mêmes workflows que dans l'ancien, jusqu'au dégel ;
7. active GitHub Pages.

Ce que vérifie **verifier** :
- chaque fichier de l'ancien dépôt est soit identique dans le neuf, soit
  laissé dans R2 et toujours couvert par R2 ;
- l'ancien n'a pas bougé depuis l'instantané ;
- tous les secrets et toutes les variables sont présents ;
- le jeton automatique est en écriture, et Pages est activé.

### Pourquoi les liens ne changent pas
Le nouveau dépôt porte **le même nom**. Les adresses
`raw.githubusercontent.com/Lucas987987/Tennis-edge/main/…`,
`lucas987987.github.io/Tennis-edge` et les déclenchements du worker
Cloudflare pointent donc vers lui, sans rien modifier dans les workers.

### Un seul point à surveiller : le jeton du worker Cloudflare
Le worker `tennis-edge-closing` déclenche « capture_closing » avec un jeton
GitHub qui lui est propre. Si, à l'étape h, **aucun** run
`repository_dispatch` n'apparaît : github.com → Fine-grained tokens → le
jeton du worker → **Edit** → ajouter le nouveau `Tennis-edge`.

C'est inutile si ce jeton est un jeton classique ou s'il couvre « All
repositories ».

## 3. Après

- **Garder l'archive telle quelle une à deux semaines**, pour le retour
  arrière. Ensuite : Settings → **Archive this repository** (lecture seule).
- Les Releases des ticks restent consultables dans l'archive. Leurs
  données sont aussi dans R2 (prérequis du contrôle).
- Les numéros de PR repartent de 1. Les anciens restent lisibles dans
  l'archive.

## 4. Retour arrière (rien n'est détruit)

1. Renommer le nouveau `Tennis-edge` en `Tennis-edge-neuf`.
2. Renommer `Tennis-edge-archive-2026` en **`Tennis-edge`**. Le désarchiver
   d'abord si on l'avait archivé.
3. Dans ce `Tennis-edge` : Dépôt neuf → **retour_arriere**, confirmation
   `RETOUR_ARRIERE`, cible `Lucas987987/Tennis-edge-neuf`. Il remet en pause
   les workflows du neuf et réactive ceux de l'ancien.

Toutes les adresses reviennent à l'ancien dépôt.

## 5. Ce qui est volontairement exclu

- **Pas de réécriture de l'historique, pas de push forcé.**
- **Pas de suppression de dépôt.**
- **Aucune valeur de secret affichée, nulle part.**
