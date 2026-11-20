# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 240) — le duel service ↔ retour sur la même échelle que les cartes des joueurs."""
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import cartes_joueurs as CJ  # noqa: E402


def carte(ser, ret, vs, vr):
    return {'note': 75, 'attributs': {'ser': ser, 'ret': ret, 'ace': 50, 'pre': 50, 'df': 50, 'for': 50},
            'valeurs': {'ser': vs, 'ret': vr, 'ace': 8.0, 'pre': 62.0, 'df': 7.0}, 'balles': 4000}


class Duel(unittest.TestCase):
    def test_le_duel_reprend_les_attributs_des_cartes(self):
        d = CJ.duel_des_cartes([carte(96, 99, 66.1, 40.2), carte(97, 87, 67.0, 38.5)], 'ATP', 'Hard')
        self.assertEqual((d['joueurs'][0]['serv_indice'], d['joueurs'][1]['ret_indice']), (96, 87))
        self.assertEqual(d['duels'], [{'service': 0, 'ecart': 96 - 87}, {'service': 1, 'ecart': 97 - 99}])
        self.assertEqual((d['source'], d['groupe'], d['joueurs'][0]['serv_pct']), ('cartes', 'hommes', 66.1))
        self.assertTrue(d['descriptif_seulement'])
        self.assertEqual(CJ.duel_des_cartes([carte(60, 60, 60.0, 40.0), carte(60, 60, 60.0, 40.0)], 'WTA', 'Clay')['groupe'], 'femmes')

    def test_sans_attributs_pas_de_duel_tire_des_cartes(self):
        self.assertIsNone(CJ.duel_des_cartes([carte(96, 99, 66.1, 40.2), {'note': 70}], 'ATP', 'Hard'))
        self.assertIsNone(CJ.duel_des_cartes([carte(96, 99, 66.1, 40.2)], 'ATP', 'Hard'))
        self.assertIsNone(CJ.duel_des_cartes(None, 'ATP', 'Hard'))

    def test_le_site_et_le_post_disent_la_meme_echelle(self):
        with open(os.path.join(RACINE, 'algo', 'index.html'), encoding='utf-8') as f:
            page = f.read()
        self.assertIn("d.source==='cartes' ? d.groupe : null", page)
        self.assertIn("mêmes chiffres que les cartes des joueurs", page)
        self.assertEqual(page.count("la même échelle que les cartes des joueurs"), 1)
        self.assertEqual(page.count("the same scale as the player cards"), 1)
        with open(os.path.join(RACINE, 'simulateur', 'cartes_joueurs.py'), encoding='utf-8') as f:
            self.assertIn("x['duel'] = du", f.read())


if __name__ == '__main__':
    unittest.main()
