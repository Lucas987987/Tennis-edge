# -*- coding: utf-8 -*-
"""27/11/2026 (paquet 505) — sonde des autres sports : lecture seule, aucun nom de joueur dans le journal, budget de
requêtes, sport introuvable signalé."""
import datetime as dt
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'scripts'))
import sonde_sports as SS  # noqa: E402


class Faux:
    def __init__(self):
        self.urls, self.octets = [], 0

    def get(self, chemin):
        self.urls.append(chemin)
        self.octets += 2048
        if '/beach-volley/' in chemin or '/beachvolley/' in chemin:
            return 404, None
        if chemin.endswith('/categories'):
            return 200, {'categories': [{'category': {'id': 1, 'name': 'International'}, 'totalEvents': 40},
                                        {'category': {'id': 2, 'name': 'USA'}, 'totalEvents': 12}]}
        if '/events/' in chemin:
            e = {'id': 9, 'status': {'type': 'finished'}, 'tournament': {'uniqueTournament': {'name': 'Coupe X'}},
                 'homeTeam': {'name': 'Joueur Secret'}, 'awayTeam': {'name': 'Autre Secret'}, 'roundInfo': {'name': 'Final'},
                 'homeScore': {'period1': 21, 'period2': 18, 'period3': 21}, 'awayScore': {'period1': 15, 'period2': 21, 'period3': 19}}
            return 200, {'events': [e, dict(e, id=10, status={'type': 'notstarted'})]}
        if chemin.endswith('/lineups'):
            return 200, {'home': {'players': [{'statistics': {'secondsPlayed': 600}}, {}]}, 'away': {'players': [{}]}}
        return 200, {'statistics': [{'groups': [1, 2, 3]}]}


def test_sonde():
    c, lignes = Faux(), []
    res = SS.sonder(c, dt.date(2026, 11, 27), lignes.append)
    txt = '\n'.join(lignes)
    assert 'Secret' not in txt
    assert [r['sport'] for r in res] == [s for s, _ in SS.SPORTS]
    assert next(r for r in res if r['sport'] == 'beach-volley')['trouve'] is False
    b = next(r for r in res if r['sport'] == 'basket-ball')
    assert b['hier'] == 52 and b['historique'][5] == 52
    assert 'temps de jeu connu pour 1' in txt and 'Coupe X 2' in txt and 'tour connu 1/1' in txt
    assert len(c.urls) <= 75


def test_workflow_lecture_seule():
    y = open(os.path.join(R, '.github', 'workflows', 'sonde_sports.yml'), encoding='utf-8').read()
    assert 'contents: read' in y and 'git ' not in y and 'workflow_dispatch' in y and 'schedule' not in y
