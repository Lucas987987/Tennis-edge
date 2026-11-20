"""Post X · analyse complète (11/11/2026, paquet 224) : bouton présent, règles de contenu."""
import re
import unittest
from pathlib import Path

PAGE = (Path(__file__).resolve().parents[1] / 'algo' / 'index.html').read_text(encoding='utf-8')


class AnalyseComplete(unittest.TestCase):
    def corps(self):
        i = PAGE.index('function analyseComplete(m, court_){')
        return PAGE[i:PAGE.index('\nfunction ouvrirPost(', i)]

    def test_bouton_et_branchement(self):
        self.assertIn('id="b-analyse-x"', PAGE)
        self.assertIn("ouvrirPost(m, 'analyse')", PAGE)

    def test_regles(self):
        c = self.corps().lower()
        for interdit in ('workers.dev', 'http', 'marché', 'value', 'pinnacle'):
            self.assertNotIn(interdit, c)
        self.assertIn('descriptif', c)
        self.assertNotIn('après le 1er set (chance', c)      # bloc retiré à la demande de Lucas


if __name__ == '__main__':
    unittest.main()
