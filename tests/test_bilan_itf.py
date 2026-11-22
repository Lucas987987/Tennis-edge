"""Paquet 360 — couverture du point par point ITF pour les joueurs de Challenger (comptes seulement)."""
import gzip
import json
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import bilan_itf as B  # noqa: E402


def _ecrire(p, lignes):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with gzip.open(p, 'wt', encoding='utf-8') as f:
        for x in lignes:
            f.write(json.dumps(x) + '\n')


def test_couverture_avant_le_match_seulement(tmp_path):
    _ecrire(str(tmp_path / 'f' / '2026-11-20.jsonl.gz'), [
        {'categorie': 'Challenger', 'jour': '2026-11-20', 'home': {'id': 1}, 'away': {'id': 2}},
        {'categorie': 'ATP', 'jour': '2026-11-20', 'home': {'id': 1}, 'away': {'id': 3}}])
    _ecrire(str(tmp_path / 'i' / '2026-11-10.jsonl.gz'), [
        {'jour': '2026-11-10', 'jeux': [[1]], 'service': {'home': [40, 60], 'away': [30, 55]}, 'home': {'id': 1}, 'away': {'id': 9}},
        {'jour': '2026-11-10', 'jeux': None, 'service': None, 'home': {'id': 2}, 'away': {'id': 9}}])     # sans déroulé
    _ecrire(str(tmp_path / 'i' / '2026-11-21.jsonl.gz'), [
        {'jour': '2026-11-21', 'jeux': [[1]], 'service': {'home': [40, 60], 'away': [30, 55]}, 'home': {'id': 2}, 'away': {'id': 9}}])  # après
    M = B.matchs_challenger('2026-11-01', str(tmp_path / 'f'))
    assert M == [('2026-11-20', 1, 2)]                       # le match ATP n'entre pas
    res = B.couverture(M, B.itf_par_joueur(str(tmp_path / 'i')))
    assert res == [(1, 60), (0, 0)]                          # joueur 2 : son match ITF est APRÈS, et l'autre sans déroulé
    d = B.resumer(res)
    assert d['tranches'][0]['n'] == 1 and d['tranches'][1]['n'] == 1


def test_workflow():
    y = open(os.path.join(RACINE, '.github', 'workflows', 'itf_points.yml'), encoding='utf-8').read()
    assert '/scripts/bilan_itf.py' in y and 'python scripts/bilan_itf.py 30' in y
