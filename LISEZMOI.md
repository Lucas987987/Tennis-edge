# Purge de l'historique — 3 workflows, à lancer dans l'ordre

Dépôt : **4,08 Go packés**. Récupérable sans perdre aucune donnée en usage :
**~2,5 Go**, soit les chemins déjà absents du répertoire de travail.

| étape | fichier | destructif ? |
|---|---|---|
| 1 | `purge_1_sauvegarde.yml` | non — fabrique et vérifie une sauvegarde |
| 2 | `purge_2_liste.yml` | non — produit `purge_chemins.txt` à relire |
| 3 | `purge_3_executer.yml` | **OUI** — réécrit tout et force-push |

## Étape 1 — sauvegarde

Deux formes, parce qu'elles échouent différemment :
- un `git bundle` de tout l'historique, en artefact (90 jours) ;
- une branche `backup-avant-purge-<date>`, qui survit au force-push de main.

Le bundle est **vérifié** : `git bundle verify`, puis re-clone réel et
comparaison du nombre de commits et du SHA de HEAD. Un bundle corrompu qu'on
croit bon serait pire que pas de sauvegarde — on prendrait le risque en se
croyant couvert.

**Téléchargez l'artefact et sortez-le de GitHub.** Une sauvegarde qui ne vit
que dans le dépôt qu'elle protège n'en est pas une.

## Étape 2 — liste

Écrit `purge_chemins.txt` à la racine, relisible dans l'interface web.
L'étape 3 lit ce fichier : ce que vous validez est ce qui sera purgé.

Un chemin n'est retenu que s'il est **déjà absent de HEAD**, vérifié deux
fois par deux moyens indépendants : la colonne « date deleted » de
filter-repo, puis un `git cat-file -e HEAD:<chemin>`. Désaccord entre les
deux -> le chemin est écarté et signalé. Testé sur des cas piégés : un
fichier encore présent malgré une date de suppression est bien écarté, un
chemin fantôme aussi.

Vous pouvez retirer des lignes du fichier (elles seront préservées).
N'en ajoutez pas : un chemin encore utilisé serait détruit.

## Étape 3 — exécution

Six gardes avant la moindre écriture :
confirmation exacte `JE CONFIRME LA PURGE` · secret `GH_PAT_WORKFLOW`
présent · branche de sauvegarde existante · `purge_chemins.txt` non vide ·
aucun chemin de la liste présent dans HEAD (elle a pu se périmer — un
fichier restauré depuis, comme `canal_public.py` aujourd'hui) · suspension
de tous les autres workflows.

La réactivation est en `if: always()` : même si la purge échoue, le pipeline
ne reste pas figé. Un workflow suspendu qu'on oublie de rallumer serait une
panne silencieuse de plus.

### Trois choses à savoir avant de lancer

**Il faut recréer le PAT.** La réécriture change le SHA de tous les commits,
y compris ceux qui touchent `.github/workflows/` — que `GITHUB_TOKEN` n'a
pas le droit de pousser. C'est ce qui a fait échouer le bump ce matin. Jeton
fine-grained sur Tennis-edge, Contents **et** Workflows en écriture, secret
`GH_PAT_WORKFLOW`. À révoquer juste après.

**Si `main` est protégée**, le force-push sera refusé. Lever la protection
le temps de l'opération, la remettre ensuite.

**La taille ne baissera pas tout de suite.** GitHub garde les objets devenus
inatteignables jusqu'à son propre ramasse-miettes, qu'un utilisateur ne peut
pas déclencher. Le dépôt peut afficher 4 Go pendant plusieurs jours. Pour
accélérer : ticket au support GitHub en demandant un `gc`. **Ne concluez pas
à un échec sur la mesure du lendemain.**

## Ce que je n'ai PAS pu tester

Mon environnement n'a pas de réseau : je n'ai pas pu installer
`git-filter-repo` ni exécuter la commande de réécriture elle-même. J'ai testé
tout ce qui l'entoure — construction et filtrage de la liste, gardes,
détection de sauvegarde — et j'ai vérifié le principe de la purge avec
`git filter-branch` sur un dépôt jouet : les chemins visés disparaissent de
l'historique, le fichier conservé reste intact.

C'est précisément pour cette raison que l'étape 1 n'est pas facultative.
