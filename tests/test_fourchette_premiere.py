import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import match_simule as MS  # noqa: E402


def test_elargit_seulement_la_premiere_balle_autour_du_milieu():
    r = MS.elargir('premiere_pct', {'moy': 62.0, 'p10': 56.0, 'p90': 68.0})
    assert r['moy'] == 62.0 and abs((r['p10'] + r['p90']) / 2 - 62.0) < 0.06
    assert abs((r['p90'] - r['p10']) - 1.23 * 12.0) < 0.15
    assert MS.elargir('aces', {'moy': 5, 'p10': 2, 'p90': 8}) == {'moy': 5, 'p10': 2, 'p90': 8}


def test_reste_entre_0_et_100():
    r = MS.elargir('premiere_pct', {'moy': 95.0, 'p10': 90.0, 'p90': 99.0})
    assert r['p90'] <= 100.0 and r['p10'] >= 0.0
    assert MS.elargir('premiere_pct', None) is None
