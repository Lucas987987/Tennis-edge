"""Paquet 399 — piste suivie : outsider peu documenté (règle écrite le 24/11/2026)."""
import math
import os
import random
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import suivi_outsider_peu_documente as S  # noqa: E402


def match(uid, p, mj, gagnant, debut='2026-11-26T10:00', c='CH', interrompu=None):
    return {'uid': uid, 'circuit': c, 'debut': debut, 'matchs_joues': mj,
            'dernier': {'combinaison': {'p_home': p}}, 'reel': {'gagnant': gagnant, 'interrompu': interrompu}}


def test_profil_et_date():
    res = {'matchs': [match('a', .85, [120, 12], 'away'), match('b', .2, [5, 300], 'away'),
                      match('c', .7, [120, 90], 'home'), match('d', .7, [40, 10], 'home'),
                      match('e', .85, [120, 12], 'home', debut='2026-11-24T10:00'),
                      match('f', .85, [120, 12], 'home', interrompu='abandon')]}
    st = {}
    assert S.mettre_a_jour(st, res) == 2
    v = sorted((x['p'], x['y']) for x in st.values())
    assert v == [(0.8, 1), (0.85, 0)]
    assert S.mettre_a_jour(st, res) == 0


def _simule(n, a_vrai, graine=1):
    r = random.Random(graine)
    out = []
    for i in range(n):
        p = r.uniform(0.6, 0.97)
        q = 1 / (1 + math.exp(-a_vrai * math.log(p / (1 - p))))
        out.append({'c': 'CH', 'd': f'2026-12-{1 + i * 28 // n:02d}T{i % 24:02d}:00', 'p': p, 'y': int(r.random() < q)})
    return out


def test_regle():
    assert S.decision(_simule(999, .6))[0] == 'en cours'
    st, m, raisons = S.decision(_simule(1200, .55))
    assert st == 'retenue', raisons
    assert m['pente_apprise'] < 1
    st, _, raisons = S.decision(_simule(1200, 1.0, graine=3))
    assert st == 'écartée'
