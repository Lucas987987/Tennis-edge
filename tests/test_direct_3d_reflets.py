"""Direct et vidéo 3D, paquet 290 (19/11/2026, Lucas : « améliorons encore la 3D »). Reflets des joueurs, des officiels
et de la balle sur les courts durs et les moquettes ; ombre de contact sous chaque joueur ; mise au point du film lue
dans l'image elle-même (le premier gros plan de la vidéo était entièrement flou : la 2e sortie de l'image n'était pas
remplie au début du film)."""
import json
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
G3D = HTML[HTML.index('const G3D = (() => {'):HTML.index('// Vue du direct choisie par le visiteur')]


class Reflets(unittest.TestCase):
    def test_surfaces(self):
        self.assertIn("const REFLET = { Hard: 0.2, Carpet: 0.22 };", G3D)       # terre battue et gazon : aucun
        self.assertIn("const ar = REFLET[E.surface]; if (!post || !ar) return;", G3D)

    def test_miroir_sous_le_sol(self):
        self.assertIn('gl.depthFunc(gl.GREATER); gl.depthMask(false); gl.frontFace(gl.CW); gl.uniform1i(U.uMiroir, 1);', G3D)
        self.assertIn('gl.frontFace(gl.CCW); gl.depthFunc(gl.LESS); gl.depthMask(true); gl.disable(gl.BLEND);', G3D)
        self.assertIn("scene.fixes.forEach((o, k) => { passe(o, M4.id()); if (k === 1) reflets(); });", G3D)
        self.assertIn('if (uMiroir == 1) { n.y = -n.y; a *= clamp(1.0 + vW.y / 1.9, 0.0, 1.0); }', G3D)
        self.assertIn("'uMiroir', 'uProf']) U[k]", G3D)

    def test_ombre_de_contact(self):
        self.assertIn('PLAQUE = maillage(plan(1, 1, [0, 0, 0]));', G3D)
        self.assertIn('for (const j of J) passe({ m: PLAQUE, tex: tc,', G3D)
        self.assertEqual(G3D.count('const CONTACTS ='), 1)                        # pas de doublon de nom (CONTACTS depuis le paquet 296)

    def test_mise_au_point(self):
        self.assertIn("uProf == 1 ? clamp(length(uEye - vW) / 80.0, 0.0, 1.0) : a", G3D)
        self.assertIn('gl.uniform1i(U.uProf, gl.isEnabled(gl.BLEND) ? 0 : 1);', G3D)
        self.assertNotIn('texture(uC, vU).a', G3D)
        self.assertEqual(G3D.count('gl.blendFunc('), 0)                          # les transparents gardent la distance
        self.assertGreaterEqual(G3D.count('gl.ZERO, gl.ONE)'), 4)

    def test_rapport(self):
        d = json.loads((RACINE / 'simulateur' / 'rapport_3d_site.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(d['paquet'], 290)
        self.assertIn(d['version_3d'], ('v290', 'v292', 'v293', 'v294', 'v295', 'v296', 'v299', 'v308', 'v309', 'v310', 'v323', 'v324', 'v326', 'v327', 'v428'))
        self.assertIn('reflets', d)


if __name__ == '__main__':
    unittest.main()
