# -*- coding: utf-8 -*-
"""Livraison 111 (29/10/2026) : bouton « Image pour X » (duel des styles) sur la carte de match."""
import os
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))


class ImageX(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ICI, '..', 'algo', 'index.html'), encoding='utf-8') as f:
            self.h = f.read()

    def test_libelles_fr_en(self):
        for k in ('x_bouton:', 'x_attendu:', 'x_faible:', 'x_pied:', 'x_derniers:'):
            self.assertEqual(self.h.count(k), 2, k)

    def test_sans_adresse_ni_nom_de_site(self):
        a = self.h.index('async function imageX(m)')
        b = self.h.index("document.addEventListener('click', e=>{", a)
        code = self.h[a:b].lower()
        for interdit in ('workers.dev', 'github', 'tennis edge', 'tennis-edge', 'http'):
            self.assertNotIn(interdit, code, interdit)

    def test_couleur_selon_ecart_et_echantillon(self):
        self.assertIn('ec >= 5 ? C.ok : ec <= -5 ? C.ko : C.ink', self.h)
        self.assertIn('b.n < 30', self.h)


if __name__ == '__main__':
    unittest.main()


class ImageXEcart(unittest.TestCase):
    """Paquet 239 : encadré « l'écart à l'attendu » et duel équilibré dans le post."""
    def setUp(self):
        with open(os.path.join(ICI, '..', 'algo', 'index.html'), encoding='utf-8') as f:
            self.h = f.read()

    def test_encadre_et_pied_fr_en(self):
        for k in ('x_ex_t:', 'x_ex_txt:', 'x_ex_ex:', 'x_ex_sur:'):
            self.assertEqual(self.h.count(k), 2, k)
        self.assertEqual(self.h.count('Descriptif seulement : ces bilans ne changent pas le % de l’algo'), 1)
        self.assertEqual(self.h.count('Descriptive only: these records do not change the algo’s %'), 1)

    def test_hauteur_suit_le_texte(self):
        a = self.h.index('async function imageX(m)')
        b = self.h.index("document.addEventListener('click', e=>{", a)
        code = self.h[a:b]
        self.assertIn('let H = 1350', code)
        self.assertIn('H = Math.max(1350,', code)
        self.assertIn("t('x_ex_t')", code)

    def test_duel_equilibre_sous_10_points(self):
        a = self.h.index('// duel service / retour')
        b = self.h.index('// statistiques prédites et projections', a)
        code = self.h[a:b]
        self.assertIn('Math.abs(e) < 10 ? `⚖️ Duel équilibré', code)
        self.assertIn('avantages[0] >= 10 && avantages[1] <= -10', code)
        self.assertIn('avantages[0] <= -10 && avantages[1] >= 10', code)
