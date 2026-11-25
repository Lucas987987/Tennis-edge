"""Paquet 324 (21/11/2026, Lucas : « retravailler les gestes ») — coups plus amples, contact inchangé."""
import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')


def cles(nom):
    ligne = re.search(r'\n    ' + nom + r': (\[\[.*?\]\]),\n', HTML).group(1)
    return eval(re.sub(r'(?<![\d.])(-?)\.(\d)', r'\g<1>0.\2', ligne))


class Gestes(unittest.TestCase):
    def test_torsion_a_la_preparation(self):
        for nom in ('cd', 'rv'):
            K = cles(nom)
            for i in (1, 2):                                   # u = 0,3 et 0,47 : épaules plus tournées que le bassin
                self.assertGreater(abs(K[i][1][1]), 1.2, nom)
                self.assertGreater(abs(K[i][1][1]) - abs(K[i][2][1]), 0.6, nom)
                self.assertGreaterEqual(K[i][3], 0.2, nom)     # genoux fléchis

    def test_contact_inchange(self):
        self.assertEqual(cles('cd')[3], [.55, [.2, -.3, 0], [0, .2, 0], .12, -.02, .06, [-.245, -.042, -.483], 1.077, [-1.29, 0, 1.116], [.566, 1.601, .09], 2.063, [-.42, -.05], [.22, .2]])
        self.assertEqual(cles('sv')[4][0], .625)

    def test_version(self):
        self.assertRegex(HTML, r"const VERSION_3D = 'v(32[4-9]|4[0-9][0-9])';")


if __name__ == '__main__':
    unittest.main()
