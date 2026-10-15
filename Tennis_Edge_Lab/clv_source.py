#!/usr/bin/env python3
"""clv_source.py — lecture de clv_history pour le Lab (15/10/2026).

Depuis la migration, clv_history.jsonl est découpé par mois dans le dossier
voisin clv_history/clv_history_YYYY-MM.jsonl (voir scripts/clv_store.py).
Un chemin nommé clv_history.jsonl est résolu vers ces partitions dès
qu'elles existent ; tout autre chemin est lu tel quel. L'ordre des lignes
est identique à l'ancien fichier (garanti et vérifié par clv_store).
Aucune dépendance : le Lab reste autonome.
"""
import re
from contextlib import contextmanager
from pathlib import Path

LEGACY = "clv_history.jsonl"
_NAME = re.compile(r"^clv_history_(\d{4}-\d{2})(?:_(\d+))?\.jsonl$")


def files(path):
    """Fichiers à lire pour `path`, dans l'ordre."""
    path = Path(path)
    if path.name == LEGACY:
        found = []
        folder = path.parent / "clv_history"
        if folder.is_dir():
            for p in folder.iterdir():
                m = _NAME.match(p.name)
                if m and p.is_file():
                    found.append(((m.group(1), int(m.group(2) or 1)), p))
        if found:
            return [p for _, p in sorted(found)]
    return [path] if path.is_file() else []


def exists(path):
    return bool(files(path))


def total_bytes(path):
    return sum(p.stat().st_size for p in files(path))


@contextmanager
def open_text(path):
    """Itérable de lignes sur toutes les partitions (with … as stream)."""
    paths = files(path)
    if not paths:
        raise FileNotFoundError(str(path))

    def lines():
        for p in paths:
            with p.open(encoding="utf-8") as f:
                yield from f

    yield lines()
