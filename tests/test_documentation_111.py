"""Paquet 453 : signal « documentation faible » du Challenger ramené de 1,844 à 1,11 (décision de Lucas, étude 452)."""
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))


class Documentation111(unittest.TestCase):
    def test_pente_en_place(self):
        d = json.load(open(RACINE / 'simulateur' / 'rapport_documentation.json', encoding='utf-8'))
        ch = d['circuits']['CH']
        self.assertEqual(ch['pente'], 1.11)
        self.assertEqual(ch['pente_avant'], 1.844)
        self.assertTrue(ch['adopte'])
        self.assertNotIn('marché', json.dumps(d, ensure_ascii=False))

    def test_lue_comme_en_production(self):
        d = json.load(open(RACINE / 'simulateur' / 'rapport_documentation.json', encoding='utf-8'))
        pentes = {c: v['pente'] for c, v in (d.get('circuits') or {}).items() if v.get('adopte') and v.get('pente', 0) > 1}
        self.assertEqual(pentes, {'CH': 1.11})                 # même filtre que pronostics_du_jour.py

    def test_retrait_toujours_suivi(self):
        import fantomes_circuits as FC
        self.assertIn(('documentation_faible', 'CH'), FC._directs(str(RACINE)))


if __name__ == '__main__':
    unittest.main()
