"""« Là où l'algo hésite », ATP et WTA, stats de service et de retour (paquet 316, 20/11/2026) : règle écrite avant,
rien n'entre dans l'algo."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import etude_hesitation_sr as H  # noqa: E402

SRC = (RACINE / 'simulateur' / 'etude_hesitation_sr.py').read_text(encoding='utf-8')
D = dt.date(2024, 6, 1)


def r(**k):
    v = {'n': 12, 'srv': 65.0, 'ret': 38.0, 'tot': 51.0, 'n90': 6, 'tot90': 52.0}
    v.update(k)
    return v


class Regle(unittest.TestCase):
    def test_regle_ecrite_avant(self):
        self.assertIn("RÈGLE ÉCRITE LE 20/11/2026, AVANT DE REGARDER LES RÉSULTATS", SRC)
        self.assertEqual((H.MIN_JUGES, H.MARGE, H.MIN_ERREURS_TYPES), (1000, 0.001, 2.0))
        self.assertEqual((H.COUPURE, H.FIN, H.ZONE), (dt.date(2023, 1, 1), dt.date(2026, 7, 1), (0.5, 0.6)))
        self.assertEqual(H.CIRCUITS, ('ATP', 'WTA'))
        self.assertIn('MÊME SIGNE', H.regle())

    def test_resume(self):
        h = [(D - dt.timedelta(days=400), 80, 50, 80, 30), (D - dt.timedelta(days=200), 80, 52, 80, 28),
             (D - dt.timedelta(days=30), 70, 49, 70, 21)]
        s = H.resume(h, D)
        self.assertEqual((s['n'], s['n90']), (2, 1))                                  # 400 jours : hors période
        self.assertAlmostEqual(s['srv'], 100 * 101 / 150)
        self.assertAlmostEqual(s['tot'], 100 * (101 + 49) / 300)
        self.assertAlmostEqual(s['tot90'], 100 * 70 / 140)
        self.assertIsNone(H.resume(h, D - dt.timedelta(days=500)))

    def test_indices(self):
        self.assertAlmostEqual(H.indice('service', r(srv=68.0), r()), 0.3)
        self.assertAlmostEqual(H.indice('retour', r(), r(ret=40.0)), -0.2)
        self.assertAlmostEqual(H.indice('tendance', r(tot90=54.0), r()), 0.2)
        self.assertEqual(H.indice('points_gagnes', r(n=9), r()), 0.0)                 # moins de 10 matchs
        self.assertEqual(H.indice('tendance', r(n90=4), r()), 0.0)                    # moins de 5 matchs sur 90 jours
        self.assertEqual(H.indice('service', None, r()), 0.0)

    def test_rapport_public(self):
        d = json.loads((RACINE / 'simulateur' / 'rapport_hesitation_sr.json').read_text(encoding='utf-8'))
        self.assertEqual(d['paquet'], 316)
        self.assertEqual(set(d['indices']), set(H.INDICES))
        for v in d['indices'].values():
            self.assertEqual(set(v), {'ATP', 'WTA'})
        txt = json.dumps(d, ensure_ascii=False).lower()
        for mot in ('march', 'pinnacle', 'cote'):
            self.assertNotIn(mot, txt)

    def test_rien_dans_l_algo(self):
        prod = (RACINE / 'simulateur' / 'pronostics_du_jour.py').read_text(encoding='utf-8')
        self.assertNotIn('hesitation_sr', prod)


if __name__ == '__main__':
    unittest.main()
