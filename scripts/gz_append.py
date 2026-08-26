#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gz_append.py — écriture des ticks en gzip-append (créé le 26/08/2026).

POURQUOI. Les collecteurs committaient du .jsonl BRUT toutes les 5-10 min
(~500 Mo/jour de deltas dans l'HISTORIQUE git, pour toujours), puis la
compression nocturne ajoutait la version .gz — l'historique stockait les
deux. Mesuré : +0,5 Go d'historique le seul 25/08 (US Open). À ce rythme, la
zone des 5 Go GitHub arrivait en jours, pas en mois.

COMMENT. Le format gzip accepte la CONCATÉNATION de membres : chaque lot de
lignes devient un membre compressé ajouté en 'ab' au fichier .jsonl.gz.
gzip.open() lit les membres enchaînés nativement — tous les lecteurs du
projet passent déjà par lui. Un tampon mémoire par fichier, vidé tous les
LOT_LIGNES ou LOT_SECONDES, plus un vidage atexit : au pire, un crash perd
quelques secondes de ticks (assumé — ce sont des ticks, pas des résultats).

Effet attendu sur l'historique : ~500 Mo/jour -> ~70-100 Mo/jour.
"""
import atexit
import gzip
import os
import threading
import time

LOT_LIGNES = int(os.environ.get('GZ_LOT_LIGNES', '200'))
LOT_SECONDES = float(os.environ.get('GZ_LOT_SECONDES', '45'))

_VERROU = threading.Lock()
_TAMPONS = {}          # path -> [lignes]
_DERNIER_FLUSH = {}    # path -> ts


def _flush_un(path):
    lignes = _TAMPONS.get(path)
    if not lignes:
        return
    bloc = ('\n'.join(lignes) + '\n').encode('utf-8')
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'ab') as f:
        f.write(gzip.compress(bloc, mtime=0))   # mtime=0 : sortie déterministe
        f.flush()
    _TAMPONS[path] = []
    _DERNIER_FLUSH[path] = time.monotonic()


def append_ligne(path, ligne):
    """Ajoute UNE ligne (str, sans \\n) au fichier gz ; vide le tampon par
    seuil de lignes ou d'âge. path doit finir en .jsonl.gz."""
    with _VERROU:
        _TAMPONS.setdefault(path, []).append(ligne)
        age = time.monotonic() - _DERNIER_FLUSH.get(path, 0)
        if len(_TAMPONS[path]) >= LOT_LIGNES or age >= LOT_SECONDES:
            _flush_un(path)


def flush_tout():
    """Vide tous les tampons — appelé en fin de run et par atexit."""
    with _VERROU:
        for p in list(_TAMPONS):
            _flush_un(p)


atexit.register(flush_tout)
