"""26/11/2026 (paquet 475) : grille avant l'ouverture — mois 19,99 €, fondateurs 9,99 € à vie ; prix visibles de tous
dans la section Plus, sans « −50 % » ni prix barré (l'offre fondateurs est une offre à part)."""
import os
import re
import unittest

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


class Prix(unittest.TestCase):
    def test_grille_serveur(self):
        v = open(os.path.join(R, 'workers', 'algo', 'ventes.js'), encoding='utf-8').read()
        self.assertIn('TARIFS = Object.freeze({ semaine: 5.99, mois: 19.99, trimestre: 49.99, annee: 169.99 })', v)
        self.assertIn('PRIX_FONDATEUR = 9.99', v)

    def test_page(self):
        p = open(os.path.join(R, 'algo', 'index.html'), encoding='utf-8').read()
        self.assertIn('id="plus-prix"', p)
        bloc = p[p.index('function majPrixPlus()'):p.index('function majPrixPlus()') + 1500]
        self.assertIn('TARIFS_SITE', bloc)                 # jamais de prix écrit en dur pour la grille
        for interdit in ('50 %', '50%', '<s>', 'line-through', '14,99', '19,99'):
            self.assertNotIn(interdit, bloc)
        self.assertNotIn('14,99', p)


if __name__ == '__main__':
    unittest.main()
