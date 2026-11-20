import datetime as dt
import importlib.util
import sys
import os

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, "scripts"))
_s = importlib.util.spec_from_file_location('cc_dec', os.path.join(R, 'scripts', 'capture_closing.py'))
CC = importlib.util.module_from_spec(_s)
_s.loader.exec_module(CC)


def test_redecouverte_apres_minuit_et_toutes_les_6_heures():
    a = {'_discovered_at': '2026-10-30T21:39:42'}
    assert not CC._tournaments_stale(a, now=dt.datetime(2026, 10, 30, 23, 50))
    assert CC._tournaments_stale(a, now=dt.datetime(2026, 10, 31, 0, 5))          # nouveau jour UTC
    b = {'_discovered_at': '2026-10-31T00:05:00'}
    assert not CC._tournaments_stale(b, now=dt.datetime(2026, 10, 31, 5, 0))
    assert CC._tournaments_stale(b, now=dt.datetime(2026, 10, 31, 6, 30))         # plus de 6 h
    assert CC._tournaments_stale({}) and CC._tournaments_stale({'_discovered_at': 'x'})
