"""Badminton, étape 4 (sans la série hors circuits) — données factices."""
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
import etude_etape2_badminton as E2  # noqa: E402
import etude_etape4_badminton as S  # noqa: E402
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

    def test_regle_figee(self):
        self.assertEqual(S.DEPART_REGLAGE, (400, 0.3, 1.0, 32))
        self.assertEqual(len(S.GRILLE_F1), 120)
        self.assertEqual(S.GRILLE_F3, [50, 100, 150, 200])
        self.assertEqual((S.MARGE, S.MIN_JUGES), (0.001, 1000))

    def test_meme_elo_que_l_etape_3(self):
        self.assertEqual(S.rejouer(self.M, 400, 0.3, 1.0, 32), E2.rejouer(self.M, 400, 0.3, 1.0, 32, joueurs=True))
        self.assertNotEqual(S.rejouer(self.M, 400, 0.3, 1.0, 32, delta=100), S.rejouer(self.M, 400, 0.3, 1.0, 32))

    def test_etude_sans_hors_circuit(self):
        ancienne = S.GRILLE_F1
        S.GRILLE_F1 = [(400, 0.3, 1.0, 32), (800, 0.5, 0.9, 24)]
        try:
            lignes = []
            rep = S.etudier(self.M, self.comptes, lignes.append)
        finally:
            S.GRILLE_F1 = ancienne
        self.assertEqual(rep['donnees']['hors_circuit_retires'], 200)
        self.assertEqual(set(rep['comparaisons']), {'F1', 'F2', 'F3'})
        self.assertIn(rep['decision'], ('preparer_le_produit', 's_arreter_et_regarder_pourquoi'))
        self.assertEqual(rep['decision'] == 'preparer_le_produit', rep['verdict'] == 'l_elo_tient')
        texte = json.dumps(rep, ensure_ascii=False) + '\n'.join(lignes)
        self.assertNotIn('Joueur', texte)
        for interdit in ('cote', 'value', 'marché'):
            self.assertNotIn(interdit, texte.lower())


if __name__ == '__main__':
    unittest.main()
