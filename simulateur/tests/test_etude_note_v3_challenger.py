# -*- coding: utf-8 -*-
"""Tests de simulateur/etude_note_v3_challenger.py (paquet 449), sur données factices : aucune archive nécessaire."""
import datetime as dt
import json
import math
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ICI))
import etude_note_v3_challenger as NV  # noqa: E402


def _sg(z):
    return 1 / (1 + math.exp(-z))


def lignes(pentes, n=1500, graine=2):
    """Rejeu factice (circuit, date, n_min, z vu du vainqueur) : la réalité suit la pente de la classe."""
    rnd = random.Random(graine)
    rows = []
    for d in (dt.date(2025, 3, 1), dt.date(2026, 1, 15)):
        for i, n_min in enumerate((15, 50, 150, 500)):
            for _ in range(n):
                z0 = rnd.gauss(0, 1.2)
                rows.append(('CH', d, n_min, z0 if rnd.random() < _sg(pentes[i] * z0) else -z0))
    return rows


class TestNoteV3Challenger(unittest.TestCase):
    def test_note_et_niveau(self):
        self.assertEqual(NV.note(1.0), 100)
        self.assertEqual(NV.note(0.8), 80)
        self.assertEqual(NV.note(1.25), 80)
        self.assertEqual([NV.niveau(n) for n in (70, 80, 90, 95)], ['fragile', 'prudent', 'correct', 'solide'])

    def test_apprendre_retrecit(self):
        M = NV.apprendre([(0, z) for z in (1.0, -0.5, 2.0)] + [(1, z) for z in (0.5,) * 50])
        self.assertIn('_circuit', M)
        self.assertLess(abs(M[0] - M['_circuit']), abs(M[1] - M['_circuit']) + 1)   # 3 matchs : collé au circuit

    def test_retenue_quand_la_note_en_place_se_trompe(self):
        en_place = {'_circuit': 0.8, 0: 0.75, 1: 0.79, 2: 0.92, 3: 0.92}
        j = NV.juger(lignes((1.1, 1.1, 1.1, 1.0)), en_place)
        self.assertTrue(j['retenue'], j['raisons'])
        self.assertGreater(j['periode_jugee']['gain'], NV.MARGE)
        self.assertGreater(j['sens_inverse']['gain'], 0)

    def test_non_retenue_quand_la_note_en_place_est_juste(self):
        en_place = {'_circuit': 0.9, 0: 0.7, 1: 0.8, 2: 0.9, 3: 1.0}
        j = NV.juger(lignes((0.7, 0.8, 0.9, 1.0)), en_place)
        self.assertFalse(j['retenue'])
        self.assertIn('gain sous 0,001', j['raisons'])

    def test_trop_peu_de_matchs(self):
        j = NV.juger(lignes((1.2, 1.2, 1.2, 1.2), n=100), {'_circuit': 0.8})
        self.assertIn('moins de 1 000 matchs jugés', j['raisons'])

    def test_modele_candidat(self):
        mod = {'ATP|1|1': {'pente': 0.9, 'matchs': 10}, 'CH|0|1': {'pente': 0.7, 'matchs': 10},
               '_circuits': {'ATP': 0.9, 'WTA': 1.0, 'CH': 0.8}}
        out = NV.modele_candidat(mod, {'_circuit': 1.05, 0: 1.1, 1: 1.0, 2: 1.0, 3: 0.95})
        self.assertEqual(out['ATP|1|1'], mod['ATP|1|1'])                     # ATP / WTA inchangés
        self.assertEqual({out[f'CH|0|{a}']['pente'] for a in range(3)}, {1.1})  # mêmes pentes, trois ampleurs
        self.assertEqual(out['_circuits']['CH'], 1.05)
        self.assertEqual(out['_circuits']['ATP'], 0.9)

    def test_journal(self):
        with open(NV.GABARIT_JOURNAL, encoding='utf-8') as f:
            g = json.load(f)
        self.assertEqual(g['paquet'], 449)
        j = NV.juger(lignes((1.1, 1.1, 1.1, 1.0)), {'_circuit': 0.8, 0: 0.75, 1: 0.79, 2: 0.92, 3: 0.92})
        e = NV.entree_journal({'jugement': j}, g)
        self.assertIn('RETENUE', e['quoi'])
        self.assertIn("rien n'est changé par ce paquet", e['quoi'])
        for mot in ('marché', 'Pinnacle', 'cote'):
            self.assertNotIn(mot, e['quoi'] + e['garde_fou'])

    def test_rien_en_production(self):
        src = open(os.path.join(os.path.dirname(ICI), 'etude_note_v3_challenger.py'), encoding='utf-8').read()
        self.assertNotIn("'rapport_fiabilite_v3.json'), 'w'", src)            # lu, jamais écrit
        self.assertIn("'en_production': False", src)


if __name__ == '__main__':
    unittest.main()
