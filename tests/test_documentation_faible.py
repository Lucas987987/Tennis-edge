import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import fantomes_circuits as FC  # noqa: E402
import pronostics_du_jour as P  # noqa: E402


class TestDocumentation(unittest.TestCase):
    def setUp(self):
        self.av = (P.BALLES_CUMULEES, P.PENTES_DOCUMENTATION)
        P.BALLES_CUMULEES = {'alphabeta': 300, 'deltagamma': 4000, 'epsilonzeta': 6000}
        P.PENTES_DOCUMENTATION = {'CH': 1.8}

    def tearDown(self):
        P.BALLES_CUMULEES, P.PENTES_DOCUMENTATION = self.av

    def test_etire_sous_500_balles(self):
        r = P.controle_documentation(.60, 'CH', 'Alpha Beta', 'Gamma Delta')
        self.assertGreater(r['p_home'], .66)
        self.assertEqual(r['balles'], 300)

    def test_rien_sinon(self):
        self.assertIsNone(P.controle_documentation(.60, 'CH', 'Gamma Delta', 'Epsilon Zeta'))
        self.assertIsNone(P.controle_documentation(.60, 'ATP', 'Alpha Beta', 'Gamma Delta'))

    def test_adoption_directe(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            with open(os.path.join(d, 'simulateur', 'rapport_documentation.json'), 'w') as f:
                json.dump({'circuits': {'CH': {'adopte': True, 'pente': 1.8}, 'ATP': {'adopte': False}}}, f)
            self.assertEqual(FC.lire(d).get('documentation_faible'), ['CH'])


if __name__ == '__main__':
    unittest.main()
