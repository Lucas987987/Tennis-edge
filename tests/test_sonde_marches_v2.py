# -*- coding: utf-8 -*-
"""Livraison 114 (29/10/2026) : sonde des marchés (lecture seule), sans réseau."""
import os
import sys
import unittest
from unittest import mock

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
import sonde_marches_v2 as SM  # noqa: E402
import oddspapi_v5 as ov  # noqa: E402


class Sonde(unittest.TestCase):
    def test_oddspapi_inventaire(self):
        marches = [{'marketId': 121, 'marketName': 'Winner'}, {'marketId': 151, 'marketName': 'Total Games',
                   'outcomes': [{'outcomeName': 'Over'}, {'outcomeName': 'Under'}]}, {'marketId': 160, 'marketName': 'Total Aces'}]
        fx = [{'fixtureId': 'f1', 'participants': {'participant1Name': 'A Un', 'participant2Name': 'B Deux'},
               'tournament': {'tournamentName': 'ATP Basel'}, 'status': {'live': False}},
              {'fixtureId': 'f2', 'participants': {'participant1Name': 'C', 'participant2Name': 'D'},
               'tournament': {'tournamentName': 'ITF M15'}, 'status': {'live': False}}]
        cotes = [{'fixtureId': 'f1', 'odds': {'pinnacle': {'x': {'marketId': 151, 'handicap': 22.5, 'price': 1.9},
                                                            'y': {'marketId': 121, 'price': 1.5}}}}]

        def api_get(path, params=None, **_):
            return (marches, 200) if path == '/markets' else ([], 200)
        R = {}
        with mock.patch.object(ov, 'api_get', side_effect=api_get), \
                mock.patch.object(ov, 'fixtures_today', return_value=fx), \
                mock.patch.object(ov, 'odds_main_by_fixtures', return_value=cotes) as om:
            SM.sonde_oddspapi(R)
        self.assertEqual(om.call_args[0][0], ['f1'])                       # ITF écarté
        o = R['oddspapi']
        self.assertEqual(set(o['marches_interessants']), {'151', '160'})
        self.assertEqual(o['par_bookmaker']['pinnacle']['151'], {'nom': 'Total Games', 'matchs': 1, 'lignes': ['22.5']})
        self.assertIn('Total Games', SM.resume(R))

    def test_workflow_lecture_seule(self):
        with open(os.path.join(ICI, '..', '.github', 'workflows', 'sonde_marches_v2.yml'), encoding='utf-8') as f:
            w = f.read()
        self.assertIn('contents: read', w)
        self.assertNotIn('git push', w)
        self.assertIn('workflow_dispatch', w)
        self.assertNotIn('schedule', w)


if __name__ == '__main__':
    unittest.main()
