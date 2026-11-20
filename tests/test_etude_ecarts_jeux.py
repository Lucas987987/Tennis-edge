import json, os, sys
ICI = os.path.dirname(os.path.abspath(__file__)); RAC = os.path.dirname(ICI)
sys.path.insert(0, os.path.join(RAC, 'simulateur'))
import etude_ecarts_jeux as E


def test_distribution_ancree_sur_le_pct():
    x = {'a': 0.62, 'b': 0.56, 'p': 0.70, 'tb': None}
    for s in (0.10, 0.30):
        Ec, S = E.distribution(x, s)
        assert abs(sum(Ec.values()) - 1) < 1e-6
        assert abs(S.get('2-0', 0) + S.get('2-1', 0) - 0.70) < 0.01


def test_sigma_plus_grand_elargit_les_ecarts():
    x = {'a': 0.60, 'b': 0.58, 'p': 0.55, 'tb': None}
    v = lambda D: sum(p * e * e for e, p in D.items())
    assert v(E.distribution(x, 0.40)[0]) > v(E.distribution(x, 0.10)[0])


def test_rapport_public_et_regle():
    R = json.load(open(os.path.join(RAC, 'simulateur', 'rapport_ecarts_jeux.json'), encoding='utf-8'))
    txt = json.dumps(R, ensure_ascii=False).lower()
    assert 'marché' not in txt and 'pinnacle' not in txt
    for c, v in R['circuits'].items():
        assert v['adopte'] is False
