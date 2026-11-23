#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vers_coffre.py — ranger des fichiers de run au coffre R2 PRIVÉ au lieu d'un artefact GitHub (23/11/2026, paquet 393).

Le dépôt est public : ses artefacts (« upload-artifact ») le sont aussi, téléchargeables par n'importe quel compte
GitHub. Les sorties qui contiennent des cotes, des bookmakers ou des résultats d'alertes vont donc ici :
prive/site/Tennis_Edge_Lab/journaux/<nom>/<fichier>, lisibles dans le Lab (/lab/journaux/<nom>/<fichier>, avec la clé).
Sans les secrets R2 : rien n'est envoyé (le fichier reste dans le run, qui est effacé à la fin).
Usage : python scripts/vers_coffre.py --nom suivi_outsiders suivi_outsiders.txt 'dossier/*.json'
"""
import glob
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))


def main(argv):
    args = argv[1:]
    if len(args) < 3 or args[0] != '--nom':
        print('usage : vers_coffre.py --nom NOM fichier…')
        return 2
    nom, motifs = args[1], args[2:]
    fichiers = sorted({f for m in motifs for f in glob.glob(m) if os.path.isfile(f)})
    sys.path.insert(0, ICI)
    try:
        import r2_io
        c = r2_io.client(quiet=True)
    except Exception:  # noqa: BLE001
        c = None
    if not c:
        print(f'{len(fichiers)} fichier(s) : coffre R2 absent, rien envoyé (rien de publié non plus).')
        return 0
    n = 0
    for f in fichiers:
        try:
            c.put(f'prive/site/Tennis_Edge_Lab/journaux/{nom}/{os.path.basename(f)}', open(f, 'rb').read())
            n += 1
        except Exception:  # noqa: BLE001 — jamais bloquant
            print(f'::warning::{os.path.basename(f)} non envoyé au coffre')
    print(f'{n} fichier(s) au coffre privé : /lab/journaux/{nom}/')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
