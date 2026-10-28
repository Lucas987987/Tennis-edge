# -*- coding: utf-8 -*-
"""Sonde TennisApi des joueurs Challenger peu documentés (28/10/2026) — sans réseau."""
import datetime as dt
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import sonde_peu_documentes as SD  # noqa: E402

TS = lambda d: int(dt.datetime(d.year, d.month, d.day, 12, tzinfo=dt.timezone.utc).timestamp())


def ev(i, jour, adv, cat):
    return {'id': i, 'startTimestamp': TS(jour), 'status': {'type': 'finished'},
            'homeTeam': {'id': 7, 'name': 'Petit Joueur'}, 'awayTeam': {'id': 99, 'name': adv},
            'tournament': {'category': {'name': cat}}}


STATS = {'statistics': [{'period': 'ALL', 'groups': [{'statisticsItems': [
    {'key': 'firstServeAccuracy', 'homeValue': 40, 'homeTotal': 64, 'awayValue': 38, 'awayTotal': 60},
    {'key': 'firstServePointsAccuracy', 'homeValue': 28, 'homeTotal': 40, 'awayValue': 25, 'awayTotal': 38},
    {'key': 'secondServePointsAccuracy', 'homeValue': 12, 'homeTotal': 24, 'awayValue': 10, 'awayTotal': 22},
    {'key': 'aces', 'homeValue': 3, 'awayValue': 2}, {'key': 'doubleFaults', 'homeValue': 2, 'awayValue': 3}]}]}]}


class Faux:
    def __init__(self):
        self.n, self.codes, self.restant = 0, {}, 9999
        self.events = [ev(1, dt.date(2026, 3, 2), 'Alpha Connu', 'Challenger'),
                       ev(2, dt.date(2026, 2, 1), 'Beta Absent', 'ITF Men'),
                       ev(3, dt.date(2026, 1, 5), 'Gamma Absent', 'ITF Men'),
                       ev(4, dt.date(2026, 1, 9), 'Delta Absent', 'Challenger'),
                       ev(5, dt.date(2023, 1, 9), 'Trop Vieux', 'ITF Men')]

    def get(self, chemin):
        self.n += 1
        if '/events/previous/' in chemin:
            return 200, {'events': self.events, 'hasNextPage': False}
        if chemin.endswith('/4/statistics'):
            return 200, STATS
        return 404, None


class TestSonde(unittest.TestCase):
    def test_connu_inconnu_et_estimation(self):
        connus = {'k': [(dt.date(2026, 3, 3), SD.mots('Alpha Connu'))]}
        par_cat, par_joueur, total, moy = SD.sonder(Faux(), [('Petit Joueur', 'k', 400.0, 7)], connus,
                                                    dt.date(2026, 10, 28), journal=lambda *_: None)
        self.assertEqual(par_cat['challenger']['connus'], 1)
        self.assertEqual(par_cat['challenger']['manquants'], 1)
        self.assertEqual(par_cat['itf men']['manquants'], 2)             # le match de 2023 est ignoré
        self.assertEqual(par_cat['itf men']['taux_feuilles'], 0.0)
        self.assertEqual(par_cat['challenger']['taux_feuilles'], 1.0)
        self.assertEqual(moy, 64)
        self.assertAlmostEqual(total, 1.0)
        self.assertGreater(par_joueur[0]['balles_gagnees_estimees'], 0)

    def test_regle(self):
        self.assertFalse(SD.decider([{'gain_relatif': 2.0}], 299)['collecte_justifiee'])
        self.assertFalse(SD.decider([{'gain_relatif': 0.4}], 900)['collecte_justifiee'])
        self.assertTrue(SD.decider([{'gain_relatif': 0.6}, {'gain_relatif': 0.5}], 300)['collecte_justifiee'])


if __name__ == '__main__':
    unittest.main()
