"""26/11/2026 (paquet 476) : favoris (joueurs et matchs) sur le compte, gratuit compris ; filtre « Mes favoris » ;
les matchs des favoris remontent ; aucun accès réservé n'est ouvert par un favori."""
import os
import unittest

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


class Favoris(unittest.TestCase):
    def test_page(self):
        p = open(os.path.join(R, 'algo', 'index.html'), encoding='utf-8').read()
        self.assertIn('id="fav-filtre"', p)
        self.assertIn("(!filtreFav || estFavMatch(m))", p)
        self.assertIn("apiCompte('favoris'", p)
        self.assertEqual(p.count("fav_filtre:"), 2)                    # français et anglais
        bloc = p[p.index('function etoile('):p.index('function matchsFiltres(){')]
        self.assertIn('if (!COMPTES_DISPO) return', bloc)              # pas d'étoile sans système de comptes
        self.assertNotIn('verrou', bloc)                               # un favori ne touche pas aux verrous

    def test_serveur(self):
        c = open(os.path.join(R, 'workers', 'algo', 'comptes.js'), encoding='utf-8').read()
        self.assertIn("if (p === 'favoris') return favoris(req, env, b);", c)
        self.assertIn("'demande', 'favoris', 'push'];", c)           # dans l'export des données (483 : + appareils)


if __name__ == '__main__':
    unittest.main()
