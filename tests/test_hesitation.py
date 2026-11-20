"""« Là où l'algo hésite » (paquet 313, 20/11/2026) : règle écrite avant, base = l'algo actuel, zone 50–60 %,
rien n'entre dans l'algo."""
import datetime as dt
import json
import math
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import etude_hesitation as H  # noqa: E402

SRC = (RACINE / 'simulateur' / 'etude_hesitation.py').read_text(encoding='utf-8')


def vue(**k):
    v = {'long': False, 'court': True, 'rang': None, 'qualifie': False, 'invite': False, 'domicile': False, 'experience': 0}
    v.update(k)
    return v


class Regle(unittest.TestCase):
    def test_regle_ecrite_avant(self):
        self.assertIn("RÈGLE ÉCRITE LE 20/11/2026, AVANT DE REGARDER LES RÉSULTATS", SRC)
        self.assertEqual((H.MIN_JUGES, H.MARGE, H.MIN_ERREURS_TYPES), (1000, 0.001, 2.0))
        self.assertEqual((H.COUPURE, H.FIN), (dt.date(2023, 1, 1), dt.date(2026, 7, 1)))
        self.assertEqual(H.ZONE, (0.50, 0.60))
        self.assertIn('CIRCUIT PAR CIRCUIT', H.regle())
        self.assertIn('MÊME SIGNE', H.regle())

    def test_indices_vus_du_favori(self):
        self.assertAlmostEqual(H.indice('classement', vue(rang=50), vue(rang=200)), 2.0)
        self.assertEqual(H.indice('classement', vue(rang=1), vue(rang=5000)), 4.0)          # borné
        self.assertEqual(H.indice('classement', vue(rang=None), vue(rang=50)), 0.0)
        self.assertEqual(H.indice('entree', vue(), vue(qualifie=True)), 1.0)
        self.assertEqual(H.indice('invitation', vue(invite=True), vue()), 1.0)
        self.assertEqual(H.indice('domicile', vue(), vue(domicile=True)), -1.0)
        self.assertAlmostEqual(H.indice('experience', vue(experience=99), vue(experience=9)), math.log(10))

    def test_zone(self):
        z55 = H._lg(0.55)
        self.assertEqual(H.zone({'zb': z55, 'vg': 'g', 'vp': 'p'})[1:], ('g', 'p', 1))      # le favori a gagné
        self.assertEqual(H.zone({'zb': -z55, 'vg': 'g', 'vp': 'p'})[1:], ('p', 'g', 0))     # le favori a perdu
        self.assertIsNone(H.zone({'zb': H._lg(0.65), 'vg': 'g', 'vp': 'p'}))
        self.assertIsNone(H.zone({'zb': 0.0, 'vg': 'g', 'vp': 'p'}))

    def test_rapport_public(self):
        d = json.loads((RACINE / 'simulateur' / 'rapport_hesitation.json').read_text(encoding='utf-8'))
        self.assertEqual(d['paquet'], 313)
        self.assertEqual(set(d['indices']), set(H.INDICES))
        for v in d['indices'].values():
            self.assertEqual(set(v), {'ATP', 'WTA', 'CH'})
        self.assertIn('le % de victoire ne change pas', d['descriptif'])
        txt = json.dumps(d, ensure_ascii=False).lower()
        for mot in ('march', 'pinnacle', 'cote'):
            self.assertNotIn(mot, txt)

    def test_rien_dans_l_algo(self):
        prod = (RACINE / 'simulateur' / 'pronostics_du_jour.py').read_text(encoding='utf-8')
        self.assertNotIn('hesitation', prod)


if __name__ == '__main__':
    unittest.main()
