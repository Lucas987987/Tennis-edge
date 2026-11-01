"""Régression : doublons du calendrier OddsPapi dans la vitrine publique.

La sortie de production est dédoublonnée, les documents sans provenance
conservent le contrôle de sécurité strict sur les UID.
"""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import validation_vitrine as VV


def match(uid, debut='2026-11-02T12:00'):
    return {
        'uid': uid, 'debut': debut, 'p_home': 0.7,
        'simulation_disponible': True, 'scores_probables': [['6-0 6-0', 1.0]],
        'scores_source': 'exact',
        'distribution_scores': [{'score': [[6, 0], [6, 0]], 'probabilite': 1.0}],
        'simulation': {'n': 20000, 'version': 'simulation', 'sets_gagnants': 2,
                       'tb_final': 7, 'scenario': {
                           'selection': 'representatif', 'score': '6-0 6-0',
                           'sets': [[6, 0], [6, 0]], 'points': '0' * 48,
                           'premier_serveur': True, 'simulation_index': 0,
                           'vainqueur': 0,
                       }},
    }


class DoublonsCalendrierProduction(unittest.TestCase):
    def test_publication_dedoublonnee_et_validation_complete(self):
        a = match('2026-11-02_daniel_michalski_august_holmgren')
        b = match('2026-11-02_joel_schwaerzler_jan_kumstat')
        c = match('2026-11-02_yu_hsiou_hsu_aleksandar_vukic')
        doc = {'pronostics_du': '2026-11-01T14:00:00Z', 'simulations': 20000,
               'matchs': [a, copy.deepcopy(a), b, copy.deepcopy(b), c, copy.deepcopy(c)]}
        self.assertTrue(VV.valider(doc))
        self.assertEqual([m['uid'] for m in doc['matchs']], [a['uid'], b['uid'], c['uid']])
        self.assertEqual(VV.supprimer_doublons_production(doc), 0)

    def test_conserver_lheure_plus_tot(self):
        recent = match('meme_uid', '2026-11-02T15:00')
        ancien = match('meme_uid', '2026-11-02T12:00')
        doc = {'pronostics_du': '2026-11-01T14:00:00Z', 'simulations': 20000,
               'matchs': [recent, ancien]}
        self.assertTrue(VV.valider(doc))
        self.assertEqual(doc['matchs'][0]['debut'], ancien['debut'])

    def test_document_sans_provenance_reste_bloquant(self):
        doc = {'simulations': 20000, 'matchs': [match('x'), match('x')]}
        with self.assertRaisesRegex(ValueError, 'match publié en double'):
            VV.valider(doc)

    def test_vrai_defaut_du_scenario_toujours_bloquant(self):
        a = match('uid_unique')
        a['simulation']['scenario']['points'] += '0'
        doc = {'pronostics_du': '2026-11-01T14:00:00Z', 'simulations': 20000,
               'matchs': [a, copy.deepcopy(a)]}
        with self.assertRaisesRegex(ValueError, 'surnuméraires'):
            VV.valider(doc)


if __name__ == '__main__':
    unittest.main()
