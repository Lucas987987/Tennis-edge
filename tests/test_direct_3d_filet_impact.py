"""Direct et vidéo 3D, paquet 292 (19/11/2026) : filet à mailles carrées de 4,5 cm (avant : rayures horizontales vues
de loin) et éclair bref au contact de la raquette."""
import json
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
G3D = HTML[HTML.index('const G3D = (() => {'):HTML.index('// Vue du direct choisie par le visiteur')]


class FiletEtImpact(unittest.TestCase):
    def test_mailles_carrees(self):
        self.assertIn('return toile(64, 64, (c, w, h) => {', G3D)
        self.assertIn('for (let k = 0; k < 4; k++) { c.fillRect(k * 16, 0, 3, h); c.fillRect(0, k * 16, w, 3); }', G3D)
        self.assertIn('const U = x => (x + xP) / 0.18, V = y => y / 0.18;', G3D)
        self.assertNotIn('k * 8 / N * 3', G3D)

    def test_eclair(self):
        self.assertIn('const u = (t - v.t) / 0.12; if (u < 0 || u >= 1) continue;', G3D)
        self.assertIn('if (!(v.qui >= 0)) continue;', G3D)
        i = G3D.index('éclair bref au contact')
        bloc = G3D[i:i + 1200]
        self.assertIn('gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE, gl.ZERO, gl.ONE);', bloc)
        self.assertIn('gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA, gl.ZERO, gl.ONE);', bloc)   # rétabli

    def test_rapport(self):
        d = json.loads((RACINE / 'simulateur' / 'rapport_3d_site.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(d['paquet'], 292)
        self.assertIn('filet', d)


if __name__ == '__main__':
    unittest.main()
