import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import nos_resultats as NR  # noqa: E402


def test_masters_de_paris_sur_dur():
    table = {'paris': 'Clay'}                          # ce que l'archive associe au mot « paris »
    assert NR.surface_de('ATP Paris', table) == 'Hard'
    assert NR.surface_de('Rolex Paris Masters', table) == 'Hard'
    assert NR.surface_de('Roland Garros', table) == 'Clay'
    assert NR.surface_de('French Open, Paris', table) == 'Clay'
