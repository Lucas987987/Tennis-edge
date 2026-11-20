"""Drapeaux du post X (04/11/2026) : pays des joueurs tirés des fiches, Russie / Biélorussie sans drapeau."""
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import vitrine as V  # noqa: E402


class Pays(unittest.TestCase):
    def test_pays_le_plus_recent_et_absent_si_inconnu(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'feuilles'))
            for jour, pays in (('2026-10-01', 'ESP'), ('2026-10-20', 'FRA')):
                with gzip.open(os.path.join(d, 'feuilles', f'{jour}.jsonl.gz'), 'wt', encoding='utf-8') as f:
                    f.write(json.dumps({'jour': jour, 'home': {'nom': 'Jean Test', 'pays': pays},
                                        'away': {'nom': 'Ana Essai', 'pays': 'deu'}}) + '\n')
            L = [{'home': 'Jean Test', 'away': 'Ana Essai'}, {'home': 'Inconnu Un', 'away': 'Inconnu Deux'}]
            V.ajouter_pays(L, d)
            self.assertEqual(L[0]['pays'], ['FRA', 'DEU'])
            self.assertNotIn('pays', L[1])

    @unittest.skipUnless(shutil.which('node'), 'node absent')
    def test_drapeaux_js(self):
        html = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
        bloc = re.search(r'const PAYS2 = .*?\nfunction drapeau\(a3\)\{.*?\n\}', html, re.S).group(0)
        js = bloc + "\nconsole.log(JSON.stringify([drapeau('FRA'), drapeau('gbr'), drapeau('RUS'), drapeau('BLR'), drapeau(null), drapeau('XXX')]));"
        out = json.loads(subprocess.run(['node', '-e', js], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(out, ['🇫🇷', '🇬🇧', '', '', '', ''])


if __name__ == '__main__':
    unittest.main()
