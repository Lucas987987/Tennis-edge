"""526 : badminton — étape 5 (l'Elo après une surprise) et étude du score en manches (données factices)."""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..'))
sys.path.insert(0, ICI)
import elo_badminton as EB  # noqa: E402
import etude_etape4_badminton as S4  # noqa: E402
import etude_etape5_badminton as S5  # noqa: E402
import etude_score_badminton as SC  # noqa: E402
from test_etude_elo_badminton import ecrire_monde  # noqa: E402


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        ecrire_monde(cls.dir, jours=500, debut=dt.date(2022, 6, 1))
        cls.M, cls.comptes = EB.lire(cls.dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir)

    def test_manches_lues(self):
        self.assertTrue(all(m[10] in (2, 3) for m in self.M))

    def test_regles_figees(self):
        self.assertEqual(S5.GRILLE_M, [0.5, 0.6, 0.7, 0.8, 0.9])
        self.assertEqual((SC.POIDS, SC.MARGE, SC.MIN_JUGES, SC.ECART_MAX), (50, 0.001, 1000, 3.0))

    def test_m1_redonne_l_etape_4(self):
        self.assertEqual(S5.rejouer(self.M, *S5.DEPART_REGLAGE), S4.rejouer(self.M, *S4.DEPART_REGLAGE))

    def test_s0(self):
        for p in (0.5, 0.63, 0.9):
            d = SC.s0(p)
            self.assertAlmostEqual(sum(d.values()), 1.0, places=9)
            self.assertAlmostEqual(d['h20'] + d['h21'], p, places=6)
        T_ = {('simple messieurs', SC.tranche(0.7)): [100, 50, 30.0]}
        d = SC.s1(0.7, 'simple messieurs', T_)
        self.assertAlmostEqual(sum(d.values()), 1.0, places=9)
        self.assertAlmostEqual(d['h20'] + d['h21'], 0.7, delta=0.03)

    def test_etudes(self):
        for mod in (S5, SC):
            L = []
            rep = mod.etudier(self.M, self.comptes, L.append)
            self.assertIn('verdict', rep)
            texte = json.dumps(rep, ensure_ascii=False) + '\n'.join(L)
            self.assertNotIn('Joueur', texte)
            for interdit in ('cote', 'value', 'marché'):
                self.assertNotIn(interdit, texte.lower())


if __name__ == '__main__':
    unittest.main()
