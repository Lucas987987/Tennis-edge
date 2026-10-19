# Tennis Edge — garde anti-alertes après début SANS MARGE (19 octobre 2026)

Paquet compatible avec `.github/workflows/appliquer_paquet.yml` : déposer le ZIP à la racine du dépôt **main**, sans le décompresser. Le workflow appliquera automatiquement les fichiers, exécutera les tests et fusionnera la PR s'ils sont verts.

## Fichiers

- `scripts/prematch_guard.py` : une seule barrière de vérification des courbes d'alertes, 0 requête réseau.
- `scripts/build_live_curves.py` : appelle ce garde **après** avoir écrit les points bruts dans `parts/live_*`, et **avant** que `courbes_alertes.yml` lance les canaux Telegram.
- `tests/test_prematch_guard.py` : 17 tests (avec sous-tests) sur départ dépassé, reports, heures, états live/annulé, correspondance de fixtures, fraîcheur, résultats déjà présents.

## Politique de sécurité

- Heure de référence : fichier `matches_oddspapi.json` déjà collecté ; preuve de fraîcheur du snapshot : `matches_oddspapi_meta.json` (25 min max par défaut).
- **Aucune marge de 45 minutes** : l’alerte reste éligible jusqu’à l’heure officielle du début (strictement avant). À l’heure prévue ou après, elle est bloquée. Attention : les scripts Telegram conservent leurs propres seuils de publication (`canal_public` 45 min, `steam_alert` 15 min, certaines hypothèses 5 min). Ce paquet retire seulement la marge ajoutée par `prematch_guard` et ne modifie pas ces règles existantes.
- Refus si fixture absente/ambiguë, statut live ou annulé lorsqu'il est disponible, résultat déjà connu, courbe trop ancienne, point horodaté après début, horaire incohérent ou snapshot trop ancien.
- Les **fichiers plats temporaires** `book_curves_live.jsonl`, `set1_curves_live.jsonl`, `set2_curves_live.jsonl` sont nettoyés à chaque cycle. Les partitions historiques `parts/live_*` restent intactes. Elles continuent à alimenter le calcul de résultats et de CLV lors du workflow nocturne.
- Le garde ne supprime plus les alertes des 45 dernières minutes. Le filtrage des heures périmées, des matchs déjà démarrés et des données non fiables reste actif. Les autres règles de détection des hypothèses ne changent pas.

## Limites

Il n'existe **pas** dans les snapshots utilisés de statut live fiable pour toutes les rencontres, ni d'horodatage individuel de mise à jour de chaque prix. Le filtrage sur l'horaire officiel, la marge et la fraîcheur **réduit le risque**, mais ne prouve pas qu'un match n'a pas commencé avant l'heure annoncée. Un blocage garanti des matchs démarrés en avance nécessiterait un statut live fiable dans les données collectées ; le présent correctif n'ajoute aucune requête API.

## Contrôle après installation

À la prochaine exécution « Courbes live + alertes forward », lire la ligne `🛡️ PREMATCH_GUARD` dans les logs de l'étape « Courbes live + alertes forward (0 requête API) ». Si le snapshot est absent/périmé, les alertes s'arrêtent par sécurité jusqu'au retour d'une capture fraîche.
