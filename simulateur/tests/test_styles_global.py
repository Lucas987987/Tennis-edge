"""Second avis global de styles : gel, orientation et journal prospectif."""
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import styles_global as SG
import vitrine as V


class VariablesEtPrediction(unittest.TestCase):
    def setUp(self):
        self.acc = {
            ('a', 'equilibre', 'global'): {'n': 20, 'v': 14},
            ('b', 'equilibre', 'global'): {'n': 20, 'v': 8},
        }

    def test_variables_uniquement_globales_et_antisymetriques(self):
        x = SG.variables(self.acc, 'a', 'b', 'equilibre', 'equilibre')
        y = SG.variables(self.acc, 'b', 'a', 'equilibre', 'equilibre')
        self.assertGreater(x['bilan_global'], 0)
        self.assertAlmostEqual(x['bilan_global'], -y['bilan_global'])
        self.assertEqual(x['documentation_bilans'], 20)
        self.assertNotIn('bilan_surface', x)
        self.assertNotIn('elo', x)

    def test_prediction_reversible_et_champion_inchange(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            source = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            shutil.copy(os.path.join(source, SG.FICHIER_MODELE), os.path.join(d, SG.FICHIER_MODELE))
            modele = SG.charger_modele(d)
            p = SG.predire(modele, {'cles': ['a', 'b'], 'bilan_global': .2})
            q = SG.predire(modele, {'cles': ['b', 'a'], 'bilan_global': -.2})
            self.assertAlmostEqual(p, 1-q)
            m = {'combinaison': {'p_home': .61}, 'stats': {'p_home': .7}}
            self.assertEqual(SG.probabilite_champion(m), .61)
            self.assertEqual(m['combinaison']['p_home'], .61)


class JournalProspectif(unittest.TestCase):
    def setUp(self):
        self.source = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.bloc = {
            'challenger_seulement': True, 'schema': SG.SCHEMA,
            'styles': ['equilibre', 'equilibre'], 'bilan_global': .2,
            'taux_global_home': .6, 'taux_global_away': .4,
            'documentation_global_home': 20, 'documentation_global_away': 20,
            'documentation_bilans': 20,
        }

    def match(self, debut='2026-10-29T12:00:00Z'):
        return {'uid': 'u1', 'debut_utc': debut, 'home': 'A', 'away': 'B', 'cles': ['a', 'b'],
                'circuit': 'ATP', 'surface': 'Hard', 'combinaison': {'p_home': .61}}

    def test_fige_unique_sans_modifier_le_document_ni_avant_le_gel(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            shutil.copy(os.path.join(self.source, SG.FICHIER_MODELE), os.path.join(d, SG.FICHIER_MODELE))
            with open(os.path.join(d, SG.FICHIER_FEATURES), 'w', encoding='utf-8') as f:
                json.dump({'matchs': {'u1': {'styles_global': self.bloc}}}, f)
            doc = {'genere_le': '2026-10-28T01:00:00Z', 'matchs': [self.match()]}
            avant = copy.deepcopy(doc)
            r1, r2 = SG.journaliser(d, doc), SG.journaliser(d, doc)
            self.assertEqual(r1['nouveaux_figes'], 1)
            self.assertEqual(r2['nouveaux_figes'], 0)
            self.assertEqual(doc, avant)
            ancien = dict(doc, matchs=[self.match('2026-10-27T12:00:00Z')])
            self.assertEqual(SG.journaliser(d, ancien)['n_eligibles'], 0)
            with open(os.path.join(d, SG.JOURNAL), encoding='utf-8') as f:
                ligne = json.loads(f.readline())
            self.assertEqual(ligne['champion'], .61)
            self.assertEqual(ligne['paire_styles'], 'equilibre|equilibre')
            self.assertFalse(ligne['activation'])

    def test_confirmation_independante_et_champion_public_sans_second_avis(self):
        futur = {'debut_utc': '2026-10-29T12:00:00Z', 'resultat_resolu': True,
                 'pronostic_fige': True, 'apparie_champion': True, 'y': 1,
                 'champion': .6, 'styles_global': .61, 'paire_styles': 'equilibre|equilibre'}
        rapport = SG.evaluer_confirmation([futur], bootstrap=0)
        self.assertFalse(rapport['activation'])
        self.assertTrue(rapport['comparaison_independante_pas_preuve_incrementale'])
        lignes = [{'uid': 'u1'}]
        V.ajouter_styles_descriptifs(lignes, {'matchs': {'u1': {
            'descriptif_seulement': True, 'joueurs': [{}, {}], 'styles_global': self.bloc}}})
        self.assertNotIn('styles_global', lignes[0]['styles_descriptifs'])


if __name__ == '__main__':
    unittest.main()
