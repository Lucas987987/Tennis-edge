"""522 : étude « outsider confirmé » — définition des cas et règle de décision (données factices)."""
import os
import random
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'scripts'))
import etude_outsider_confirme as S  # noqa: E402


def test_cas():
    J = 86400
    M = [(0, 'j', 'G', 'A', 'T1', 'x', 'y', 1, 0.3),        # x outsider gagne
         (J, 'j', 'G', 'A', 'T1', 'x', 'z', 0, 0.4),        # x encore outsider, même tournoi : CAS (perdu)
         (2 * J, 'j', 'G', 'A', 'T1', 'z', 'w', 1, 0.7),    # z : précédent perdu, favori → rien
         (3 * J, 'j', 'G', 'A', 'T2', 'z', 'x', 0, 0.6),    # x outsider mais autre tournoi → témoin « outsiders » seul
         (4 * J, 'j', 'G', 'A', 'T2', 'v', 'x', 0, 0.8)]    # x a gagné en outsider au tour d'avant (T2) → CAS (gagné)
    out = S.cas(M, 10)
    assert [(p, w) for _, _, p, w in out['confirme']] == [(0.4, False), (0.19999999999999996, True)]
    assert out['apres_favori'] == []
    assert len(out['outsiders']) == 5


def test_regle():
    rnd = random.Random(3)
    L = [('A' if i % 2 else 'B', 0.3, rnd.random() < 0.38) for i in range(4000)]   # gagne plus souvent que 30 %
    d = S.juger(L)
    assert d['verdict'] == 'retenu' and d['beta_appris'] > 0 and d['beta_jugement'] > 0
    L = [('A' if i % 2 else 'B', 0.3, rnd.random() < 0.30) for i in range(4000)]
    assert S.juger(L)['verdict'] == 'non_retenu'
    assert S.juger(L[:1500])['verdict'] == 'trop_peu_de_cas'                     # 750 cas jugés


def test_workflow_et_source():
    y = open(os.path.join(R, '.github', 'workflows', 'etude_outsider_confirme.yml'), encoding='utf-8').read()
    assert 'workflow_dispatch' in y and 'schedule' not in y and 'git add -- rapport_outsider_confirme.json rapport_outsider_confirme2.json' in y
    src = open(os.path.join(R, 'scripts', 'etude_outsider_confirme.py'), encoding='utf-8').read()
    for interdit in ("['psw']", "['psl']", 'pinnacle'):   # les colonnes de cotes ne sont jamais lues
        assert interdit not in src.lower(), interdit
