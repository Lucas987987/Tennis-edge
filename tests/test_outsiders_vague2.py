"""Outsiders qui gagnent, deuxième vague (paquet 304, 20/11/2026) : règle écrite avant, base = l'algo actuel
(Challenger : les deux décalages du paquet 274 compris), rien n'entre dans l'algo."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import etude_outsiders_vague2 as V  # noqa: E402

SRC = (RACINE / 'simulateur' / 'etude_outsiders_vague2.py').read_text(encoding='utf-8')
D = dt.date(2024, 5, 1)


def vue(**k):
    v = {'long': False, 'court': True, 'rang': None, 'charge': 0, 'tournois': 0, 'dyn': None, 'enchaine': False}
    v.update(k)
    return v


class Regle(unittest.TestCase):
    def test_regle_ecrite_avant(self):
        self.assertIn("RÈGLE ÉCRITE LE 20/11/2026, AVANT DE REGARDER LES RÉSULTATS", SRC)
        self.assertEqual((V.MIN_JUGES, V.MARGE, V.MIN_ERREURS_TYPES), (1000, 0.001, 2.0))
        self.assertEqual((V.COUPURE, V.FIN), (dt.date(2023, 1, 1), dt.date(2026, 7, 1)))
        self.assertIn('CIRCUIT PAR CIRCUIT', V.regle())

    def test_situations(self):
        self.assertTrue(V.situation('favori_charge', vue(charge=4), vue(charge=8, tournois=2)))
        self.assertFalse(V.situation('favori_charge', vue(charge=6), vue(charge=8, tournois=2)))
        self.assertFalse(V.situation('favori_charge', vue(charge=2), vue(charge=9, tournois=1)))
        self.assertTrue(V.situation('dynamiques_opposees', vue(dyn=31.0), vue(dyn=-30.0)))
        self.assertFalse(V.situation('dynamiques_opposees', vue(dyn=None), vue(dyn=-50.0)))
        self.assertTrue(V.situation('favori_enchaine', vue(), vue(enchaine=True)))

    def test_note_il_y_a(self):
        h = [(dt.date(2024, 2, 1), 1500.0), (dt.date(2024, 3, 1), 1520.0), (dt.date(2024, 4, 20), 1560.0)]
        self.assertEqual(V.note_il_y_a(h, D, 60), 1520.0)
        self.assertIsNone(V.note_il_y_a(h, D, 120))

    def test_base_challenger_comme_la_production(self):
        z = V._lg(0.3)                                                      # le vainqueur est l'outsider (30 %)
        r = {'c': 'CH', 'd': D, 'zb': z, 'vg': vue(rang=50), 'vp': vue(rang=90, long=True)}
        V.poser_ch_en_place([r], {'favori_fatigue': 0.15, 'outsider_mieux_classe': 0.16})
        self.assertAlmostEqual(r['zb'], z + 0.31)
        r2 = {'c': 'CH', 'd': D, 'zb': -z, 'vg': vue(rang=90), 'vp': vue(rang=50)}   # l'outsider a perdu
        V.poser_ch_en_place([r2], {'outsider_mieux_classe': 0.16})
        self.assertAlmostEqual(r2['zb'], -z - 0.16)
        r3 = {'c': 'ATP', 'd': D, 'zb': z, 'vg': vue(rang=50), 'vp': vue(rang=90, long=True)}
        V.poser_ch_en_place([r3], {'favori_fatigue': 0.15})
        self.assertEqual(r3['zb'], z)

    def test_rapport_public(self):
        p = RACINE / 'simulateur' / 'rapport_outsiders_vague2.json'
        d = json.loads(p.read_text(encoding='utf-8'))
        self.assertEqual(d['paquet'], 304)
        self.assertEqual(set(d['situations']), set(V.SITUATIONS))
        for v in d['situations'].values():
            self.assertEqual(set(v), {'ATP', 'WTA', 'CH'})
        self.assertIn('le % de victoire ne change pas', d['descriptif'])
        txt = json.dumps(d, ensure_ascii=False).lower()
        for mot in ('march', 'pinnacle', 'cote'):
            self.assertNotIn(mot, txt)

    def test_rien_dans_l_algo(self):
        prod = (RACINE / 'simulateur' / 'pronostics_du_jour.py').read_text(encoding='utf-8')
        self.assertNotIn('vague2', prod)


if __name__ == '__main__':
    unittest.main()
