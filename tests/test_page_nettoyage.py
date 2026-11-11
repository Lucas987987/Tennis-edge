"""Nettoyage de la page de l'algo (11/11/2026, paquet 219)."""
import unittest
from pathlib import Path

PAGE = (Path(__file__).resolve().parents[1] / 'algo' / 'index.html').read_text(encoding='utf-8')


class PageNettoyee(unittest.TestCase):
    def test_pas_d_etiquette_incertitude(self):
        self.assertNotIn('rendIncertitude', PAGE)
        self.assertNotIn('te-uncertainty', PAGE)

    def test_fourchette_toujours_affichee(self):
        self.assertIn('m.fourchette', PAGE)

    def test_un_seul_bouton_arena(self):
        self.assertEqual(PAGE.count('🏟️ Arena</a>'), 1)
        self.assertNotIn('position:fixed;bottom:18px', PAGE)

    def test_plus_de_code_3d(self):
        for mot in ('babylon', 'lv-3d-', 'lv-v9-', 'lv-v6-', 'Vue immersive'):
            self.assertNotIn(mot, PAGE)

    def test_analyse_detaillee_bilingue(self):
        self.assertIn("'Detailed analysis'", PAGE)
        self.assertIn('8 times out of 10', PAGE)


if __name__ == '__main__':
    unittest.main()
