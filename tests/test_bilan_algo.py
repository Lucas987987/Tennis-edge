"""Bilan hebdomadaire de l'algorithme (22/10/2026) : vainqueurs trouvés par version, erreurs, changements."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import bilan_algo as BA  # noqa: E402


class Bilan(unittest.TestCase):
    def test_message(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'Tennis_Edge_Lab', 'live'))
            m = lambda h, ok, p, sc=None: {'debut': '2026-10-20T14:00', 'home': h, 'away': 'X Y', 'tournoi': 'ATP Vienna',
                                           'reel': {'gagnant': 'home' if ok else 'away', 'score': sc},
                                           'premier': {'combinaison': {'vainqueur_juste': ok, 'proba_du_vainqueur': p, 'sets_justes': ok,
                                                                       'score_juste': False},
                                                       'stats': {'vainqueur_juste': ok, 'proba_du_vainqueur': p}}}
            json.dump({'matchs': [m('A B', True, 0.7), m('C D', False, 0.2, '4-6 3-6'), m('E F', True, 0.6)]},
                      open(os.path.join(d, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), 'w'))
            old = BA.ICI
            BA.ICI = d
            try:
                json.dump({'adoptes': ['forme_fatigue', 'styles']}, open(os.path.join(d, 'facteurs.json'), 'w'))
                json.dump({'combinaison': {'adopte': True, 'poids': {'elo': 0.75, 'simulation': 0.25}}},
                          open(os.path.join(d, 'choix_simulation.json'), 'w'))
                json.dump({'adoptes': ['forme_fatigue', 'blessure']}, open(os.path.join(d, 'bilan_algo_etat.json'), 'w'))
                t, etat = BA.construire(d, dt.datetime(2026, 10, 26, 3, 0))
            finally:
                BA.ICI = old
        self.assertIn('3 matchs joués', t)
        self.assertIn('Simulation + Elo : vainqueur 2/3 (67 %) · sets 2/3 · score exact 0/3', t)
        self.assertIn('C D annoncé à 80 %, battu (ATP Vienna, 4-6 3-6)', t)
        self.assertIn('+ styles · − blessure', t)
        self.assertIn("poids de la simulation 25 % (appris sur l'archive 2024–2026)", t)
        self.assertEqual(etat['adoptes'], ['forme_fatigue', 'styles'])


if __name__ == '__main__':
    unittest.main()
