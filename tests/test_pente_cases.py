"""Corriger le % avec la note de fiabilité (paquet 317, 21/11/2026) : règle écrite avant, rien n'entre dans l'algo."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import etude_pente_cases as P  # noqa: E402

SRC = (RACINE / 'simulateur' / 'etude_pente_cases.py').read_text(encoding='utf-8')


class Regle(unittest.TestCase):
    def test_regle_ecrite_avant(self):
        self.assertIn("RÈGLE ÉCRITE LE 21/11/2026, AVANT DE REGARDER LES RÉSULTATS", SRC)
        self.assertEqual((P.MIN_JUGES, P.MARGE, P.MIN_ERREURS_TYPES, P.SEUIL_NOTE), (1000, 0.001, 2.0, 85))
        self.assertEqual((P.COUPURE, P.FIN), (dt.date(2023, 1, 1), dt.date(2026, 7, 1)))
        self.assertIn('MÊME CÔTÉ DE 1', P.regle())

    def test_juger(self):
        J = [{'c': 'CH', 'z': z, 'a': 0.8, 'note': 80} for z in [1.0] * 700 + [-1.0] * 300]   # trop confiant : 70 % pour 73 % annoncés
        r = P.juger(J, 'CH', 'notes_basses')
        self.assertEqual(r['2023 → juin 2026']['matchs'], 1000)
        self.assertGreater(r['2023 → juin 2026']['gain'], 0)
        self.assertEqual(P.juger(J, 'ATP', 'toutes_les_cases')['raisons'], ['aucun match'])

    def test_rapport_public(self):
        d = json.loads((RACINE / 'simulateur' / 'rapport_pente_cases.json').read_text(encoding='utf-8'))
        self.assertEqual(d['paquet'], 317)
        self.assertEqual(set(d['variantes']), set(P.VARIANTES))
        txt = json.dumps(d, ensure_ascii=False).lower()
        for mot in ('march', 'pinnacle', 'cote'):
            self.assertNotIn(mot, txt)

    def test_rien_dans_l_algo(self):
        prod = (RACINE / 'simulateur' / 'pronostics_du_jour.py').read_text(encoding='utf-8')
        self.assertNotIn('pente_cases', prod)


if __name__ == '__main__':
    unittest.main()
