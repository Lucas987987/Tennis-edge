# -*- coding: utf-8 -*-
"""27/11/2026 (paquet 508) — collecte du badminton : catégories lues une fois, jours rangés comme le tennis de table
(débordement ±12 h écarté, score de chaque set), reprise, aucun nom dans le journal, workflow."""
import datetime as dt
import json
import os
import sys
import tempfile

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'scripts'))
import allsports as AS  # noqa: E402
import collecte_badminton as CB  # noqa: E402
import collecte_tennis_de_table as CT  # noqa: E402


class Faux:
    def __init__(self):
        self.urls = []

    def bilan(self):
        return f'{len(self.urls)} requêtes'

    def get(self, chemin):
        self.urls.append(chemin)
        if chemin == '/api/badminton/tournament/categories':
            return 200, {'categories': [{'id': 77, 'name': 'International'}]}
        j, m, a = map(int, chemin.rsplit('/events/', 1)[1].split('/'))
        d = dt.datetime(a, m, j, 10, tzinfo=dt.timezone.utc)
        ev = lambda i, t, st='finished': {'id': i, 'startTimestamp': int(t.timestamp()), 'winnerCode': 1,
                                          'tournament': {'uniqueTournament': {'id': 5, 'name': 'Welsh International, Singles'}},
                                          'homeTeam': {'id': 1, 'name': 'Joueuse Secrète'}, 'awayTeam': {'id': 2, 'name': 'Autre'},
                                          'status': {'type': st, 'description': 'Ended'}, 'roundInfo': {'name': 'Final'},
                                          'homeScore': {'period1': 21, 'period2': 21}, 'awayScore': {'period1': 16, 'period2': 10}}
        return 200, {'events': [ev(j * 100 + m, d), ev(j * 100 + m + 1, d - dt.timedelta(hours=14))]}   # la veille : écarté


def test_collecte_et_reprise():
    dossier = tempfile.mkdtemp()
    c, lignes = Faux(), []
    auj = dt.date(2026, 11, 27)
    res = CB.passage(c, auj, dossier, lignes.append, debut=auj - dt.timedelta(days=4))
    assert res['jours'] == 4 and res['matchs'] == 4
    assert c.urls[0] == '/api/badminton/tournament/categories' and len(c.urls) == 1 + 4
    L = AS.lire_jsonl(CT.chemin('2026-11-25', dossier))
    assert len(L) == 1 and L[0]['manches'] == [[21, 16], [21, 10]] and L[0]['ligue'] == 'International'
    assert L[0]['tour'] == 'Final' and L[0]['tournoi'] == 'Welsh International, Singles'
    etat = json.load(open(os.path.join(dossier, 'etat.json'), encoding='utf-8'))
    assert etat['categories'] == [['International', 77]]
    assert 'Secrète' not in '\n'.join(lignes) and 'badminton :' in lignes[0]
    c2 = Faux()                                                    # catégories gardées ; seul hier est redemandé
    res = CB.passage(c2, auj, dossier, lignes.append, debut=auj - dt.timedelta(days=4))
    assert c2.urls == [] and res['jours'] == 0
    c3 = Faux()
    res = CB.passage(c3, auj + dt.timedelta(days=1), dossier, lignes.append, debut=auj - dt.timedelta(days=4), heure=3)
    assert res.get('saute') and c3.urls == []                       # historique fait, avant 6 h UTC
    res = CB.passage(c3, auj + dt.timedelta(days=1), dossier, lignes.append, debut=auj - dt.timedelta(days=4), heure=9)
    assert res['jours'] >= 1


def test_workflow():
    y = open(os.path.join(R, '.github', 'workflows', 'collecte_badminton.yml'), encoding='utf-8').read()
    for x in ('/scripts/collecte_badminton.py', '/scripts/collecte_tennis_de_table.py', '/historique/badminton/',
              'git add -A -- historique/badminton', 'python scripts/collecte_badminton.py "$MINUTES"'):
        assert x in y, x
    assert 'historique/tennis_de_table' not in y
