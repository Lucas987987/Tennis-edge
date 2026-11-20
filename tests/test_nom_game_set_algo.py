"""Nouveau nom « Game Set Algo » et domaine gamesetalgo.com (paquet 311, 20/11/2026)."""
import re
import tomllib
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')


class Nom(unittest.TestCase):
    def test_page(self):
        self.assertIn('<title>Game Set Algo', HTML)
        self.assertIn('</span>Game Set Algo <small data-t="marque">', HTML)
        self.assertIn("ANALYSE COMPLÈTE · GAME SET ALGO", HTML)
        # l'ancien nom ne reste que dans des commentaires CSS
        visibles = [l for l in HTML.splitlines() if re.search(r'Tennis Edge|TENNIS EDGE', l) and not l.lstrip().startswith('/*')]
        self.assertEqual(visibles, [])

    def test_adresse_seulement_a_la_demande(self):
        self.assertEqual(HTML.count("v_url:'gamesetalgo.com'"), 2)
        self.assertNotIn('<i></i>GAME SET ALGO.', HTML)


class Domaine(unittest.TestCase):
    def test_worker(self):
        d = tomllib.loads((RACINE / 'workers' / 'algo' / 'wrangler.toml').read_text(encoding='utf-8'))
        self.assertIn({'pattern': 'gamesetalgo.com', 'custom_domain': True}, d['routes'])
        self.assertIn({'pattern': 'www.gamesetalgo.com', 'custom_domain': True}, d['routes'])
        self.assertTrue(d['workers_dev'])                                   # l'ancienne adresse reste en service
        self.assertEqual(d['r2_buckets'][0]['binding'], 'COFFRE')


if __name__ == '__main__':
    unittest.main()
