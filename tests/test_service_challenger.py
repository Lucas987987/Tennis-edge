"""Paquet 336 — service en Challenger (étude, règle, application au seul Challenger) et sonde point par point."""
import json
import os
import sys
import tempfile
import unittest

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import etude_service_challenger as E  # noqa: E402
import match_simule as MS  # noqa: E402
import sonde_points_challenger as SP  # noqa: E402

C = {'f': 0.62, 'a': 0.08, 'd': 0.04, 'w1': 0.70, 'w2j': 0.52}


class Etude(unittest.TestCase):
    def test_delta_augmente_les_jeux_sans_changer_le_vainqueur(self):
        d0, a0, b0 = E.distribution(C, C, 0.6, 0.0)
        d1, a1, b1 = E.distribution(C, C, 0.6, 0.02)
        moy = lambda d: sum(k * v for k, v in d.items()) / sum(d.values())
        self.assertGreater(moy(d1), moy(d0))
        self.assertGreater(a1 + b1, a0 + b0)                      # les deux servent mieux
        import modele as MM
        self.assertAlmostEqual(MM.match_forme(a1, b1, 2, E.SIGMA)['victoire'], 0.6, places=3)   # réancré

    def test_log_loss_des_lignes(self):
        d = {18: 0.5, 22: 0.5}
        self.assertAlmostEqual(E.log_loss_lignes(d, 22), -sum(__import__('math').log(x) for x in (.5, .5, .5, .5, 1 - 1e-6, 1 - 1e-6)) / 6, places=5)

    def test_regle(self):
        ref = {'n': 1200, 'log_loss_lignes': 0.6000, 'ecart_pts_service': 5.0}
        mieux = {'n': 1200, 'log_loss_lignes': 0.5985, 'ecart_pts_service': 5.0}
        f0, f1 = {'n': 300, 'log_loss_lignes': 0.61, 'ecart_pts_service': 5.0}, {'n': 300, 'log_loss_lignes': 0.605, 'ecart_pts_service': 5.0}
        ok, _ = E.decider({}, {0.0: ref, 0.01: mieux}, {0.0: f0, 0.01: f1}, 0.01)
        self.assertTrue(ok)
        ok, r = E.decider({}, {0.0: ref, 0.01: dict(mieux, log_loss_lignes=0.5995)}, {0.0: f0, 0.01: f1}, 0.01)
        self.assertFalse(ok)                                       # gain 0,0005 < 0,001
        ok, r = E.decider({}, {0.0: ref, 0.01: mieux}, {0.0: f0, 0.01: dict(f1, log_loss_lignes=0.62)}, 0.01)
        self.assertFalse(ok)                                       # sens contraire sur les feuilles
        ok, r = E.decider({}, {0.0: dict(ref, n=500), 0.01: dict(mieux, n=500)}, {0.0: f0, 0.01: f1}, 0.01)
        self.assertFalse(ok)                                       # moins de 1 000 matchs
        self.assertFalse(E.decider({}, {}, {}, 0.0)[0])

    def test_reglage_seulement_en_challenger_et_jamais_sur_la_simulation_pure(self):
        rg = {'par_circuit': {'CH': {'jeux_delta': 0.01}}}
        self.assertEqual(MS.reglages_du_circuit(rg, 'CH'), {'jeux_delta': 0.01})
        self.assertIsNone(MS.reglages_du_circuit(rg, 'ATP'))
        self.assertEqual(MS.reglages_du_circuit({'ace_facteur': 1.03, **rg}, 'CH'), {'ace_facteur': 1.03, 'jeux_delta': 0.01})
        src = open(os.path.join(RACINE, 'simulateur', 'pronostics_du_jour.py'), encoding='utf-8').read()
        self.assertIn("reg = MS.reglages_du_circuit(REGLAGES, c) if p_home is not None else MS.reglages_du_circuit(REGLAGES, None)", src)
        self.assertIn("reg = MS.reglages_du_circuit(REGLAGES, c) if p_home is not None else None", src)

    def test_production_ne_lit_le_delta_que_si_la_regle_est_passee(self):
        sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
        import pronostics_du_jour as PJ
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            p = os.path.join(d, 'simulateur', 'rapport_service_challenger.json')
            json.dump({'retenu': False, 'delta_appris': 0.01}, open(p, 'w'))
            self.assertIsNone(PJ.charger_reglages(d))
            json.dump({'retenu': True, 'delta_appris': 0.01}, open(p, 'w'))
            self.assertIsNone(PJ.charger_reglages(d), 'la règle seule ne suffit pas : contrôle comme en production exigé')
            json.dump({'retenu': True, 'verifie_comme_en_production': True, 'delta_appris': 0.01}, open(p, 'w'))
            self.assertEqual(PJ.charger_reglages(d), {'par_circuit': {'CH': {'jeux_delta': 0.01}}})


class Sonde(unittest.TestCase):
    def test_points_au_service_sans_jeux_decisifs(self):
        jeux = [[1, 1, 1, 'HHAH'], [1, 2, 2, 'AAAA'], [1, 13, 1, 'HAHAHAHA']]
        s = SP.service(jeux)
        self.assertEqual(s[1], [3, 4])
        self.assertEqual(s[2], [4, 4])

    def test_comparaison_sackmann(self):
        lignes = [{'tourney_date': '20190506', 'winner_name': 'Jan Choinski', 'loser_name': 'Max Purcell',
                   'w_svpt': '60', 'w_1stWon': '30', 'w_2ndWon': '12', 'l_svpt': '50', 'l_1stWon': '20', 'l_2ndWon': '10'}]
        self.assertEqual(SP.pct_sackmann(lignes, 'Max Purcell', 'Jan Choinski', '2019'), (60.0, 70.0))
        self.assertIsNone(SP.pct_sackmann(lignes, 'Max Purcell', 'Jan Choinski', '2020'))

    def test_workflows(self):
        w = open(os.path.join(RACINE, '.github/workflows/sonde_points_challenger.yml'), encoding='utf-8').read()
        self.assertIn('contents: read', w)
        self.assertNotIn('git push', w)
        e = open(os.path.join(RACINE, '.github/workflows/etude_service_challenger.yml'), encoding='utf-8').read()
        self.assertIn("paths: ['simulateur/etude_service_challenger.py']", e)
        self.assertIn('git add -- simulateur/rapport_service_challenger.json', e)


if __name__ == '__main__':
    unittest.main()


class Garde(unittest.TestCase):
    def test_l_etude_ne_pose_jamais_le_controle_production(self):
        src = open(os.path.join(RACINE, 'simulateur', 'etude_service_challenger.py'), encoding='utf-8').read()
        self.assertNotIn("'verifie_comme_en_production':", src)
