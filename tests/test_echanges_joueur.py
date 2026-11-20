import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import echanges_joueur as EJ  # noqa: E402

J = dt.date(2026, 10, 30)


def _d(jours, tranche, pts, scope='total'):
    return (J - dt.timedelta(days=jours), 'Hard', 'ATP', scope, tranche, pts, pts // 2)


def test_profil_frappes_et_seuil():
    D = {'a': [_d(10, '1-3', 100), _d(10, '4-6', 60), _d(20, '7-9', 30), _d(20, '10', 10),
               _d(20, '10', 500, scope='service'),          # hors « total » : ignoré
               _d(400, '10', 1000),                          # plus d'un an : ignoré
               (J, 'Hard', 'ATP', 'total', '10', 1000, 0)]}   # le jour même : exclu
    p = EJ.Echanges(D).profil('a', J)
    assert p['points'] == 200 and p['jours_charts'] == 2
    assert abs(p['frappes'] - (100 * 2 + 60 * 5 + 30 * 8 + 10 * 11.5) / 200) < 0.01
    assert p['long_pct'] == 20.0 and p['court_pct'] == 50.0
    assert EJ.Echanges({'b': [_d(5, '1-3', 50)]}).profil('b', J) is None
    assert EJ.Echanges({}).profil('x', J) is None
