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
