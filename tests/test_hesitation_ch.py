"""Paquets 314–315 : zone d'hésitation en Challenger (classement, invitation, expérience) et leur retrait."""
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
        self.ancien = (P.HESITATION_CH, P.PROGRAMME, P.EXPERIENCE)
        P.HESITATION_CH = {'classement': 0.0847, 'invitation': -0.2563}
        P.EXPERIENCE = None
        P.PROGRAMME = {CLE: {'home': 'a', 'away': 'b', 'rangs_actuels': [100, 400], 'tetes': ['WC', None]}}

    def tearDown(self):
        P.HESITATION_CH, P.PROGRAMME, P.EXPERIENCE = self.ancien

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

    def test_experience(self):
        P.HESITATION_CH = {'experience': 0.0526}
        P.EXPERIENCE = {'a': 99, 'b': 9}
        d = P.signaux_hesitation('CH', 0.56, 'a', 'b', DEBUT)                      # a favori et plus expérimenté
        self.assertAlmostEqual(d['hesitation_experience'], 0.0526 * math.log(10))
        d = P.signaux_hesitation('CH', 0.44, 'a', 'b', DEBUT)                      # b favori, moins expérimenté : vers a
        self.assertAlmostEqual(d['hesitation_experience'], 0.0526 * math.log(10))
        P.EXPERIENCE = None
        self.assertEqual(P.signaux_hesitation('CH', 0.56, 'a', 'b', DEBUT), {})     # compteur absent : rien

    def test_compteur_archive_plus_feuilles(self):
        import gzip
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur')); os.makedirs(os.path.join(d, 'feuilles'))
            json.dump({'jusqu_au': '2026-06-01', 'n': {'a': 10}}, open(os.path.join(d, 'simulateur', 'experience_joueurs.json'), 'w'))
            F = [{'id': 1, 'vainqueur': 1, 'categorie': 'Challenger', 'home': {'nom': 'A'}, 'away': {'nom': 'B'}},
                 {'id': 1, 'vainqueur': 1, 'categorie': 'Challenger', 'home': {'nom': 'A'}, 'away': {'nom': 'B'}},   # doublon
                 {'id': 2, 'vainqueur': 2, 'categorie': 'ITF Men', 'home': {'nom': 'A'}, 'away': {'nom': 'B'}},      # ITF : non
                 {'id': 3, 'vainqueur': None, 'categorie': 'ATP', 'home': {'nom': 'A'}, 'away': {'nom': 'B'}}]       # pas fini
            with gzip.open(os.path.join(d, 'feuilles', '2026-07-01.jsonl.gz'), 'wt') as f:
                f.write(''.join(json.dumps(r) + '\n' for r in F))
            with gzip.open(os.path.join(d, 'feuilles', '2026-05-31.jsonl.gz'), 'wt') as f:     # avant : déjà dans l'archive
                f.write(json.dumps(F[0]) + '\n')
            n = P.charger_experience(d, lambda x: x.lower() if x else None)
            self.assertEqual(n, {'a': 11, 'b': 1})

    def test_fichier_en_place(self):
        self.assertEqual(P.charger_hesitation(str(RACINE)), {'classement': 0.0447, 'invitation': -0.202, 'experience': 0.0526})
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
        self.assertIn("hesitation_experience: L==='fr'?", html)
        self.assertIn('experience', OC.FICHIERS['hesitation_ch.json'])


if __name__ == '__main__':
    unittest.main()
