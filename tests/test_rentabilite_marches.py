"""Étude « l'algorithme sur Kalshi / Polymarket » (23/10/2026) : prix pris 60 min avant au plus tard, frais,
seuil, un côté par match, CLV contre la clôture Pinnacle, témoin Pinnacle."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import etude_rentabilite_marches as ER  # noqa: E402

D = dt.datetime(2026, 10, 20, 12, 0, tzinfo=dt.timezone.utc)
H = lambda h: D - dt.timedelta(hours=h)


class Regle(unittest.TestCase):
    def setUp(self):
        self.M = {'u1': {'debut': D, 'pin': [(H(5), 0.55), (H(0.5), 0.60)]}}
        self.prix = {('kalshi', 'u1'): {'home': [(H(3), 0.50, 0.495), (H(0.5), 0.40, 0.395)],
                                        'away': [(H(3), 0.52, 0.515)]}}

    def test_pari(self):
        P = ER.paris(self.prix, self.M, {'u1': (0.62, 'home')}, 0.05, 'historique')
        self.assertEqual(len(P), 1)
        p = P[0]
        self.assertEqual((p['cote'], p['ask']), ('home', 0.50))            # le prix de 30 min avant n'est pas pris
        self.assertAlmostEqual(p['ecart'], 0.62 - 0.50 - 0.07 * 0.25, places=4)
        self.assertTrue(p['gagne'])
        self.assertAlmostEqual(p['roi'], (1 - 0.5175) / 0.5175, places=3)
        self.assertAlmostEqual(p['clv_pinnacle'], 0.10, places=4)          # clôture Pinnacle 0,60 contre 0,50

    def test_sous_le_seuil_et_frais(self):
        self.assertEqual(ER.paris(self.prix, self.M, {'u1': (0.56, 'home')}, 0.05, 'historique'), [])
        P = ER.paris(self.prix, self.M, {'u1': (0.30, 'away')}, 0.05, 'historique')   # away : 0,70 contre 0,52
        self.assertEqual(P[0]['cote'], 'away')
        self.assertFalse(ER.paris(self.prix, self.M, {'u1': (0.62, 'home', H(0.5))}, 0.05, 'direct'))  # pronostiqué trop tard

    def test_temoin(self):
        P = ER.paris(self.prix, self.M, {'u1': (0.10, 'home')}, 0.03, 'historique', temoin=True)
        self.assertEqual(P[0]['cote'], 'home')                              # Pinnacle 0,55 à H−1 contre 0,50

    def test_bilan(self):
        self.assertIn('ne pas conclure', ER.bilan([{'roi': 0.1, 'clv_pinnacle': 0.02, 'gagne': True}] * 5)['verdict'])
        b = ER.bilan([{'roi': 0.1, 'clv_pinnacle': 0.02 + 0.001 * k, 'gagne': True} for k in range(40)])
        self.assertIn('bat la clôture', b['verdict'])


if __name__ == '__main__':
    unittest.main()
