#!/usr/bin/env python3
"""Évite les commits quotidiens « vides » (V6.6).

Pour chaque fichier JSON donné : si la version de travail ne diffère de la
version committée (HEAD) que par des horodatages volatils, la version HEAD
est restaurée. Ensuite `git diff --quiet` décide s'il y a quelque chose à
publier. Aucun autre fichier n'est touché.

Usage : python3 Tennis_Edge_Lab/commit_guard.py --root . fichier1.json fichier2.json ...
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

VOLATILE_KEYS = frozenset({
    "generated_at", "checked_at", "latest_cutoff_utc", "fetched_at",
    "created_at_utc_run", "runtime_seconds",
})


def strip_volatile(value):
    if isinstance(value, dict):
        return {k: strip_volatile(v) for k, v in value.items() if k not in VOLATILE_KEYS}
    if isinstance(value, list):
        return [strip_volatile(v) for v in value]
    return value


def head_bytes(root: pathlib.Path, rel: str):
    result = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=root,
                            capture_output=True)
    return result.stdout if result.returncode == 0 else None


def only_volatile_changes(old: bytes, new: bytes) -> bool:
    try:
        return strip_volatile(json.loads(old)) == strip_volatile(json.loads(new))
    except ValueError:
        return old == new


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root).resolve()
    restored = changed = 0
    for rel in args.files:
        path = root / rel
        if not path.is_file():
            continue
        old = head_bytes(root, rel)
        if old is None:
            changed += 1
            continue
        new = path.read_bytes()
        if old == new:
            continue
        if only_volatile_changes(old, new):
            path.write_bytes(old)
            restored += 1
        else:
            changed += 1
    print(f"commit_guard : {changed} fichier(s) modifié(s), {restored} restauré(s) (horodatage seul)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
