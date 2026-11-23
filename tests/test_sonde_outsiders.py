"""Paquet 397 — sonde des outsiders peu documentés : cibles, comptage, règle, identités à vérifier."""
import datetime as dt
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import sonde_outsiders_inconnus as S  # noqa: E402
import elo as E  # noqa: E402


def m(uid, home, away, p, mj, gagnant, debut='2026-11-10T12:00', c='CH'):
    return {'uid': uid, 'home': home, 'away': away, 'circuit': c, 'debut': debut, 'matchs_joues': mj,
            'reel': {'gagnant': gagnant}, 'p': p}


def test_cibles_outsiders_seulement():
    res = {'matchs': [m('a', 'Fav', 'Inconnu', .9, [120, 5], 'away'),
                      m('b', 'Connu1', 'Connu2', .7, [120, 80], 'home'),
                      m('c', 'PeuFav', 'Connu3', .6, [10, 80], 'home'),               # favori peu documenté : non
                      m('d', 'Inconnu2', 'Fav2', .2, [3, 200], 'away'),
                      m('e', 'Fav3', 'Vieux', .9, [120, 5], 'home', debut='2026-10-01T10:00')]}
    c = S.cibles(res, lambda x: x['p'])
    assert [(n, g) for n, _, _, g in c] == [('Inconnu', True), ('Inconnu2', False)]


def test_compter_simples_termines_depuis_juin_2024():
    ts = lambda d: int(dt.datetime(*d, tzinfo=dt.timezone.utc).timestamp())  # noqa: E731
    simple = {'homeTeam': {'name': 'A', 'subTeams': []}, 'awayTeam': {'name': 'B', 'subTeams': []}}
    ev = [dict(simple, status={'type': 'finished'}, startTimestamp=ts((2025, 3, 1)), tournament={'category': {'name': 'ITF Men'}}),
          dict(simple, status={'type': 'finished'}, startTimestamp=ts((2023, 3, 1)), tournament={'category': {'name': 'ITF Men'}}),
          dict(simple, status={'type': 'canceled'}, startTimestamp=ts((2025, 3, 1)), tournament={'category': {'name': 'ITF Men'}}),
          {'homeTeam': {'name': 'A / C'}, 'awayTeam': {'name': 'B / D'}, 'status': {'type': 'finished'},
           'startTimestamp': ts((2025, 3, 1)), 'tournament': {'category': {'name': 'ITF Men'}}}]
    assert sum(S.compter(ev).values()) == 1


def test_regle_fixee_avant():
    peu = [{'tennisapi': 10, 'classement': 9}] * 30
    assert S.decider(peu)['donnees_manquantes'] is False
    manque = [{'tennisapi': 40, 'classement': 12}] * 30
    assert S.decider(manque)['donnees_manquantes'] is True
    assert S.decider(manque[:10])['donnees_manquantes'] is None


def test_identites_a_verifier():
    J = {'zachviiala': {'nom': 'Zach Viiala', 'matchs': 27}, 'viialazachary': {'nom': 'Zachary Viiala', 'matchs': 1},
         'alexandershevchenko': {'nom': 'Alexander Shevchenko', 'matchs': 339},
         'carleshernandez': {'nom': 'Carles Hernandez', 'matchs': 130}}
    d = S.doublons_possibles(['Zachary Viiala', 'Aleksandr Shevchenko', 'Alex Hernandez'], J, E.cle, E.mots)
    assert {x['autre_nom'] for x in d} == {'Zach Viiala', 'Alexander Shevchenko'}
