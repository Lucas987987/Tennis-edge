"""23/10/2026 : pas de requête d'identité pour les joueurs vus seulement en ITF (non joué)."""
import gzip
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import joueurs_infos as JI  # noqa: E402


class SansITF(unittest.TestCase):
    def test_joueurs(self):
        with tempfile.TemporaryDirectory() as d:
            with gzip.open(os.path.join(d, '2026-10-20.jsonl.gz'), 'wt', encoding='utf-8') as f:
                f.write(json.dumps({'categorie': 'ITF Men', 'home': {'id': 1, 'nom': 'A'}, 'away': {'id': 2, 'nom': 'B'}}) + '\n')
                f.write(json.dumps({'categorie': 'Challenger', 'home': {'id': 3, 'nom': 'C'}, 'away': {'id': 1, 'nom': 'A'}}) + '\n')
            old = JI.FM.DOSSIER
            JI.FM.DOSSIER = d
            try:
                self.assertEqual(set(JI.joueurs_des_feuilles()), {'3', '1'})
            finally:
                JI.FM.DOSSIER = old


if __name__ == '__main__':
    unittest.main()
