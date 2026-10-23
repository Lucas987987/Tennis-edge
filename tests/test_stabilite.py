"""Règle de stabilité (23/10/2026) : marge 0,001, deux semaines de suite pour entrer comme pour sortir."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import stabilite as ST  # noqa: E402


class Stabilite(unittest.TestCase):
    def test_entree_deux_semaines(self):
        e = {}
        self.assertFalse(ST.decider(e, 'x', False, True, 0.600, 0.605, 'S1')[0])
        self.assertFalse(ST.decider(e, 'x', False, True, 0.600, 0.605, 'S1')[0])   # même semaine : compte une fois
        ok, note = ST.decider(e, 'x', False, True, 0.600, 0.605, 'S2')
        self.assertTrue(ok)
        self.assertIn('adopté', note)

    def test_marge(self):
        e = {}
        for s in ('S1', 'S2', 'S3'):
            ok, note = ST.decider(e, 'arbres', False, True, 0.5962, 0.5963, s)
            self.assertFalse(ok)
        self.assertIn('écart trop faible', note)

    def test_serie_coupee(self):
        e = {}
        ST.decider(e, 'x', False, True, 0.60, 0.61, 'S1')
        ST.decider(e, 'x', False, False, 0.61, 0.60, 'S2')
        self.assertFalse(ST.decider(e, 'x', False, True, 0.60, 0.61, 'S3')[0])      # il faut deux semaines DE SUITE
        self.assertTrue(ST.decider(e, 'x', False, True, 0.60, 0.61, 'S4')[0])

    def test_sortie_et_hysteresis(self):
        e = {}
        self.assertTrue(ST.decider(e, 'y', True, False, 0.6105, 0.6100, 'S1')[0])   # un peu moins bien : reste
        self.assertTrue(ST.decider(e, 'y', True, False, 0.6105, 0.6100, 'S2')[0])
        self.assertTrue(ST.decider(e, 'y', True, False, 0.62, 0.61, 'S3')[0])       # nettement moins bien : 1/2
        self.assertFalse(ST.decider(e, 'y', True, False, 0.62, 0.61, 'S4')[0])      # 2/2 : sort

    def test_sans_log_loss(self):
        e = {}
        self.assertFalse(ST.decider(e, 'g', False, True, semaine='S1')[0])
        self.assertTrue(ST.decider(e, 'g', False, True, semaine='S2')[0])

    def test_appliquer_garde_les_anciens_reglages(self):
        e = {}
        ancien = {'adopte': True, 'delta': -0.56, 'raison': 'r'}
        out = ST.appliquer(e, 'nv', ancien, {'adopte': False, 'delta': None, 'raison': 'semaine moyenne',
                                             'll': {'avec': 0.5455, 'sans': 0.5450}}, ('delta',), 'S1')
        self.assertTrue(out['adopte'])
        self.assertFalse(out['adopte_brut'])
        self.assertEqual(out['delta'], -0.56)
        self.assertIn('en place', out['raison'])


if __name__ == '__main__':
    unittest.main()
