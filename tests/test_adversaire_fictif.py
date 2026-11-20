import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import pronostics_du_jour as PD  # noqa: E402


def test_places_vides_du_tableau_ecartees():
    for n in ('R16P6', 'Qf1', 'WQF2', 'WSF1', 'TBD', 'Bye', 'Winner R32P4'):
        assert PD.adversaire_fictif(n), n
    for n in ('Casper Ruud', 'Q. Halys', 'Qinwen Zheng', 'Arthur Fils', 'Ugo Humbert'):
        assert not PD.adversaire_fictif(n), n


def test_matchs_a_venir_sans_adversaire_fictif(tmp_path):
    debut = (dt.datetime.utcnow() + dt.timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
    L = [{'commence_time': debut, 'home_team': 'Ben Shelton', 'away_team': 'R16P6', 'sport_title': 'ATP Paris'},
         {'commence_time': debut, 'home_team': 'Casper Ruud', 'away_team': 'Rafael Jodar', 'sport_title': 'ATP Paris'}]
    (tmp_path / 'matches_oddspapi.json').write_text(json.dumps(L), encoding='utf-8')
    out = PD.matchs_a_venir(str(tmp_path), dt.datetime.utcnow())
    assert [(x['home'], x['away']) for x in out] == [('Casper Ruud', 'Rafael Jodar')]
