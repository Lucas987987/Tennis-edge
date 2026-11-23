"""Paquet 374 — favori le moins documenté (Challenger 500–1 500) en service : part de l'Elo ramenée vers 50 %."""
import json
import math
import os
import sys
import unittest

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import apres_match as AM  # noqa: E402
import elo as E  # noqa: E402
import fantomes_circuits as FC  # noqa: E402
import pronostics_du_jour as PJ  # noqa: E402


class TestFavoriMoinsDocumente(unittest.TestCase):
    def setUp(self):
        self._avant = (PJ.FAVORI_MOINS_DOC, PJ.BALLES_CUMULEES, PJ.COMBINAISON, PJ.SIGNAUX_CIRCUIT)
        PJ.FAVORI_MOINS_DOC = {'CH': {'pente': 0.775, 'de': 500, 'a': 1500}}
        PJ.BALLES_CUMULEES = {E.cle('Peu Vu'): 900, E.cle('Tres Vu'): 8000, E.cle('Inconnu Total'): 100}
        PJ.COMBINAISON = {'elo': 0.6}
        PJ.SIGNAUX_CIRCUIT = {'favori_moins_documente': ['CH']}

    def tearDown(self):
        PJ.FAVORI_MOINS_DOC, PJ.BALLES_CUMULEES, PJ.COMBINAISON, PJ.SIGNAUX_CIRCUIT = self._avant

    def test_favori_moins_documente_ramene_vers_50(self):
        f = PJ.controle_favori_moins_doc(0.68, 0.70, 'CH', 'Peu Vu', 'Tres Vu')
        lg = math.log(0.70 / 0.30)
        self.assertAlmostEqual(f['decalage'], round(0.6 * (0.775 - 1) * lg, 4), places=4)
        self.assertLess(f['p_home'], 0.68)
        self.assertEqual(f['balles'], [900, 8000])
        # symétrique : favori à l'extérieur
        g = PJ.controle_favori_moins_doc(0.32, 0.30, 'CH', 'Tres Vu', 'Peu Vu')
        self.assertGreater(g['p_home'], 0.32)

    def test_hors_case(self):
        self.assertIsNone(PJ.controle_favori_moins_doc(0.68, 0.70, 'CH', 'Tres Vu', 'Peu Vu'))     # favori le plus vu
        self.assertIsNone(PJ.controle_favori_moins_doc(0.68, 0.70, 'ATP', 'Peu Vu', 'Tres Vu'))    # autre circuit
        self.assertIsNone(PJ.controle_favori_moins_doc(0.68, 0.70, 'CH', 'Inconnu Total', 'Tres Vu'))  # sous 500
        PJ.BALLES_CUMULEES = None
        self.assertIsNone(PJ.controle_favori_moins_doc(0.68, 0.70, 'CH', 'Peu Vu', 'Tres Vu'))

    def test_signal_branche(self):
        f = PJ.controle_favori_moins_doc(0.68, 0.70, 'CH', 'Peu Vu', 'Tres Vu')
        self.assertEqual(PJ.signaux_du_match('CH', 0.68, None, None, None, None, fmd_ctl=f),
                         {'favori_moins_documente': f['decalage']})
        self.assertIn('favori_moins_documente', FC.SIGNAUX)
        self.assertIn(('favori_moins_documente', 'CH'), FC.directs(RACINE))
        self.assertNotIn(('favori_moins_documente', 'ATP'), FC.directs(RACINE))

    def test_config_livree(self):
        with open(os.path.join(RACINE, 'simulateur', 'favori_moins_documente.json'), encoding='utf-8') as f_:
            d = json.load(f_)
        self.assertEqual(set(d['pentes']), {'CH'})
        self.assertEqual((d['pentes']['CH']['de'], d['pentes']['CH']['a']), (500, 1500))
        self.assertGreaterEqual(d['pentes']['CH']['matchs_juges'], 1000)

    def test_fantome_apres_match(self):
        self.assertIn('fantome_favori_moins_documente', open(os.path.join(RACINE, 'simulateur', 'apres_match.py'),
                                                             encoding='utf-8').read())


if __name__ == '__main__':
    unittest.main()
