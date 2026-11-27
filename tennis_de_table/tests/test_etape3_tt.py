"""Paquet 496 : étape 3 du tennis de table — ancrage exact sur le %, catégories de scores vues du favori, étalonnage,
recalage par table, règle de jugement, rapport sans nom."""
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
import etude_etape3_tt as E3  # noqa: E402
from test_elo_tt import ecrire_monde  # noqa: E402


class Ancrage(unittest.TestCase):
    def test_q_retrouve_le_pourcentage(self):
        for n in (3, 4):
            for p in (0.5, 0.62, 0.8, 0.93):
                q = E3.q_ancre(p, n)
                self.assertAlmostEqual(E2.p_match(E2.p_manche(q), n), p, places=3)
        D = E3.distribution(0.7, 3)
        self.assertAlmostEqual(sum(D.values()), 1.0)
        self.assertAlmostEqual(sum(v for k, v in D.items() if k[0] == 'F'), 0.7, places=3)
        self.assertEqual(len(E3.categories(4)), 8)

    def test_categorie_reelle(self):
        m = (0, '', 'X', 1, 2, 1, 0.5, 3, (3, 1))
        self.assertEqual(E3.categorie_reelle(m, True, 3), ('F', 1))
        self.assertEqual(E3.categorie_reelle(m, False, 3), ('O', 1))


class Etude(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        ecrire_monde(cls.dir, jours=700)
        cls.M = ET.matchs(cls.dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir)

    def test_etude(self):
        lignes = []
        rep = E3.etudier(self.M, [400, 0.6, 0.5, 20], {'Poland': 1.1}, lignes.append)
        po = rep['par_ligue']['Poland']
        self.assertTrue(po['produit'])
        e = po['Q1_etalonnage']
        self.assertIn('3_manches_gagnantes', e['par_format'])
        sc = e['par_format']['3_manches_gagnantes']['scores']
        self.assertEqual(len(sc), 6)
        self.assertAlmostEqual(sum(x['reel_pct'] for x in sc.values()), 100, delta=0.5)
        self.assertAlmostEqual(sum(x['annonce_pct'] for x in sc.values()), 100, delta=0.5)
        self.assertIn('retenu', po['Q2_recalage'])
        self.assertNotIn('Joueur', json.dumps(rep) + '\n'.join(lignes))

    def test_pas_assez(self):
        self.assertEqual(E3.etudier(self.M[:300], [400, 0.6, 0.5, 20], {}, lambda x: None)['verdict'], 'donnees_insuffisantes')


if __name__ == '__main__':
    unittest.main()
