"""Paquet 494 : étape 2 du tennis de table — formules manche et match, Elo aux points, pente par ligue, règle de
jugement, rapport sans nom de joueur."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..'))
sys.path.insert(0, ICI)
import elo_tt as ET  # noqa: E402
import etude_etape2_tt as E2  # noqa: E402
from test_elo_tt import ecrire_monde  # noqa: E402


class Formules(unittest.TestCase):
    def test_manche_et_match(self):
        self.assertAlmostEqual(E2.p_manche(0.5), 0.5)
        self.assertAlmostEqual(E2.p_manche(0.55), 0.6868, places=3)
        self.assertAlmostEqual(E2.p_match(0.6, 3), 0.68256, places=4)
        self.assertAlmostEqual(sum(E2.scores_manches(0.62, 4).values()), 1.0)
        self.assertAlmostEqual(E2.p_match_de_q(0.55, 3), E2.p_match(E2.p_manche(0.55), 3), places=4)
        self.assertGreater(E2.p_match(0.6, 4), E2.p_match(0.6, 3))     # plus long : le meilleur gagne plus souvent


class Etude(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        ecrire_monde(cls.dir, jours=700)
        cls.M = ET.matchs(cls.dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir)

    def test_format_et_score(self):
        m = self.M[0]
        self.assertEqual(m[7], 3)
        self.assertEqual(max(m[8]), 3)

    def test_etude(self):
        lignes = []
        rep = E2.etudier(self.M, [400, 0.6, 0.5, 20], lignes.append)
        self.assertEqual(set(rep['A_pente_par_ligue']), {'Czech Republic', 'Poland'})
        b = rep['B_simulation_aux_points']
        self.assertIn(tuple(b['reglage_appris']), E2.GRILLE_POINTS)
        self.assertEqual(b['toutes_ligues']['matchs'], rep['jugement'])
        self.assertTrue(rep['bilan_par_ligue']['Poland']['produit'])
        self.assertFalse(rep['bilan_par_ligue']['Czech Republic']['produit'])
        self.assertIn('score_le_plus_probable_juste_pct', b['score_en_manches']['Poland'])
        self.assertNotIn('Joueur', json.dumps(rep) + '\n'.join(lignes))
        # monde factice tiré point par point : la simulation aux points doit au moins égaler l'Elo
        self.assertGreater(b['toutes_ligues']['gain'], -0.002)

    def test_regle(self):
        self.assertTrue(E2.passe({'matchs': 1000, 'gain': 0.002, 'erreur_type': 0.0005}, True))
        self.assertFalse(E2.passe({'matchs': 999, 'gain': 0.002, 'erreur_type': 0.0005}, True))
        self.assertFalse(E2.passe({'matchs': 5000, 'gain': 0.002, 'erreur_type': 0.0015}, True))
        self.assertFalse(E2.passe({'matchs': 5000, 'gain': 0.002, 'erreur_type': 0.0005}, False))


if __name__ == '__main__':
    unittest.main()
