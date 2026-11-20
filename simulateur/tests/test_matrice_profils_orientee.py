"""Contrôles de la matrice exhaustive et orientée des cinq profils."""
import datetime as dt
import itertools
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import etude_matrice_profils_orientee as EM


def ligne(i, circuit='WTA', styles=('serveur_attaquant', 'contreur')):
    return {'date': dt.date(2024, 1, 1)+dt.timedelta(days=3*i), 'semaine': f'{i//20}',
            'y': i % 2, 'elo': .55+.02*(i % 3), 'service_retour': .54+.01*(i % 4),
            'surface': 'Hard', 'circuit': circuit,
            'documentation_balles': 1000, 'documentation_matchs': 100,
            'documentation_bilans': 40, 'documentation_surface': 20,
            'bilan_global': .1, 'bilan_surface': .05,
            'style_home': styles[0], 'style_away': styles[1],
            'paire_styles': '|'.join(sorted(styles))}


class OrientationMatriceTest(unittest.TestCase):
    def test_cinq_profils_dix_paires_vingt_directions(self):
        self.assertEqual(len(EM.STYLES), 5)
        self.assertEqual(len(EM.PAIRES), 10)
        self.assertEqual(len({EM.cle_direction(a, b) for a, b in itertools.permutations(EM.STYLES, 2)}), 20)
        self.assertNotIn('indetermine', EM.STYLES)

    def test_orientation_libre_dans_les_deux_sens(self):
        paire = ('contreur', 'grand_serveur')
        self.assertEqual(EM.orientation_paire(ligne(0, styles=paire), paire), 1)
        self.assertEqual(EM.orientation_paire(ligne(0, styles=paire[::-1]), paire), -1)
        self.assertEqual(EM.orientation_paire(ligne(0, styles=('equilibre', 'contreur')), paire), 0)

    def test_cellule_inverse_sans_double_comptage(self):
        cellule = {'n': 10, 'coefficient_log_odds_favorisant_profil': .2,
                   'victoires_profil_pct': 60.0, 'probabilite_controle_profil_pct': 52.0,
                   'residuel_controle_points': 8.0,
                   'ic95_bootstrap_semaine': {'residuel_controle_points': {'bas': 1.0, 'haut': 14.0}}}
        inv = EM._inverser_cellule(cellule)
        self.assertEqual(inv['n'], 10)
        self.assertEqual(inv['coefficient_log_odds_favorisant_profil'], -.2)
        self.assertEqual(inv['victoires_profil_pct'], 40.0)
        self.assertEqual(inv['residuel_controle_points'], -8.0)
        self.assertEqual(inv['ic95_bootstrap_semaine']['residuel_controle_points'], {'bas': -14.0, 'haut': -1.0})


class EvaluationMatriceTest(unittest.TestCase):
    def test_toutes_les_cellules_sont_rapportees_sans_activation(self):
        rows = []
        for i in range(600):
            circuit = ('ATP', 'WTA', 'CH')[i % 3]
            styles = EM.PAIRES[i % len(EM.PAIRES)]
            if i % 2:
                styles = styles[::-1]
            rows.append(ligne(i, circuit, styles))
        rapport = EM.evaluer(rows, bootstrap=0)
        self.assertTrue(rapport['convergence']['challenger'])
        self.assertEqual(sum(':' in k for k in rapport['coefficients_non_standardises']), 30)
        for nom in EM.BRANCHES:
            self.assertEqual(len(rapport['matrice_directionnelle'][nom]), 20)
            self.assertEqual(rapport['branches'][nom]['activation'], False)
        self.assertFalse(rapport['activation'])
        self.assertFalse(rapport['champion_actif_modifie'])
        self.assertIn('aucune case positive', rapport['comparaisons_multiples'])
        self.assertIn('réutilisé', rapport['nature_diagnostic'])


if __name__ == '__main__':
    unittest.main()
