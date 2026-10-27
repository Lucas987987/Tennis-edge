"""Contrôles temporels et statistiques de la valeur des bilans de styles."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import styles_joueurs as ST
import styles_valeur as SV
from simulateur.tests.test_styles_descriptifs import match


class TauxContractes(unittest.TestCase):
    def test_zero_et_petit_echantillon_restent_proches_de_50(self):
        self.assertEqual(SV._taux({}, 'a', 'equilibre', 'global'), (.5, 0))
        acc = {('a', 'equilibre', 'global'): {'n': 7, 'v': 5}}
        p, n = SV._taux(acc, 'a', 'equilibre', 'global')
        self.assertEqual(n, 7)
        self.assertAlmostEqual(p, 15/27)
        self.assertLess(p, 5/7)

    def test_ecart_change_de_sens_avec_l_orientation(self):
        acc = {('a', 'equilibre', 'global'): {'n': 20, 'v': 14},
               ('b', 'equilibre', 'global'): {'n': 20, 'v': 8}}
        x = SV._features(acc, 'a', 'b', 'equilibre', 'equilibre', 'Hard')
        y = SV._features(acc, 'b', 'a', 'equilibre', 'equilibre', 'Hard')
        self.assertGreater(x['bilan_global'], 0)
        self.assertAlmostEqual(x['bilan_global'], -y['bilan_global'])


class ObservationTemporelle(unittest.TestCase):
    def test_meme_jour_exclu_et_controles_identiques(self):
        M = [match(i) for i in range(8)]
        neuvieme = dict(M[-1], num=9)
        M.append(neuvieme)  # même date que le huitième : son résultat n'est pas encore disponible
        choisis = {id(m) for m in M}
        rows = SV.observations(M, choisis)
        self.assertEqual(rows[-2]['documentation_bilans'], 1)
        self.assertEqual(rows[-1]['documentation_bilans'], 1)
        reference = ST.observations_controle(M, choisis)
        self.assertEqual([(r['y'], r['elo'], r['service_retour']) for r in rows],
                         [(r['y'], r['elo'], r['service_retour']) for r in reference])

    def test_aucune_activation_automatique(self):
        rows = []
        for i in range(240):
            rows.append({'date': dt.date(2024, 1, 1)+dt.timedelta(days=3*i),
                         'semaine': f'{i//20}', 'y': i % 2,
                         'elo': .55, 'service_retour': .54, 'surface': 'Hard', 'circuit': 'ATP',
                         'documentation_balles': 1000, 'documentation_matchs': 100,
                         'documentation_bilans': 40, 'documentation_surface': 20,
                         'bilan_global': .1, 'bilan_surface': .05,
                         'paire_styles': 'equilibre|equilibre'})
        out = SV.evaluer(rows, bootstrap=0)
        self.assertFalse(out['activation'])
        self.assertFalse(out['champion_actif_modifie'])


if __name__ == '__main__':
    unittest.main()
