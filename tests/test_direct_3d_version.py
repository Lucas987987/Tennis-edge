"""Direct 3D du site (paquet 281, 18/11/2026) : Lucas voyait des juges de ligne et des ramasseurs en blocs, signe que
les modèles 3D des personnages n'étaient pas chargés sur son téléphone. Le chargement est retenté 3 fois, et une
petite étiquette dit la version du moteur et si les joueurs 3D sont chargés."""
import json
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
BLOC = HTML[HTML.index('const G3D = (() => {'):HTML.index('// Vue du direct choisie par le visiteur')]


class VersionEtModeles(unittest.TestCase):
    def test_trois_essais(self):
        self.assertIn('for (let essai = 0; essai < 3; essai++)', BLOC)
        self.assertIn("{ cache: 'reload' }", BLOC)
        self.assertIn("MOD.etat = 'absent'; MOD.erreur", BLOC)

    def test_etiquette(self):
        self.assertIn("const VERSION_3D = 'v429';", BLOC)
        self.assertIn('stop.abort(), 25000', BLOC)                                # un essai bloqué abandonne
        self.assertIn("MOD.etat === 'absent' && MOD.erreur ?", BLOC)            # la cause s'affiche
        self.assertIn("verEl.className = 'g3d-ver'", BLOC)
        for k in ('g3_mod_ok', 'g3_mod_charge', 'g3_mod_absent'):
            self.assertEqual(HTML.count(k + ':'), 2, k)                          # français et anglais
        self.assertIn('.g3d-ver{', HTML)
        self.assertIn('body.video .film .g3d > :not(canvas){display:none}', HTML)   # jamais dans la vidéo

    def test_rapport(self):
        d = json.loads((RACINE / 'simulateur' / 'rapport_3d_site.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(d['paquet'], 281); self.assertEqual(d['version_3d'], 'v429')


if __name__ == '__main__':
    unittest.main()
