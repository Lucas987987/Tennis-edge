# -*- coding: utf-8 -*-
"""27/11/2026 (paquet 502) — tennis de table : le tour (et le format s'il est annoncé) rangés par la collecte ;
rattrapage des tours International (reprise, une requête par jour, aucun nom) ; workflows."""
import datetime as dt
import gzip
import json
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'scripts'))
import collecte_tennis_de_table as CT  # noqa: E402
import collecte_tours_tt as CTT  # noqa: E402


def ev(i, tour=None, rnd=None, dpc=None):
    e = {'id': i, 'startTimestamp': 1795561200, 'tournament': {'name': 'WTT Champions X, MS'}, 'homeTeam': {'id': 1, 'name': 'Joueur A'},
         'awayTeam': {'id': 2, 'name': 'Joueur B'}, 'status': {'type': 'finished', 'description': 'Ended'}, 'winnerCode': 1}
    if tour or rnd is not None:
        e['roundInfo'] = {k: v for k, v in (('name', tour), ('round', rnd)) if v is not None}
    if dpc:
        e['defaultPeriodCount'] = dpc
    return e


def test_ligne_range_tour_et_format():
    assert CT.ligne(ev(1, 'Final', 29, 7), 'International')['tour'] == 'Final'
    assert CT.ligne(ev(1, 'Final', 29, 7), 'International')['format'] == 4
    assert CT.ligne(ev(1, rnd=3), 'International')['tour'] == '#3'
    r = CT.ligne(ev(1), 'International')
    assert 'tour' not in r and 'format' not in r


class Client:
    def __init__(self, panne=()):
        self.urls, self.panne = [], set(panne)

    def get(self, chemin):
        self.urls.append(chemin)
        if chemin.endswith('/categories'):
            return 200, {'categories': [{'category': {'id': 7, 'name': 'International'}}, {'category': {'id': 8, 'name': 'Poland'}}]}
        jour = chemin.rsplit('/events/', 1)[1]
        if jour in self.panne:
            return 500, None
        d, m, y = map(int, jour.split('/'))
        return 200, {'events': [ev(d * 1000 + m, 'Final'), ev(d * 1000 + m + 1, 'Round of 16'), ev(d * 1000 + m + 2)]}


def test_rattrapage_reprise(tmp_path):
    f = str(tmp_path / 'tours.json.gz')
    auj, debut = dt.date(2026, 11, 27), dt.date(2026, 11, 20)
    c = Client(panne={'22/11/2026'})
    lignes = []
    res = CTT.passage(c, auj, f, lignes.append, debut)
    assert res == {'jours': 6, 'manques': 1, 'reste': 1, 'arret': None}
    assert c.urls[0].endswith('/categories') and all('/category/7/events/' in u for u in c.urls[1:])
    with gzip.open(f, 'rt', encoding='utf-8') as g:
        d = json.load(g)
    assert d['jusqu_au'] == '2026-11-26' and d['categorie'] == 7
    assert d['tours'][str(26 * 1000 + 11)] == 'Final' and str(26 * 1000 + 11 + 2) not in d['tours']
    assert 'Joueur' not in json.dumps(d) and 'Joueur' not in '\n'.join(lignes)
    c2 = Client()
    res = CTT.passage(c2, auj + dt.timedelta(days=3), f, lignes.append, debut)   # seul le jour manqué est redemandé
    assert res['jours'] == 1 and res['reste'] == 0 and c2.urls == ['/api/table-tennis/category/7/events/22/11/2026']
    c3 = Client()
    assert CTT.passage(c3, auj + dt.timedelta(days=4), f, lignes.append, debut)['jours'] == 0 and c3.urls == []
    assert 'rattrapage terminé' in lignes[-2]


def test_workflows():
    y = open(os.path.join(R, '.github', 'workflows', 'collecte_tours_tt.yml'), encoding='utf-8').read()
    for x in ('/scripts/allsports.py', '/scripts/collecte_tennis_de_table.py', '/scripts/collecte_tours_tt.py',
              'git add -A -- historique/tennis_de_table/tours_international.json.gz', "ALLSPORTS_RESERVE: '60'"):
        assert x in y, x
    e = open(os.path.join(R, '.github', 'workflows', 'etude_format_tt.yml'), encoding='utf-8').read()
    assert 'python tennis_de_table/etude_format_tt.py .' in e and 'git add -- tennis_de_table/rapport_format_tt.json' in e
    assert 'workflow_dispatch' in e and 'schedule' not in e
