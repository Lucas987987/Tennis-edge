"""Contrôles de la correction orientée des profils serveurs par branche."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import etude_serveurs_circuits as ES
import styles_valeur as SV
from simulateur.tests.test_styles_descriptifs import match


def ligne(i, circuit='WTA', styles=('serveur_attaquant', 'contreur')):
    return {'date': dt.date(2024, 1, 1)+dt.timedelta(days=3*i), 'semaine': f'{i//20}',
            'y': i % 2, 'elo': .55+.02*(i % 3), 'service_retour': .54+.01*(i % 4),
            'surface': 'Hard', 'circuit': circuit,
            'documentation_balles': 1000, 'documentation_matchs': 100,
            'documentation_bilans': 40, 'documentation_surface': 20,
            'bilan_global': .1, 'bilan_surface': .05,
            'style_home': styles[0], 'style_away': styles[1],
            'paire_styles': '|'.join(sorted(styles))}


class VariableServeurTest(unittest.TestCase):
    def test_quatre_duels_orientes_et_zero_hors_perimetre(self):
        for serveur, adverse in ES.DUELS.values():
            self.assertEqual(ES.duel_serveur(serveur, adverse), 1)
            self.assertEqual(ES.duel_serveur(adverse, serveur), -1)
        self.assertEqual(ES.duel_serveur('serveur_attaquant', 'grand_serveur'), 0)
        self.assertEqual(ES.duel_serveur('indetermine', 'contreur'), 0)

    def test_une_seule_branche_active_a_la_fois(self):
        r = ligne(0, 'WTA')
        self.assertEqual(ES.variable_branche(r, 'wta'), 1)
        self.assertEqual(ES.variable_branche(r, 'atp'), 0)
        self.assertEqual(ES.variable_branche(r, 'challenger'), 0)
        self.assertEqual(ES.branche('CH'), 'challenger')
        self.assertEqual(ES.branche('ITF'), 'challenger')

    def test_observations_conservent_styles_et_temporalite(self):
        matchs = [match(i) for i in range(8)]
        matchs.append(dict(matchs[-1], num=9))
        rows = SV.observations(matchs, {id(m) for m in matchs})
        self.assertIn('style_home', rows[-1])
        self.assertIn('style_away', rows[-1])
        self.assertEqual(rows[-2]['documentation_bilans'], rows[-1]['documentation_bilans'])


class EvaluationTest(unittest.TestCase):
    def test_modeles_partages_figes_et_aucun_choix_apres_diagnostic(self):
        rows = []
        for i in range(360):
            circuit = ('ATP', 'WTA', 'CH')[i % 3]
            styles = list(ES.DUELS.values())[i % 4]
            if i % 2:
                styles = styles[::-1]
            rows.append(ligne(i, circuit, styles))
        rapport = ES.evaluer(rows, bootstrap=0)
        self.assertEqual(set(rapport['branches']), {'atp', 'wta', 'challenger'})
        self.assertTrue(rapport['socle_partage'])
        self.assertFalse(rapport['algorithmes_autonomes_par_circuit'])
        self.assertFalse(rapport['activation'])
        self.assertFalse(rapport['champion_actif_modifie'])
        self.assertTrue(all(rapport['convergence'].values()))
        self.assertEqual(set(rapport['branches']['wta']['duels_diagnostic']), set(ES.DUELS))
        self.assertIn('réutilisé', rapport['nature_diagnostic'])
        self.assertIn('aucun duel', rapport['selection'])

    def test_une_branche_sans_match_ne_peut_pas_etre_activee(self):
        rapport = ES.evaluer([ligne(i) for i in range(240)], bootstrap=0)
        self.assertEqual(rapport['branches']['atp']['couverture_diagnostic']['n'], 0)
        self.assertFalse(rapport['branches']['atp']['suivi_prospectif_justifie'])
        self.assertFalse(rapport['activation'])


if __name__ == '__main__':
    unittest.main()
