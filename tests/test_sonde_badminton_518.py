"""518 : sonde des matchs de badminton à venir (lecture seule, aucun nom de joueur dans le journal)."""
import datetime as dt
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'scripts'))
import sonde_badminton_avenir as S  # noqa: E402


class Faux:
    def __init__(self, maintenant):
        self.octets, self.urls, self.m = 0, [], maintenant

    def get(self, chemin):
        self.urls.append(chemin)
        t = int(self.m.timestamp()) + 3600 * 2 + 86400 * (len(self.urls) - 1)
        ev = [{'id': 1, 'startTimestamp': t, 'status': {'type': 'notstarted'}, 'homeTeam': {'id': 7, 'name': 'Secret Nom'},
               'awayTeam': {'id': 8, 'name': 'Autre Nom'}, 'roundInfo': {'name': 'Round of 32'}, 'defaultPeriodCount': 3,
               'tournament': {'name': 'Open Factice, MS'}},
              {'id': 2, 'startTimestamp': t, 'status': {'type': 'notstarted'}, 'homeTeam': {'id': 9, 'name': 'TBD'},
               'awayTeam': {'id': 10, 'name': 'Encore Nom'}, 'tournament': {'name': 'Open Factice, XD'}}]
        self.octets += 1000
        return 200, {'events': ev}


def test_sonde():
    m = dt.datetime(2026, 11, 27, 20, tzinfo=dt.timezone.utc)
    c, L = Faux(m), []
    tot = S.sonder(c, m, L.append)
    assert len(c.urls) == S.JOURS and all('/category/259/events/' in u for u in c.urls)
    assert tot['a_venir'] == 2 * S.JOURS and tot['connus'] == S.JOURS
    texte = '\n'.join(L)
    for nom in ('Secret', 'Autre Nom', 'Encore'):
        assert nom not in texte
    assert "'SM': 1" in texte and "'mixte': 1" in texte


def test_workflow():
    y = open(os.path.join(R, '.github', 'workflows', 'sonde_badminton.yml'), encoding='utf-8').read()
    assert 'contents: read' in y and 'workflow_dispatch' in y and 'schedule' not in y
    assert '/scripts/sonde_badminton_avenir.py' in y
