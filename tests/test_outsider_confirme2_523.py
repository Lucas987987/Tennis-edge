"""523 : l'outsider confirmé comparé aux autres outsiders de même % (données factices)."""
import os
import random
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'scripts'))
import etude_outsider_confirme2 as S  # noqa: E402


def monde(effet, n=12000, seed=4):
    """Tous les outsiders gagnent 1,2 fois plus souvent que leur % (réglage général) ; les confirmés + effet."""
    rnd = random.Random(seed)
    L = []
    for i in range(n):
        p = rnd.uniform(0.1, 0.49)
        c = 1 if (i // 2) % 4 == 0 else 0
        q = S._sg(S._lg(p) + 0.2 + (effet if c else 0))
        L.append(('A' if i % 2 else 'B', p, rnd.random() < q, c))
    return L


def test_reglage_general_absorbe():
    d = S.juger(monde(0.0))
    assert d['verdict'] == 'non_retenu'                     # le réglage général n'est pas un effet de l'outsider confirmé
    assert abs(d['reglage_general_appris'][0]) > 0.05


def test_effet_propre_retenu():
    d = S.juger(monde(0.5, n=16000))
    assert d['verdict'] == 'retenu' and d['beta_appris'] > 0 and d['beta_jugement'] > 0


def test_observations():
    out = {'confirme': [('G', 'A', 0.3, True)], 'outsiders': [('G', 'A', 0.3, True), ('G', 'A', 0.4, False)]}
    assert S.observations(out) == [('G', 'A', 0.3, True, 1), ('G', 'A', 0.4, False, 0)]
