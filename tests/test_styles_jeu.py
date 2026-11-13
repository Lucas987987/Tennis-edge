# -*- coding: utf-8 -*-
"""13/11/2026 (paquet 252) — styles de jeu d'après les coups (descriptif) et leur étude."""
import datetime as dt
import json
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
SIM = os.path.join(RACINE, 'simulateur')
sys.path.insert(0, SIM)
import styles_jeu as SJ  # noqa: E402


def sommes(**k):
    s = {'points_joues': 1000, 'montees': 80, 'montees_gagnees': 54, 'coup_droit': 50, 'revers': 30, 'amortis_joues': 20,
         'fautes_directes': 160}
    s.update(k)
    return s


class Classement(unittest.TestCase):
    def test_moyen_est_complet(self):
        self.assertEqual(SJ.classer(sommes(), sommes()), ['complet'])

    def test_seuils(self):
        m = sommes()
        self.assertEqual(SJ.classer(sommes(montees=120, montees_gagnees=90), m), ['joueur_de_filet'])
        self.assertEqual(SJ.classer(sommes(montees=120, montees_gagnees=60), m), ['complet'])   # monte mais y perd
        self.assertEqual(SJ.classer(sommes(coup_droit=65), m), ['attaquant_coup_droit'])
        self.assertEqual(SJ.classer(sommes(coup_droit=64), m), ['complet'])
        self.assertEqual(SJ.classer(sommes(fautes_directes=130), m), ['regulier'])

    def test_deux_etiquettes_au_plus_les_plus_marquees(self):
        st = SJ.classer(sommes(coup_droit=90, revers=40, amortis_joues=31, fautes_directes=120), sommes())
        self.assertEqual(len(st), 2)
        self.assertEqual(st[0], 'attaquant_coup_droit')                # 90/65 la plus marquée

    def test_style_fige_avant_la_date(self):
        j0 = dt.date(2025, 1, 1)
        L = [(j0 + dt.timedelta(days=7 * i), dict(sommes(), _g='m')) for i in range(12)]
        P = SJ.Profils({'Un Joueur': L}, lambda n: 'un')
        self.assertIsNone(P.style('un', j0 + dt.timedelta(days=7 * 9))[0])     # 9 matchs avant : pas de style
        self.assertEqual(P.style('un', j0 + dt.timedelta(days=7 * 12))[1], 12)


class Etude(unittest.TestCase):
    def test_rapport(self):
        r = json.load(open(os.path.join(SIM, 'rapport_styles_jeu.json'), encoding='utf-8'))
        self.assertEqual(r['statut'], 'etude')
        self.assertEqual(r['retenus'], [])
        t = json.dumps(r, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'cote', 'value'):
            self.assertNotIn(mot, t)


class Branchement(unittest.TestCase):
    def test_page_vitrine_workflow(self):
        s = open(os.path.join(RACINE, 'algo', 'index.html'), encoding='utf-8').read()
        self.assertIn('${rendStylesJeu(m)}', s)
        self.assertIn("joueur_de_toucher:{fr:'Joueur de toucher'", s)
        v = open(os.path.join(SIM, 'vitrine.py'), encoding='utf-8').read()
        self.assertIn("ligne['styles_jeu'] = b_", v)
        w = open(os.path.join(RACINE, '.github', 'workflows', 'pronostics_quotidien.yml'), encoding='utf-8').read()
        self.assertIn('python simulateur/styles_jeu.py /tmp/sackmann . /tmp/mcp', w)


if __name__ == '__main__':
    unittest.main()
