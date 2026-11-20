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

import datetime
import gzip
import json
import os
import re
import sys

PARTS = os.environ.get('PARTS_DIR', 'parts')
BUCKET = os.environ.get('R2_BUCKET', 'tennis-edge-courbes')
PREFIX = os.environ.get('R2_PREFIX', 'parts/')
INCLUDE = re.compile(os.environ.get(
    'R2_INCLUDE',
    r'^(live_(match|set1|set2)_|hist_(book|set1|set2)_).+\.jsonl(\.gz)?$'))


def lignes(chemin):
    """Nombre de lignes, fichier entier — tous les blocs gzip compris.

    gzip.open de Python enchaîne les blocs concaténés ; on lit jusqu'au bout
    plutôt que de faire confiance à la taille.
    """
    ouvrir = gzip.open if chemin.endswith('.gz') else open
    n = 0
    with ouvrir(chemin, 'rb') as f:
        for _ in f:
            n += 1
    return n


def client():
    """Client S3 vers R2, ou None avec un message clair si un secret manque."""
    manque = [k for k in ('R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY',
                          'R2_ENDPOINT') if not os.environ.get(k)]
    if manque:
        print(f'SECRETS MANQUANTS : {", ".join(manque)}')
        print('  À ajouter dans Settings -> Secrets and variables -> Actions.')
        return None
    import boto3
    from botocore.config import Config
    return boto3.client(
        's3',
        endpoint_url=os.environ['R2_ENDPOINT'].rstrip('/'),
        aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
        region_name='auto',
        # Depuis boto3 1.36, les envois ajoutent par défaut des sommes de
        # contrôle que R2 n'accepte pas toujours. Cloudflare recommande de
        # ne les calculer que lorsqu'elles sont exigées.
        config=Config(request_checksum_calculation='when_required',
                      response_checksum_validation='when_required'),
    )


def distants(s3):
    """{nom: taille} des objets déjà présents sous le préfixe."""
    out = {}
    pag = s3.get_paginator('list_objects_v2')
    for page in pag.paginate(Bucket=BUCKET, Prefix=PREFIX):
        for o in page.get('Contents', []):
            out[o['Key'][len(PREFIX):]] = o['Size']
    return out


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

    s3 = None if sec else client()
    if not sec and s3 is None:
        return 1
    deja = distants(s3) if s3 else {}
    print(f'{len(deja)} objet(s) déjà dans r2://{BUCKET}/{PREFIX}')

    # Le manifeste précédent garde les comptes de lignes des fichiers qu'on
    # ne renvoie pas : on le reprend pour ne pas les perdre.
    manifeste = {}
    if s3 and '_manifest.json' in deja:
        try:
            corps = s3.get_object(Bucket=BUCKET, Key=PREFIX + '_manifest.json')
            manifeste = json.loads(corps['Body'].read()).get('fichiers', {})
        except Exception as e:                      # noqa: BLE001
            print(f'  manifeste précédent illisible ({e}) — reconstruit')

    envoyes, inchanges, illisibles, echecs = [], 0, [], []
    for nom in locaux:
        chemin = os.path.join(PARTS, nom)
        taille = os.path.getsize(chemin)
        if deja.get(nom) == taille:
            inchanges += 1
            continue
        try:
            n = lignes(chemin)
        except Exception as e:                      # noqa: BLE001
            illisibles.append(f'{nom} ({type(e).__name__})')
            continue
        etat = 'nouveau' if nom not in deja else f'{deja[nom]} -> {taille} o'
        print(f'  {"(simulation) " if sec else ""}{nom:42} {n:>8} lignes  {etat}')
        if sec:
            envoyes.append(nom)
            continue
        try:
            s3.upload_file(
                chemin, BUCKET, PREFIX + nom,
                ExtraArgs={'Metadata': {'lignes': str(n)},
                           'ContentType': 'application/gzip'
                           if nom.endswith('.gz') else 'application/x-ndjson'})
        except Exception as e:                      # noqa: BLE001
            echecs.append(f'{nom} ({type(e).__name__}: {e})')
            continue
        envoyes.append(nom)
        manifeste[nom] = {
            'octets': taille, 'lignes': n,
            'envoye_le': datetime.datetime.now(datetime.timezone.utc)
            .isoformat(timespec='seconds'),
        }

    if s3 and envoyes:
        s3.put_object(
            Bucket=BUCKET, Key=PREFIX + '_manifest.json',
            ContentType='application/json',
            Body=json.dumps({
                'maj': datetime.datetime.now(datetime.timezone.utc)
                .isoformat(timespec='seconds'),
                'fichiers': manifeste,
            }, ensure_ascii=False, indent=1).encode())

    print(f'\nenvoyés {len(envoyes)} · inchangés {inchanges} · '
          f'illisibles {len(illisibles)} · échecs {len(echecs)}')
    for x in illisibles:
        print(f'  ILLISIBLE, NON ENVOYÉ : {x}')
    for x in echecs:
        print(f'  ÉCHEC D\'ENVOI : {x}')
    # Rouge si quelque chose n'est pas parti : un trou silencieux dans R2
    # est exactement la panne qu'on vient de passer une semaine à ne pas voir.
    return 1 if (illisibles or echecs) else 0


if __name__ == '__main__':
    raise SystemExit(main())
