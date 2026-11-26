"""Paquet 484 (26/11/2026, Lucas) : le RIB n'apparaît jamais sur le site (seulement par e-mail, avec un bouton pour le
renvoyer) ; la petite icône des notifications est une balle blanche sur fond transparent."""
import os
import struct
import unittest

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
lire = lambda *p: open(os.path.join(R, *p), encoding='utf-8').read()


class Rib(unittest.TestCase):
    def test_jamais_de_coordonnees_sur_la_page(self):
        s = lire('algo', 'index.html')
        for mot in ('fd_pay_lignes', 'PAIEMENT.iban', 'IBAN :', 'IBAN:'):
            self.assertNotIn(mot, s)
        self.assertIn("apiCompte('rib', {})", s)
        c = lire('workers', 'algo', 'comptes.js')
        bloc = c.split('function paiementDe(u, env) {')[1].split('\n}\n')[0]
        self.assertIn('iban: null', bloc)
        self.assertNotIn('VIREMENT', bloc)


class Badge(unittest.TestCase):
    def test_badge_transparent(self):
        p = os.path.join(R, 'algo', 'badge-96.png')
        with open(p, 'rb') as f:
            tete = f.read(33)
        self.assertEqual(tete[:8], b'\x89PNG\r\n\x1a\n')
        w, h, prof, couleur = struct.unpack('>IIBB', tete[16:26])
        self.assertEqual((w, h, couleur), (96, 96, 6))              # RGBA : Android n'en garde que la forme
        self.assertIn("badge: 'badge-96.png'", lire('algo', 'sw.js'))
        self.assertIn("'/badge-96.png': 'badge-96.png'", lire('workers', 'algo', 'worker.js'))
        self.assertIn('algo/badge-96.png', lire('.github', 'workflows', 'pages.yml'))


if __name__ == '__main__':
    unittest.main()
