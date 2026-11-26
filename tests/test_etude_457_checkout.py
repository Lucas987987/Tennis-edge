"""Paquet 485 : l'étude 457 (styles de jeu approfondie) a besoin de Tennis_Edge_Lab/books.py (import de
backtest_pronostic → nos_resultats) ; le run du 26/11 était rouge sans lui. Même liste que l'étude 456.
Lecture du texte du workflow (le module yaml n'est pas installé pour les tests)."""
import os
import unittest

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def chemins(nom):
    lignes = open(os.path.join(R, '.github', 'workflows', nom), encoding='utf-8').read().splitlines()
    out, dedans = set(), False
    for l in lignes:
        if l.strip() == 'sparse-checkout: |':
            dedans = True
            continue
        if dedans:
            if l.strip().startswith('/'):
                out.add(l.strip())
            else:
                break
    return out


class Checkout(unittest.TestCase):
    def test_books_present(self):
        a = chemins('etude_styles_approfondie.yml')
        self.assertIn('/Tennis_Edge_Lab/books.py', a)
        self.assertTrue(chemins('etude_irregularite.yml') <= a)
        self.assertGreater(len(chemins('etude_irregularite.yml')), 5)


if __name__ == '__main__':
    unittest.main()
