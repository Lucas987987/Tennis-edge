# Correctifs quater — 04/09/2026 au soir

## Pourquoi steam_pipeline était rouge : mon correctif de ce matin

```
🔒 STRICT : 1 livrable(s) en défaut, 1 alerte(s) de contenu -> exit 1
   ⚠️ Taille du dépôt : AUCUNE mesure réussie depuis jamais
```

`repo_size_status.json` date du 04/09 12h14 : il a été écrit par l'ANCIEN
`repo_sentinel.py`, qui ne connaissait pas encore `derniere_mesure_reussie_le`.
Mon code lisait un champ absent, concluait « jamais mesuré », et bloquait.

J'ai confondu **ancien format** et **jamais mesuré**. Un contrôle qui se
déclenche sur sa propre migration est un faux positif — exactement le défaut
symétrique de `|| true`.

Règle corrigée :
- champ absent + fichier réécrit il y a moins de 72 h -> ancien format, PASSE
- champ absent + fichier de plus de 72 h -> le producteur n'a pas tourné avec
  le nouveau code en trois jours, BLOQUE
- champ présent -> règle des 72 h sur la dernière mesure réussie, inchangée

Dès que health_check repassera (cron 07h37, ou lancement manuel maintenant),
le champ apparaîtra et le comportement normal reprendra.

## Deuxième bug de ma part, dans le correctif « ter »

`canal_public_log.jsonl` ajouté aux livrables surveillés serait resté en
« FIGÉ (fraîcheur inconnue) » **en permanence**, donc bloquant même après
restauration de son producteur : `_age_interne_h()` faisait un `json.load`,
or c'est du JSONL. C'était le premier livrable 'externe' à ce format.

Une alarme qui ne peut jamais passer au vert n'est pas une surveillance
stricte : au bout de trois jours on cesse de la lire, et on retombe sur le
mode de panne que `--strict` combat. Pour un `.jsonl` on lit désormais la
DERNIÈRE ligne — l'événement le plus récent, donc la vraie fraîcheur du flux.
Vérifié : 7,6 h sur votre fichier, cohérent avec sa dernière entrée (10h48).

## Ce fichier contient AUSSI le correctif « ter »

Contrôle d'intégrité `scripts_manquants()` inclus, avec résolution des appels
en boucle (`for s in ...; do python scripts/${s}.py`). Inutile de poser les
deux : celui-ci les contient tous.

## État après correctifs, rejoué sur votre dépôt réel

```
🔒 STRICT : 0 livrable(s) critique(s) en défaut, 1 alerte(s) de contenu -> exit 1
   ⚠️ Script manquant : scripts/canal_public.py ...
```

Un seul signal restant, et c'est le vrai. Avec `scripts/canal_public.py`
restauré : « tous les livrables critiques sont présents », code de sortie 0.

## Il reste UNE chose à faire de votre côté

`scripts/canal_public.py` est toujours absent. Le canal public ne publie
plus depuis le 04/09 10h48. Restaurez-le depuis l'historique git — je ne
peux pas le réécrire sans l'avoir vu.

## Vérifications

- 5 cas de migration testés (ancien format 6 h / 80 h / date illisible,
  nouveau format 12 h / 144 h) : seuls les trois derniers cas légitimes
  bloquent
- `_age_interne_h` relit correctement un JSONL et un objet JSON
- `--strict` rejoué sur l'état réel du dépôt : 1 alerte avant restauration,
  0 et code 0 après
- 14/14 tests
