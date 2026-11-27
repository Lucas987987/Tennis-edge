"""Badminton, étape 2 (grille élargie, pente apprise, doubles au joueur) — données factices."""
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
import etude_etape2_badminton as S  # noqa: E402
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
        self.assertEqual(S.DEPART_REGLAGE, (200, 0.3, 0.25, 16))
        self.assertEqual(len(S.GRILLE_C1), 96)
        self.assertEqual(sorted({x[0] for x in S.GRILLE_C1}), [100, 200, 400, 800])
        self.assertEqual(sorted({x[1] for x in S.GRILLE_C1}), [0, 0.1, 0.2, 0.3])
        self.assertEqual((S.MARGE, S.MIN_JUGES), (0.001, 1000))

    def test_paires_lues(self):
        d = [m for m in self.M if m[2].startswith('double')]
        self.assertTrue(d and all(m[9] and len(m[9][0]) == 2 for m in d))
        self.assertTrue(all(m[9] is None for m in self.M if m[2].startswith('simple')))

    def test_meme_elo_que_l_etape_1(self):
        P1 = S.rejouer(self.M, 200, 0.3, 0.25, 16)
        P2 = EB.rejouer(self.M, a=200, c=0.3, w=0.25, s=16)
        self.assertEqual(P1, P2)
        P3 = S.rejouer(self.M, 200, 0.3, 0.25, 16, joueurs=True)
        self.assertEqual([p for p, m in zip(P1, self.M) if not m[9]], [p for p, m in zip(P3, self.M) if not m[9]])
        # un joueur change de partenaire : sa note le suit (au joueur), pas la nouvelle paire (entité neuve)
        M = [(0, '2023-01-01', 'double messieurs', 'p1', 'p2', 1, 0.6, False, 'nom', (('A', 'B'), ('C', 'D'))),
             (1, '2023-01-02', 'double messieurs', 'p3', 'p4', 1, 0.6, False, 'nom', (('A', 'E'), ('C', 'F')))]
        self.assertEqual(S.rejouer(M, 200, 0.3, 0, 16)[1], 0.5)
        self.assertGreater(S.rejouer(M, 200, 0.3, 0, 16, joueurs=True)[1], 0.5)

    def test_pente(self):
        P = [0.6, 0.7, 0.4]
        self.assertEqual(S.appliquer(P, None, self.M[:3]), P)
        Q = S.appliquer(P, 2.0, self.M[:3])
        self.assertAlmostEqual(Q[0], 1 / (1 + (0.4 / 0.6) ** 2))

    def test_etude(self):
        ancienne = S.GRILLE_C1
        S.GRILLE_C1 = [(200, 0.3, 0.25, 16), (400, 0.2, 0.5, 32)]
        try:
            lignes = []
            rep = S.etudier(self.M, self.comptes, lignes.append)
        finally:
            S.GRILLE_C1 = ancienne
        self.assertIn(rep['verdict'], ('l_elo_tient', 'l_elo_ne_tient_pas'))
        self.assertEqual(set(rep['comparaisons']), {'C1', 'C2a', 'C2b', 'C3'})
        self.assertEqual(list(rep['jugement_par_epreuve']), EB.EPREUVES)
        self.assertEqual(rep['jugement_toutes_epreuves']['matchs'], rep['periodes']['jugement'])
        self.assertIn('sans_hors_circuit_publie_sans_decider', rep)
        texte = json.dumps(rep, ensure_ascii=False) + '\n'.join(lignes)
        self.assertNotIn('Joueur', texte)
        for interdit in ('cote', 'value', 'marché'):
            self.assertNotIn(interdit, texte.lower())


if __name__ == '__main__':
    unittest.main()
