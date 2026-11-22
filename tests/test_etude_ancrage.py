"""Paquet 342 — ancrage et nombre de jeux : la production est reproduite exactement, le % ne bouge jamais, la règle
ne conclut rien sous 1 000 matchs jugés, et aucun script de l'algo ne lit le rapport."""
import glob
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import etude_ancrage as EA  # noqa: E402
import modele as MM  # noqa: E402

X = {'a': 0.68, 'b': 0.58, 'p': 0.78, 'sigma': 0.22, 'sg': 2, 'tb': 7, 'total': 21, 'service': [66.0, 60.0]}


def test_production_reproduite_et_pourcentage_inchange():
    dist, a, b = EA.variante(X, 0.0, 0.0)
    assert (a, b) == (X['a'], X['b'])
    for k, d in ((0.2, 0.0), (0.0, 0.1), (-0.1, -0.05)):
        _, a2, b2 = EA.variante(X, k, d)
        v = MM.match_forme(a2, b2, 2, X['sigma'], 7)['victoire']
        v0 = MM.match_forme(X['a'], X['b'], 2, X['sigma'], 7)['victoire']
        assert abs(v - v0) < 2e-3


def test_niveau_releve_donne_plus_de_jeux():
    moy = lambda d: sum(k * v for k, v in d.items()) / sum(d.values())
    assert moy(EA.variante(X, 0.0, 0.15)[0]) > moy(EA.variante(X, 0.0, 0.0)[0])


def test_rien_conclu_sous_1000():
    xs = []
    for i in range(30):
        y = dict(X, circuit='CH', debut='2026-11-01' if i < 15 else '2026-11-10', total=20 + i % 5)
        xs.append(y)
    r = EA.etudier(xs)
    for cle in ('CH|ECART', 'CH|NIVEAU'):
        assert r['cases'][cle]['retenu'] is False and 'pas encore jugeable' in r['cases'][cle]['raison']


def test_regle():
    assert (EA.GAIN_MIN, EA.N_MIN, EA.COUPURE) == (0.001, 1000, '2026-11-08')
    assert 0.0 in EA.GRILLES['ECART'] and 0.0 in EA.GRILLES['NIVEAU']


def test_aucun_script_de_l_algo_ne_lit_le_rapport():
    for p in glob.glob(os.path.join(RACINE, 'simulateur', '*.py')) + glob.glob(os.path.join(RACINE, 'scripts', '*.py')):
        if os.path.basename(p) != 'etude_ancrage.py':
            assert 'rapport_ancrage' not in open(p, encoding='utf-8').read(), p
