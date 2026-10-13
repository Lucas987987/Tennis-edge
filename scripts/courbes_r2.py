#!/usr/bin/env python3
"""courbes_r2.py — envoie les partitions de courbes dans le compartiment R2.

    python scripts/courbes_r2.py            # envoie ce qui manque ou a changé
    python scripts/courbes_r2.py --dry      # liste sans rien envoyer

POURQUOI CE SCRIPT
------------------
Le circuit « courbes_r2 » du worker Cloudflare n'écrit plus rien depuis le
05/10. Il cherche les partitions sous leur ancien nom, `parts/live_*.jsonl`,
alors que `curves_parts.py` les écrit compressées en `.jsonl.gz` depuis le
03/10 à 16:01 UTC (pour rester sous la limite de 100 Mo par fichier de
GitHub). Mesuré dans la table `ingestion` :

    01/10  écrits 30   absents 0
    04/10  écrits 144  absents 3     (la veille existait encore en .jsonl)
    05/10  écrits 0    absents 6     -> plus rien depuis

Plutôt que de modifier le worker, c'est le dépôt — qui produit ces fichiers —
qui les envoie lui-même. Le worker garde ses trois autres circuits (matchs,
mouvements, signaux), qui fonctionnent.

CE QUI EST ENVOYÉ
-----------------
Les partitions de courbes de `parts/` : `live_{match,set1,set2}_*` (les trois
derniers jours) et `hist_{book,set1,set2}_*` (l'historique hebdomadaire). Les
secondes comblent au premier passage le trou ouvert le 03/10 : les partitions
live ne restent que trois jours dans le dépôt, l'historique, lui, reste.

Les ticks Polymarket / Kalshi ne sont PAS envoyés : ce ne sont pas des courbes
de cotes, et ils ont déjà leur archivage en Releases (archive_ticks.py).

CE QUI DÉCIDE D'UN ENVOI
------------------------
La TAILLE. Une partition compressée grossit par ajout de blocs gzip à la fin ;
si sa taille n'a pas changé, son contenu non plus. On ne se fie pas à la date
du fichier : sur un runner, c'est l'heure du checkout, elle change à chaque
fois et ferait tout renvoyer.

LE PIÈGE DES .gz
----------------
Ces fichiers sont faits de dizaines de blocs gzip mis bout à bout (51 dans
`live_match_2026-10-09.jsonl.gz`). Un décompresseur qui s'arrête au premier
bloc en lit 2 % — 899 lignes sur 47 188 — sans erreur. Chaque fichier est donc
décompressé EN ENTIER avant envoi, et son nombre de lignes est écrit dans les
métadonnées de l'objet et dans `_manifest.json`. Quiconque relira R2 pourra
vérifier qu'il obtient le même compte.

Un fichier illisible n'est pas envoyé : mieux vaut un trou signalé qu'une
copie corrompue qui passerait pour bonne.

CE QUE CE SCRIPT NE FAIT PAS
----------------------------
Il ne commite rien et n'écrit rien dans le dépôt : il ne peut donc ni faire
grossir GitHub, ni entrer en conflit avec les collecteurs qui poussent toutes
les trois minutes. Il ne supprime rien dans R2 : une partition purgée du dépôt
après trois jours reste dans R2, c'est précisément le but.
"""

import gzip
import os
import re
import sys

from r2_storage import R2Store, create_client, count_jsonl

PARTS = os.environ.get('PARTS_DIR', 'parts')
BUCKET = os.environ.get('R2_BUCKET', 'tennis-edge-courbes')
INCLUDE = re.compile(os.environ.get(
    'R2_INCLUDE',
    r'^(live_(match|set1|set2)_|hist_(book|set1|set2)_).+\.jsonl(\.gz)?$'))


def lignes(chemin):
    """Nombre de lignes, fichier entier — tous les blocs gzip compris.

    gzip.open de Python enchaîne les blocs concaténés ; on lit jusqu'au bout
    plutôt que de faire confiance à la taille.
    """
    return count_jsonl(chemin)


def main():
    sec = '--dry' in sys.argv
    if not os.path.isdir(PARTS):
        print(f'{PARTS}/ introuvable — lancer depuis la racine du dépôt.')
        return 1

    locaux = sorted(f for f in os.listdir(PARTS) if INCLUDE.match(f))
    print(f'{len(locaux)} partition(s) de courbes dans {PARTS}/')
    if not locaux:
        print('  RIEN À ENVOYER — le checkout a-t-il bien ramené parts/ ?')
        return 1

    if sec:
        for name in locaux:
            path = os.path.join(PARTS, name)
            print(f'  [simulation] {name:42} {lignes(path):>8} lignes')
        print(f'\nSimulation terminée pour {len(locaux)} partition(s); aucune connexion R2.')
        return 0

    store = R2Store(create_client(), BUCKET)
    report = store.sync_legacy_partitions(PARTS)
    print(
        f"\nR2 r2://{BUCKET}/parts/: "
        f"{report['uploaded']} version(s) immuable(s), "
        f"{report['unchanged']} déjà vérifiée(s), "
        f"{report['files']} fichier(s) au manifeste."
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
