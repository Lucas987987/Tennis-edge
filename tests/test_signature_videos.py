"""Signature des vidéos et des cartes pour X (paquet 310) — depuis le paquet 446 (25/11/2026), l'adresse gamesetalgo.com."""
import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')


class Signature(unittest.TestCase):
    def test_adresse_officielle(self):
        m = re.search(r"const SIGNE = '(.*?)';", HTML)
        self.assertIsNotNone(m)
        self.assertIn('GAMESETALGO.COM', m.group(1))
        self.assertNotRegex(m.group(1).lower(), r'http|//|\.dev|\.io|workers|github')

    def test_partout(self):
        self.assertIn('<div class="f3-fin" hidden></div>${SIGNE}</div>`;', HTML)            # vidéo 3D (et résumé)
        self.assertIn("<div class=\"pied\">${t('c_pied', D.simulations)}</div>${SIGNE}</div>`;", HTML)   # carte de stats
        self.assertIn("${esc(t('b_pied'))}</div>${SIGNE}</div>`;", HTML)                     # carte bilan
        self.assertIn("${esc(t('s_pied'))}</div>${SIGNE}</div>`;", HTML)                     # carte de la semaine
        self.assertIn('.film .te-signe{', HTML)
        self.assertIn('.ca .te-signe{', HTML)


if __name__ == '__main__':
    unittest.main()
