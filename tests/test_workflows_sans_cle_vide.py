# -*- coding: utf-8 -*-
"""24/11/2026 (paquet 402) — un « env: » laissé vide (valeur nulle) fait refuser le fichier par GitHub : le workflow
n'apparaît plus que sous son chemin (book_index.yml, elo.yml, player_profiles.yml) et ne tourne plus. Aucune clé sans
valeur ne doit rester sans contenu en dessous. Lecture ligne à ligne (PyYAML n'est pas installé sur le runner)."""
import glob
import os
import re

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
CLE = re.compile(r'^(\s*)(- )?([A-Za-z0-9_.-]+):\s*(#.*)?$')
# Déclencheurs que GitHub accepte sans valeur (« workflow_dispatch: » seul est la forme courante).
DECLENCHEURS = {'workflow_dispatch', 'push', 'pull_request', 'workflow_call', 'release', 'create', 'delete'}


def _significatives(lignes):
    for i, l in enumerate(lignes):
        s = l.split('#', 1)[0] if l.lstrip().startswith('#') else l
        if s.strip():
            yield i, l


def cles_vides(texte):
    """Clés sans valeur sur leur ligne et sans aucun contenu plus indenté (ou liste au même niveau) en dessous."""
    L = [(i, l) for i, l in _significatives(texte.splitlines())]
    fautes = []
    for k, (i, l) in enumerate(L):
        m = CLE.match(l)
        if not m or m.group(3) in DECLENCHEURS:
            continue
        ind = len(m.group(1)) + (2 if m.group(2) else 0)
        if k + 1 >= len(L):
            fautes.append((i + 1, m.group(3)))
            continue
        n = L[k + 1][1]
        ind_n = len(n) - len(n.lstrip())
        if ind_n > ind or (ind_n == ind and n.lstrip().startswith('- ')):
            continue
        fautes.append((i + 1, m.group(3)))
    return fautes


def test_detecte_env_vide():
    t = "jobs:\n  a:\n    steps:\n      - name: x\n        env:   # rien\n        run: echo\n"
    assert cles_vides(t) == [(5, 'env')]
    assert cles_vides("on:\n  push:\n    branches: [main]\njobs:\n  a:\n    steps:\n    - run: echo\n") == []


def test_aucune_cle_vide_dans_les_workflows():
    fautes = []
    for f in sorted(glob.glob(os.path.join(RACINE, '.github', 'workflows', '*.yml'))):
        with open(f, encoding='utf-8') as fh:
            for ligne, cle in cles_vides(fh.read()):
                fautes.append(f"{os.path.basename(f)}:{ligne} {cle}")
    assert not fautes, fautes
