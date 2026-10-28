"""Contrôles du challenger dur fondé sur les statistiques contre les styles."""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import etude_statistiques_styles as ES
import statistiques_styles as SS
import styles_descriptifs as SD
import vitrine as V
from simulateur.tests.test_styles_descriptifs import match


def ligne_synthetique(i):
    return {'date': dt.date(2024, 1, 1) + dt.timedelta(days=3*i), 'semaine': f'{i//20}',
            'y': i % 2, 'elo': .55 + .02*(i % 3), 'service_retour': .54 + .01*(i % 4),
            'surface': 'Hard', 'circuit': 'ATP', 'documentation_balles': 1000,
            'documentation_matchs': 100, 'documentation_bilans': 40, 'documentation_surface': 20,
            'bilan_global': .1, 'bilan_surface': .05, 'documentation_stats': 20,
            'stats_points_gagnes_pct': .01*((i % 5)-2),
            'stats_service_gagnes_pct': .02*((i % 3)-1),
            'stats_retour_gagnes_pct': .01*((i % 4)-1),
            'stats_gagnes_2e_pct': .015*((i % 5)-2),
            'stats_balles_break_sauvees_pct': .01*((i % 3)-1),
            'stats_balles_break_converties_pct': .02*((i % 4)-1)}


class VariablesEtEvaluationTest(unittest.TestCase):
    def test_absence_des_deux_cotes_et_temporalite(self):
        self.assertEqual(SD.variables_statistiques({}, 'a', 'b', 'equilibre', 'equilibre')['documentation_stats'], 0)
        M = [match(i) for i in range(8)]
        M.append(dict(M[-1], num=9))
        rows = ES.observations(M, {id(m) for m in M})
        self.assertEqual(rows[-2]['documentation_stats'], rows[-1]['documentation_stats'])
        self.assertGreater(rows[-1]['documentation_stats'], 0)

    def test_modele_fige_sur_decouverte_et_jamais_actif(self):
        rapport = ES.evaluer([ligne_synthetique(i) for i in range(240)], bootstrap=0)
        self.assertEqual(rapport['n_decouverte'], 122)
        self.assertTrue(all(rapport['convergence'].values()))
        self.assertFalse(rapport['activation'])
        self.assertFalse(rapport['champion_actif_modifie'])
        self.assertIn('réutilisé', rapport['nature_diagnostic'])


class JournalDurTest(unittest.TestCase):
    def setUp(self):
        self.source = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.bloc = {'challenger_seulement': True, 'schema': SS.SCHEMA,
                     'styles': ['equilibre', 'grand_serveur'], 'bilan_global': .1,
                     'documentation_stats': 20, 'stats_points_gagnes_pct': .01,
                     'stats_service_gagnes_pct': .02, 'stats_retour_gagnes_pct': -.01,
                     'stats_gagnes_2e_pct': .015, 'stats_balles_break_sauvees_pct': .01,
                     'stats_balles_break_converties_pct': -.02}

    def match(self, debut='2026-10-29T12:00:00Z', surface='Hard', uid='u1'):
        return {'uid': uid, 'debut_utc': debut, 'home': 'A', 'away': 'B', 'circuit': 'ATP',
                'surface': surface, 'matchs_joues': [20, 30], 'cles': ['a', 'b'],
                'stats': {'p_home': .61}, 'combinaison': {'p_simulation': .58, 'match_simule': {
                    'profil_contexte': {'n_balles_effectives': [800, 900]}}}}

    def test_dur_seulement_premier_fige_et_historique_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            shutil.copy(os.path.join(self.source, SS.FICHIER_MODELE), os.path.join(d, SS.FICHIER_MODELE))
            with open(os.path.join(d, SS.FICHIER_FEATURES), 'w', encoding='utf-8') as f:
                json.dump({'matchs': {'u1': {'statistiques_styles': self.bloc},
                                      'u2': {'statistiques_styles': self.bloc}}}, f)
            doc = {'genere_le': '2026-10-28T01:00:00Z',
                   'matchs': [self.match(), self.match(uid='u2', surface='Clay')]}
            r1, r2 = SS.journaliser(d, doc), SS.journaliser(d, doc)
            self.assertEqual((r1['n_eligibles'], r1['nouveaux_figes']), (1, 1))
            self.assertEqual(r2['nouveaux_figes'], 0)
            ancien = dict(doc, matchs=[self.match('2026-10-27T12:00:00Z')])
            self.assertEqual(SS.journaliser(d, ancien)['n_eligibles'], 0)
            with self.assertRaises(ValueError):
                SS.evaluer_confirmation([{'debut_utc': '2026-10-27T12:00:00Z'}], bootstrap=0)

    def test_orientation_alphabetique_retournee_au_home(self):
        modele = SS.charger_modele(self.source)
        row = SS.observation(self.match(), self.bloc)
        p0, p1 = SS.predire(modele, row)
        inverse = dict(row, cles=['b', 'a'], elo=1-row['elo'], service_retour=1-row['service_retour'],
                       bilan_global=-row['bilan_global'])
        for nom in modele['variables_statistiques']:
            inverse[f'stats_{nom}'] = -row[f'stats_{nom}']
        q0, q1 = SS.predire(modele, inverse)
        self.assertAlmostEqual(p0, 1-q0)
        self.assertAlmostEqual(p1, 1-q1)

    def test_confirmation_insuffisante_et_bloc_hors_vitrine(self):
        futur = {'debut_utc': '2026-10-29T12:00:00Z', 'resultat_resolu': True, 'surface': 'Hard',
                 'pronostic_fige': True, 'apparie_champion': True, 'y': 1,
                 'champion': .6, 'controle': .6, 'challenger': .61, 'variables': {}}
        rapport = SS.evaluer_confirmation([futur], bootstrap=0)
        self.assertFalse(rapport['activation'])
        self.assertFalse(rapport['criteres_numeriques_atteints'])
        lignes = [{'uid': 'u1'}]
        V.ajouter_styles_descriptifs(lignes, {'matchs': {'u1': {
            'descriptif_seulement': True, 'joueurs': [{}, {}], 'statistiques_styles': self.bloc}}})
        self.assertNotIn('statistiques_styles', lignes[0]['styles_descriptifs'])


if __name__ == '__main__':
    unittest.main()
