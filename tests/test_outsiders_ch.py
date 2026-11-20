"""Paquet 274 : deux signaux d'outsider en Challenger (favori fatigué, outsider mieux classé) et leur retrait."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import pronostics_du_jour as P  # noqa: E402
import outsiders_ch as OC  # noqa: E402

DEBUT = dt.datetime(2026, 11, 18, 15, 0)
TS = DEBUT.replace(tzinfo=dt.timezone.utc).timestamp()


class Signaux(unittest.TestCase):
    def setUp(self):
        self.ancien = (P.OUTSIDERS_CH, P.DERNIERS_MATCHS, P.PROGRAMME)
        P.OUTSIDERS_CH = {'favori_fatigue': 0.1553, 'outsider_mieux_classe': 0.1559}
        P.DERNIERS_MATCHS = {'fav': [(TS - 86400, 'drummondville', 3)], 'out': [(TS - 86400, 'drummondville', 2)]}
        P.PROGRAMME = {('2026-11-18', 'fav', 'out'): {'home': 'fav', 'away': 'out', 'rangs_actuels': [150, 90]}}

    def tearDown(self):
        P.OUTSIDERS_CH, P.DERNIERS_MATCHS, P.PROGRAMME = self.ancien

    def test_les_deux_vers_l_outsider(self):
        d = P.signaux_outsiders('CH', 0.68, 'fav', 'out', 'ATP Challenger Drummondville', DEBUT)
        self.assertEqual(d, {'outsider_favori_fatigue': -0.1553, 'outsider_mieux_classe': -0.1559})   # home = favori
        d = P.signaux_outsiders('CH', 0.32, 'out', 'fav', 'ATP Challenger Drummondville', DEBUT)
        self.assertEqual(d, {'outsider_favori_fatigue': 0.1553, 'outsider_mieux_classe': 0.1559})     # home = outsider

    def test_hors_champ(self):
        self.assertEqual(P.signaux_outsiders('ATP', 0.68, 'fav', 'out', 'Drummondville', DEBUT), {})
        self.assertEqual(P.signaux_outsiders('CH', 0.90, 'fav', 'out', 'Drummondville', DEBUT), {})   # outsider à 10 %
        self.assertEqual(P.signaux_outsiders('CH', 0.52, 'fav', 'out', 'Drummondville', DEBUT), {})   # pas d'outsider net

    def test_fatigue_seulement_dans_ce_tournoi(self):
        P.DERNIERS_MATCHS = {'fav': [(TS - 86400, 'metz', 3)]}
        self.assertNotIn('outsider_favori_fatigue', P.signaux_outsiders('CH', 0.68, 'fav', 'out', 'ATP Challenger Drummondville', DEBUT))
        P.DERNIERS_MATCHS = {'fav': [(TS - 86400, 'drummondville', 3)], 'out': [(TS - 86400, 'drummondville', 3)]}
        self.assertNotIn('outsider_favori_fatigue', P.signaux_outsiders('CH', 0.68, 'fav', 'out', 'ATP Challenger Drummondville', DEBUT))
        P.DERNIERS_MATCHS = {'fav': [(TS - 86400, 'drummondville', 3)]}                 # premier match de l'outsider ici
        self.assertIn('outsider_favori_fatigue', P.signaux_outsiders('CH', 0.68, 'fav', 'out', 'ATP Challenger Drummondville', DEBUT))

    def test_classement_inconnu_ou_favori_mieux_classe(self):
        P.PROGRAMME = {('2026-11-18', 'fav', 'out'): {'home': 'fav', 'away': 'out', 'rangs_actuels': [90, 150]}}
        self.assertNotIn('outsider_mieux_classe', P.signaux_outsiders('CH', 0.68, 'fav', 'out', 'Drummondville', DEBUT))
        P.PROGRAMME = {}
        self.assertNotIn('outsider_mieux_classe', P.signaux_outsiders('CH', 0.68, 'fav', 'out', 'Drummondville', DEBUT))

    def test_fichier_en_place(self):
        self.assertEqual(P.charger_outsiders(str(RACINE)), {'favori_fatigue': 0.1553, 'outsider_mieux_classe': 0.1559})


class Retrait(unittest.TestCase):
    def _racine(self, d, n, gagne):
        os.makedirs(os.path.join(d, 'simulateur')); os.makedirs(os.path.join(d, 'Tennis_Edge_Lab', 'live'))
        json.dump({'signaux': {'outsider_mieux_classe': {'beta': .1559, 'retire': False}}},
                  open(os.path.join(d, 'simulateur', 'outsiders_ch.json'), 'w'))
        R = [{'circuit': 'CH', 'reel': {'gagnant': 'home' if gagne(k) else 'away', 'interrompu': None},
              'fiabilite': {'outsiders': {'decalages': {'outsider_mieux_classe': -0.1559}, 'p_home_avec': 0.62}}} for k in range(n)]
        json.dump({'matchs': R}, open(os.path.join(d, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), 'w'))

    def test_retire_si_le_favori_gagne_plus(self):
        with tempfile.TemporaryDirectory() as d:
            self._racine(d, 220, lambda k: k % 10 < 8)                   # le favori gagne 80 % : le décalage fait pire
            r, nouveau = OC.suivi(d)
            self.assertEqual(r['outsider_mieux_classe']['verdict'], 'retiré')
            self.assertTrue(nouveau['signaux']['outsider_mieux_classe']['retire'])

    def test_garde_et_trop_tot(self):
        with tempfile.TemporaryDirectory() as d:
            self._racine(d, 220, lambda k: k % 100 < 58)                 # le favori gagne 58 % : le décalage aide
            self.assertEqual(OC.suivi(d)[0]['outsider_mieux_classe']['verdict'], 'gardé')
        with tempfile.TemporaryDirectory() as d:
            self._racine(d, 150, lambda k: k % 10 < 8)
            self.assertEqual(OC.suivi(d)[0]['outsider_mieux_classe']['verdict'], 'trop tôt')

    def test_libelles_du_site(self):
        html = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
        self.assertIn("outsider_favori_fatigue: L==='fr'?", html)
        self.assertIn("outsider_mieux_classe: L==='fr'?", html)


if __name__ == '__main__':
    unittest.main()
