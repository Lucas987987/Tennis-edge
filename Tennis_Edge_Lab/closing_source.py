#!/usr/bin/env python3
"""closing_source.py — closing_lines pour le Lab (16/10/2026).

Depuis la migration, closing_lines.json ne garde que les matchs « chauds » ;
les autres sont dans closing_lines/closing_lines_YYYY-MM.jsonl. Ce module
rend le dict complet, identique à celui des scripts : il délègue à
scripts/closing_store.py (une seule implémentation). Si ce script n'est pas
dans le checkout, il lit le fichier chaud seul et le SIGNALE.
"""
import importlib.util
import json
from pathlib import Path


def _store(repo):
    p = Path(repo) / "scripts" / "closing_store.py"
    if not p.is_file():
        return None
    spec = importlib.util.spec_from_file_location("closing_store", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_all(repo, default=None):
    repo = Path(repo)
    hot = repo / "closing_lines.json"
    store = _store(repo)
    if store is not None:
        return store.load_all_or(str(hot), default)
    if (repo / "closing_lines").is_dir():
        print("⚠️ closing_source : scripts/closing_store.py absent du checkout — "
              "archives closing_lines/ IGNORÉES, dict partiel.")
    if not hot.is_file():
        return default
    return json.loads(hot.read_text(encoding="utf-8"))
