"""Contrôles du challenger de styles ajustés et de sa cohorte prospective."""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import etude_styles_ajustes as EA
import styles_ajustes as SA
import styles_descriptifs as SD
import styles_valeur as SV
import vitrine as V
from simulateur.tests.test_styles_descriptifs import match


class ResidusAjustesTest(unittest.TestCase):
    def test_correction_elo_surface_contraction_et_symetrie(self):
        acc = SA.Accumulateur()
        jour = dt.date(2024, 1, 1)
        acc.ajouter('a', 'b', 'equilibre', 'grand_serveur', 'Hard', jour, .75)
        w = .5 ** (1/365)
        mesure = acc.mesure('a', 'grand_serveur', 'Hard', jour + dt.timedelta(days=1))
        self.assertAlmostEqual(mesure['residu'], .25 * w / (20+w))
        self.assertEqual(acc.mesure('a', 'grand_serveur', 'Clay', jour, True)['n_effectif'], 0)
        x = acc.variables('a', 'b', 'equilibre', 'grand_serveur', 'Hard', jour + dt.timedelta(days=1))
        y = acc.variables('b', 'a', 'grand_serveur', 'equilibre', 'Hard', jour + dt.timedelta(days=1))
        self.assertAlmostEqual(x['style_residu_global_ecart'], -y['style_residu_global_ecart'])
        self.assertAlmostEqual(x['style_residu_global_ecart'], .5 * w / (20+w))
        self.assertAlmostEqual(x['documentation_residu_global'], w)

    def test_decroissance_temporelle(self):
        acc = SA.Accumulateur()
        jour = dt.date(2024, 1, 1)
        acc.ajouter('a', 'b', 'equilibre', 'equilibre', 'Hard', jour - dt.timedelta(days=365), .6)
        acc.ajouter('a', 'b', 'equilibre', 'equilibre', 'Hard', jour, .6)
        self.assertAlmostEqual(acc.mesure('a', 'equilibre', 'Hard', jour)['n_effectif'], 1.5)

    def test_meme_jour_exclu_du_residu(self):
        M = [match(i) for i in range(8)]
        M.append(dict(M[-1], num=9))
        rows = SV.observations(M, {id(m) for m in M})
        self.assertEqual(rows[-2]['documentation_residu_global'], rows[-1]['documentation_residu_global'])
        self.assertGreater(rows[-1]['documentation_residu_global'], 0)
        self.assertLess(rows[-1]['documentation_residu_global'], 1)
        acc, _, ajustes = SD.calculer(M, {'a': {'circuit': 'ATP', 'surface': 'Hard'},
                                               'b': {'circuit': 'ATP', 'surface': 'Hard'}},
                                      M[-1]['date'], avec_ajustes=True)
        x = ajustes.variables('a', 'b', 'equilibre', 'equilibre', 'Hard', M[-1]['date'])
        self.assertGreater(x['documentation_residu_global'], 0)
        self.assertLess(x['documentation_residu_global'], 1)
        self.assertEqual(SV._taux(acc, 'a', 'equilibre', 'global')[1], 1)


class EvaluationGeleeTest(unittest.TestCase):
    def test_ajustement_controle_et_diagnostic_non_confirmant(self):
        rows = []
        for i in range(240):
            rows.append({'date': dt.date(2024, 1, 1) + dt.timedelta(days=3*i),
                         'semaine': f'{i//20}', 'y': i % 2, 'elo': .55 + .02*(i % 3),
                         'service_retour': .54 + .01*(i % 4), 'surface': 'Hard', 'circuit': 'ATP',
                         'documentation_balles': 1000, 'documentation_matchs': 100,
                         'documentation_bilans': 40, 'documentation_surface': 20,
                         'bilan_global': .1, 'bilan_surface': .05,
                         'style_residu_global_ecart': .02*((i % 5)-2),
                         'style_residu_surface_ecart': .01*((i % 3)-1),
                         'documentation_residu_global': 20, 'documentation_residu_surface': 10,
                         'paire_styles': 'equilibre|grand_serveur'})
        modele, rapport = EA.construire(rows, bootstrap=0)
        self.assertFalse(modele['activation'])
        self.assertFalse(rapport['activation'])
        self.assertFalse(rapport['champion_actif_modifie'])
        self.assertFalse(rapport['diagnostic_historique_reutilise']['confirmation'])
        self.assertTrue(rapport['confirmation_future']['2025_2026_exclus'])


class JournalProspectifTest(unittest.TestCase):
    def setUp(self):
        self.source = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.bloc = {'challenger_seulement': True, 'styles': ['equilibre', 'grand_serveur'],
                     'style_residu_global_ecart': .02, 'style_residu_surface_ecart': .01,
                     'documentation_residu_global': 20, 'documentation_residu_surface': 12}

    def match(self, debut='2026-10-29T12:00:00Z'):
        return {'uid': 'u1', 'debut_utc': debut, 'home': 'A', 'away': 'B', 'circuit': 'ATP',
                'surface': 'Hard', 'matchs_joues': [20, 30], 'stats': {'p_home': .61},
                'combinaison': {'p_simulation': .58, 'match_simule': {
                    'profil_contexte': {'n_balles_effectives': [800, 900]}}}}

    def test_premier_fige_unique_et_historique_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            shutil.copy(os.path.join(self.source, SA.FICHIER_MODELE), os.path.join(d, SA.FICHIER_MODELE))
            with open(os.path.join(d, SA.FICHIER_FEATURES), 'w', encoding='utf-8') as f:
                json.dump({'matchs': {'u1': {'styles_ajustes': self.bloc}}}, f)
            doc = {'genere_le': '2026-10-28T01:00:00Z', 'matchs': [self.match()]}
            r1, r2 = SA.journaliser(d, doc), SA.journaliser(d, doc)
            self.assertEqual(r1['nouveaux_figes'], 1)
            self.assertEqual(r2['nouveaux_figes'], 0)
            ancien = dict(doc, matchs=[self.match('2026-10-27T12:00:00Z')])
            self.assertEqual(SA.journaliser(d, ancien)['n_eligibles'], 0)
            with self.assertRaises(ValueError):
                SA.evaluer_confirmation([{'debut_utc': '2026-10-27T12:00:00Z'}], bootstrap=0)

    def test_confirmation_insuffisante_et_champion_public_sans_residu(self):
        futur = {'debut_utc': '2026-10-29T12:00:00Z', 'resultat_resolu': True,
                 'pronostic_fige': True, 'apparie_champion': True, 'y': 1,
                 'controle': .6, 'challenger': .61, 'variables': {}}
        rapport = SA.evaluer_confirmation([futur], bootstrap=0)
        self.assertFalse(rapport['activation'])
        self.assertFalse(rapport['criteres_numeriques_atteints'])
        lignes = [{'uid': 'u1'}]
        V.ajouter_styles_descriptifs(lignes, {'matchs': {'u1': {
            'descriptif_seulement': True, 'joueurs': [{}, {}], 'styles_ajustes': self.bloc}}})
        self.assertNotIn('styles_ajustes', lignes[0]['styles_descriptifs'])


if __name__ == '__main__':
    unittest.main()
