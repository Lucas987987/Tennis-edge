"""Badminton, étape 3 (pente glissante, grille de la marge élargie) — données factices."""
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
import etude_etape3_badminton as S  # noqa: E402
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
        self.assertEqual(S.DEPART_REGLAGE, (200, 0.2, 0.75, 32))
        self.assertEqual(len(S.GRILLE_D1), 144)
        self.assertEqual((S.FENETRE_J, S.MIN_FENETRE, S.MARGE, S.MIN_JUGES), (365, 1000, 0.001, 1000))

    def test_pente_glissante_passe_seulement(self):
        Y = [m[5] for m in self.M]
        P = [0.5 + (0.3 if y else -0.3) * (1 if dt.date.fromisoformat(m[1]) >= dt.date(2023, 3, 1) else 0)
             for m, y in zip(self.M, Y)]
        b = S.pentes_glissantes(P, Y, self.M)
        self.assertEqual(b['2022-06'], 1.0)                   # aucun passé : β = 1
        self.assertEqual(b['2023-03'], b['2023-02'])          # le mois en cours n'entre pas dans son propre β
        bp = S.pentes_glissantes(P, Y, self.M, par_epreuve=True)
        self.assertEqual(set(bp['2023-06']), set(EB.EPREUVES))

    def test_etude(self):
        ancienne = S.GRILLE_D1
        S.GRILLE_D1 = [(200, 0.2, 0.75, 32), (400, 0.3, 1.0, 32)]
        try:
            lignes = []
            rep = S.etudier(self.M, self.comptes, lignes.append)
        finally:
            S.GRILLE_D1 = ancienne
        self.assertIn(rep['verdict'], ('l_elo_tient', 'l_elo_ne_tient_pas'))
        self.assertEqual(set(rep['comparaisons']), {'D1', 'D2a', 'D2b'})
        self.assertEqual(rep['jugement_toutes_epreuves']['matchs'], rep['periodes']['jugement'])
        texte = json.dumps(rep, ensure_ascii=False) + '\n'.join(lignes)
        self.assertNotIn('Joueur', texte)
        for interdit in ('cote', 'value', 'marché'):
            self.assertNotIn(interdit, texte.lower())


if __name__ == '__main__':
    unittest.main()
