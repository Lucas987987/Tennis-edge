# -*- coding: utf-8 -*-
"""11/11/2026 (paquet 230) — joueurs peu vus en Challenger : l'étude passe sur l'archive, échoue au contrôle « comme en
production » (résultats ITF hommes dans l'Elo) : rien n'entre en production."""
import datetime as dt
import glob
import json
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import etude_joueurs_peu_vus as EJ  # noqa: E402
import etude_outsiders as EO  # noqa: E402


class Etude(unittest.TestCase):
    def test_tranches(self):
        self.assertEqual([EJ.tranche(n) for n in (0, 9, 10, 29, 30, 99, 100, 5000)],
                         ['moins de 10', 'moins de 10', '10 à 29', '10 à 29', '30 à 99', '30 à 99', '100 et plus', '100 et plus'])

    def test_une_pente_par_tranche_apprise_avant_2023_jugee_apres(self):
        rnd, rows = random.Random(7), []
        for jour in (dt.date(2020, 5, 4), dt.date(2024, 5, 6)):
            for n_vus, vraie in ((5, 1.3), (50, 0.8)):
                for _ in range(6000):
                    z = rnd.gauss(0, 0.9)
                    rows.append((jour, n_vus, z if rnd.random() < EO._sg(vraie * z) else -z))
        d = EJ.etudier(rows)
        self.assertAlmostEqual(d['pentes']['moins de 10'], 1.3, delta=0.1)
        self.assertAlmostEqual(d['pentes']['30 à 99'], 0.8, delta=0.08)
        self.assertEqual(d['pentes']['100 et plus'], 1.0)                       # pas assez de matchs : pas de pente
        self.assertEqual(d['2023 → juin 2026']['matchs'], 12000)
        self.assertTrue(d['retenue'], d['raisons'])

    def test_l_etude_prend_l_elo_de_production_et_ecarte_les_equipes(self):
        with open(os.path.join(RACINE, 'simulateur', 'etude_joueurs_peu_vus.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn('E.de_production(racine)', src)
        self.assertNotRegex(src, r'\bElo\(\s*\)')
        self.assertIn("!= 'D'", src)
        self.assertEqual((EJ.MIN_JUGES, EJ.MARGE), (1000, 0.001))


class Rapport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RACINE, 'simulateur', 'rapport_joueurs_peu_vus.json'), encoding='utf-8') as f:
            cls.R = json.load(f)

    def test_rapport_public_avec_brier(self):
        txt = json.dumps(self.R, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'clôture', 'cote'):
            self.assertNotIn(mot, txt)
        self.assertIn('brier', self.R['2023 → juin 2026'])

    def test_le_controle_comme_en_production_est_dit_et_l_emporte(self):
        c = self.R['controle_production']
        self.assertLess(c['avec_itf_comme_la_production']['gain_des_pentes'], 0)
        self.assertGreater(c['sans_itf_comme_l_etude']['gain_des_pentes'], 0)
        self.assertFalse(self.R['en_production'])
        self.assertIn('ITF', self.R['limite'])

    def test_aucun_fichier_de_production_ne_lit_ces_pentes(self):
        for chemin in glob.glob(os.path.join(RACINE, 'simulateur', '*.py')):
            if os.path.basename(chemin).startswith('etude_'):
                continue
            with open(chemin, encoding='utf-8') as f:
                self.assertNotIn('joueurs_peu_vus', f.read(), chemin)


if __name__ == '__main__':
    unittest.main()
