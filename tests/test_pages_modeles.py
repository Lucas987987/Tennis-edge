"""Paquet 282 (18/11/2026) : les modèles 3D des personnages n'étaient pas publiés sur GitHub Pages (étiquette du site :
« joueurs simplifiés : modèles 3D indisponibles »). Ils le sont, et le worker ne garde plus une absence en cache."""
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
PAGES = (RACINE / '.github' / 'workflows' / 'pages.yml').read_text(encoding='utf-8')
WORKER = (RACINE / 'workers' / 'algo' / 'worker.js').read_text(encoding='utf-8')


class ModelesPublies(unittest.TestCase):
    def test_pages_copie_les_modeles(self):
        self.assertIn('cp algo/modeles/joueurs3d.bin algo/modeles/LICENCE.txt _site/algo/modeles/', PAGES)
        self.assertIn('test -s _site/algo/modeles/joueurs3d.bin', PAGES)
        self.assertTrue((RACINE / 'algo' / 'modeles' / 'joueurs3d.bin').exists())

    def test_pas_de_404_en_cache(self):
        self.assertIn("cacheTtlByStatus: { '200-299': 86400, '404': 0, '500-599': 0 }", WORKER)


if __name__ == '__main__':
    unittest.main()
