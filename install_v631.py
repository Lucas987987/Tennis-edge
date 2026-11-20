#!/usr/bin/env python3
"""Install V6.3.1 in an existing Tennis-edge checkout; no Git operations."""
from pathlib import Path
import argparse
import re

OLD = "- cron: '20 4 * * *'"
NEW = "- cron: '20 5 * * 0'"

def install(root: Path):
    root = root.resolve()
    required = [
        '.github/workflows/lab_incremental_v631.yml',
        'Tennis_Edge_Lab/incremental_v631.py',
        'Tennis_Edge_Lab/tests/test_incremental_v631.py',
    ]
    for rel in required:
        if not (root / rel).is_file():
            raise FileNotFoundError(f'Extract ZIP to root first: {rel}')
    path = root / '.github/workflows/lab_autonomous.yml'
    if not path.is_file():
        raise FileNotFoundError(path)
    original = path.read_text(encoding='utf8')
    # Only change the ONE schedule entry in the existing full-analysis workflow.
    # Never patch any collector or other workflow.
    if original.count(OLD) == 1:
        output = original.replace(OLD, NEW, 1)
        path.write_text(output, encoding='utf8')
        print('✅ V6.3.1 : recherche exhaustive chaque dimanche à 05:20 UTC.')
    elif original.count(NEW) == 1 and OLD not in original:
        print('✅ V6.3.1 déjà installée : cadence hebdomadaire inchangée.')
    else:
        raise ValueError('Unexpected lab_autonomous.yml schedule; refusing changes')
    print('✅ Suivi prospectif quotidien à 04:20 UTC dans lab_incremental_v631.yml.')
    print('✅ Aucun registre, preuve ou donnée source modifié.')
    print('⚠️ Premier run : cache vide, une indexation complète est normale.')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    install(Path(ap.parse_args().root))
