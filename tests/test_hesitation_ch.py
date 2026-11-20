"""Paquet 314 : zone d'hésitation en Challenger (classement, invitation) et leur retrait."""
import datetime as dt
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import pronostics_du_jour as P  # noqa: E402
import outsiders_ch as OC  # noqa: E402

DEBUT = dt.datetime(2026, 11, 21, 15, 0)
CLE = ('2026-11-21', 'a', 'b')


class Signaux(unittest.TestCase):
    def setUp(self):
        self.ancien = (P.HESITATION_CH, P.PROGRAMME)
        P.HESITATION_CH = {'classement': 0.0847, 'invitation': -0.2563}
        P.PROGRAMME = {CLE: {'home': 'a', 'away': 'b', 'rangs_actuels': [100, 400], 'tetes': ['WC', None]}}

    def tearDown(self):
        P.HESITATION_CH, P.PROGRAMME = self.ancien

    def test_favori_a_domicile(self):
        d = P.signaux_hesitation('CH', 0.56, 'a', 'b', DEBUT)
        self.assertAlmostEqual(d['hesitation_classement'], 0.0847 * 2.0)          # favori mieux classé : renforcé
        self.assertAlmostEqual(d['hesitation_invitation'], -0.2563)               # favori invité : affaibli

    def test_favori_a_l_exterieur(self):
        d = P.signaux_hesitation('CH', 0.44, 'a', 'b', DEBUT)                       # b est le favori
        self.assertAlmostEqual(d['hesitation_classement'], 0.0847 * 2.0)           # b moins bien classé : vers a (home)
        self.assertAlmostEqual(d['hesitation_invitation'], -0.2563)                # l'adversaire a est invité : vers b, le favori

    def test_hors_zone_et_hors_circuit(self):
        for c, p in (('CH', 0.65), ('CH', 0.35), ('CH', 0.5), ('ATP', 0.55), ('WTA', 0.55)):
            self.assertEqual(P.signaux_hesitation(c, p, 'a', 'b', DEBUT), {}, (c, p))

    def test_donnees_manquantes(self):
        P.PROGRAMME = {}
        self.assertEqual(P.signaux_hesitation('CH', 0.56, 'a', 'b', DEBUT), {})

    def test_classement_borne(self):
        P.PROGRAMME = {CLE: {'home': 'a', 'away': 'b', 'rangs_actuels': [1, 5000], 'tetes': [None, None]}}
        self.assertAlmostEqual(P.signaux_hesitation('CH', 0.56, 'a', 'b', DEBUT)['hesitation_classement'], 0.0847 * 4)

    def test_fichier_en_place(self):
        self.assertEqual(P.charger_hesitation(str(RACINE)), {'classement': 0.0847, 'invitation': -0.2563})
        src = (RACINE / 'simulateur' / 'pronostics_du_jour.py').read_text(encoding='utf-8')
        self.assertIn('HESITATION_CH = charger_hesitation(racine)', src)
        self.assertIn('so_ = dict(so_ or {}, **sz_)', src)                         # gardés pour la règle de retrait


class Retrait(unittest.TestCase):
    def _racine(self, d, n, gagne):
        os.makedirs(os.path.join(d, 'simulateur')); os.makedirs(os.path.join(d, 'Tennis_Edge_Lab', 'live'))
        json.dump({'signaux': {'classement': {'beta': .0847, 'retire': False}}},
                  open(os.path.join(d, 'simulateur', 'hesitation_ch.json'), 'w'))
        R = [{'circuit': 'CH', 'reel': {'gagnant': 'home' if gagne(k) else 'away', 'interrompu': None},
              'fiabilite': {'outsiders': {'decalages': {'hesitation_classement': 0.3}, 'p_home_avec': 0.62}}} for k in range(n)]
        json.dump({'matchs': R}, open(os.path.join(d, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), 'w'))

    def test_retire_ou_garde(self):
        with tempfile.TemporaryDirectory() as d:
            self._racine(d, 220, lambda k: k % 2 == 0)                  # 50 % : le renfort du favori fait pire
            r, nouveau = OC.suivi(d, 'hesitation_ch.json')
            self.assertEqual(r['classement']['verdict'], 'retiré')
            self.assertTrue(nouveau['signaux']['classement']['retire'])
        with tempfile.TemporaryDirectory() as d:
            self._racine(d, 220, lambda k: k % 100 < 62)                # 62 % : le renfort aide
            self.assertEqual(OC.suivi(d, 'hesitation_ch.json')[0]['classement']['verdict'], 'gardé')

    def test_suivi_hebdomadaire(self):
        self.assertIn('hesitation_ch.json', OC.FICHIERS)
        wf = (RACINE / '.github' / 'workflows' / 'a_ou_b.yml').read_text(encoding='utf-8')
        self.assertIn('simulateur/hesitation_ch.json', wf)
        html = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
        self.assertIn("hesitation_classement: L==='fr'?", html)


if __name__ == '__main__':
    unittest.main()
