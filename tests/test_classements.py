"""Classements (23/10/2026) : rang au jour du match (jamais futur), lecture TennisApi, valeur pour un joueur
peu connu, rang et tête de série gardés dans la feuille."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
import classements as CL  # noqa: E402
import classements_tennisapi as CT  # noqa: E402
import feuilles_match as FM  # noqa: E402


class Rangs(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        r = self.d.name
        os.makedirs(os.path.join(r, 'sack', 'atp'))
        open(os.path.join(r, 'sack', 'atp', 'atp_players.csv'), 'w').write('player_id,name_first,name_last\n1,Ana,Bel\n2,Cora,Dix\n')
        open(os.path.join(r, 'sack', 'atp', 'atp_rankings_current.csv'), 'w').write(
            'ranking_date,rank,player,points\n20260601,300,1,100\n20260608,250,1,120\n20260608,40,2,900\n')
        os.makedirs(os.path.join(r, 'feuilles', 'classements'))
        json.dump({'ATP': {CL.E.cle('Ana Bel'): [180, 300, 'Ana Bel']}},
                  open(os.path.join(r, 'feuilles', 'classements', '2026-10-20.json'), 'w'))
        self.C = CL.charger(os.path.join(r, 'sack'), r)

    def tearDown(self):
        self.d.cleanup()

    def test_point_dans_le_temps(self):
        a = CL.E.cle('Ana Bel')
        self.assertEqual(self.C.rang_au(a, dt.date(2026, 6, 5)), 300)
        self.assertEqual(self.C.rang_au(a, dt.date(2026, 6, 8)), 300)                # le jour même : pas encore
        self.assertEqual(self.C.rang_au(a, dt.date(2026, 10, 1)), 250)
        self.assertEqual(self.C.rang_au(a, dt.datetime(2026, 10, 21, 9)), 180)        # photo TennisApi de la veille
        self.assertIsNone(self.C.rang_au(a, dt.date(2026, 5, 1)))
        self.assertIsNone(self.C.rang_au(CL.E.cle('Zed Zo'), dt.date(2026, 10, 1)))

    def test_export(self):
        p = os.path.join(self.d.name, 'ex.json')
        self.assertEqual(CL.exporter(CL.charger(os.path.join(self.d.name, 'sack')), p), 2)   # l'archive seule
        os.makedirs(os.path.join(self.d.name, 'simulateur'))
        os.replace(p, os.path.join(self.d.name, 'simulateur', 'classements_sackmann.json'))
        C2 = CL.charger(None, self.d.name)                                              # comme les pronostics du jour
        self.assertEqual(C2.rang_au(CL.E.cle('Cora Dix'), dt.date(2026, 10, 1)), 40)
        self.assertEqual(C2.rang_au(CL.E.cle('Ana Bel'), dt.date(2026, 10, 22)), 180)

    def test_niveau(self):
        self.assertEqual(CL.niveau_inconnu(800, 40), 0.0)                         # joueur rodé : rien
        self.assertGreater(CL.niveau_inconnu(800, 0), 0.5)
        self.assertLess(CL.niveau_inconnu(30, 0), 0)
        self.assertEqual(CL.niveau_inconnu(None, 0), 0.5)


class TennisApi(unittest.TestCase):
    def test_lecture(self):
        doc = {'rankings': [{'team': {'name': 'Jannik Sinner'}, 'ranking': 1, 'points': 11000},
                            {'team': {'name': 'X'}, 'ranking': None}]}
        self.assertEqual(CT.lire_classement(doc), {CL.E.cle('Jannik Sinner'): [1, 11000, 'Jannik Sinner']})
        self.assertEqual(CT.lire_classement({'error': 1}), {})

    def test_feuille_rang_tete(self):
        e = {'id': 1, 'startTimestamp': 1792575000, 'homeTeam': {'name': 'A B', 'ranking': 140}, 'awayTeam': {'name': 'C D'},
             'homeTeamSeed': 'Q', 'time': {'period1': 2400, 'period2': 2700, 'currentPeriodStartTimestamp': 5},
             'status': {'type': 'finished'}, 'tournament': {}}
        f = FM.fiche(e, 'Challenger')
        self.assertEqual((f['home']['rang'], f['home']['tete_de_serie']), (140, 'Q'))
        self.assertNotIn('rang', f['away'])
        self.assertEqual(f['duree_min'], 85)


if __name__ == '__main__':
    unittest.main()
