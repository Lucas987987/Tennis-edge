"""Paquet 323 (21/11/2026, Lucas : « améliorer les coups, la balle, la caméra, le décor ») — 3D du site et des vidéos."""
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
BLOC = HTML[HTML.index('const G3D = (() => {'):HTML.index('// Vue du direct choisie par le visiteur')]


class Balle(unittest.TestCase):
    def test_taille_vue(self):
        self.assertIn("const kB = b ? cl(0.14 * Math.hypot(b.x - eye[0], b.y - eye[1], b.z - eye[2]) * Math.tan((CAPT.fov || 0.6) / 2), 1, 2.6) : 1;", BLOC)
        self.assertIn("if (b) passe({ m: BALLE, spec: 0.5, emis: 0.5 }, chaine(M4.tr(b.x, b.y, b.z), M4.sc(kB, kB, kB)));", BLOC)
        self.assertLess(BLOC.index('const kB = '), BLOC.index('M4.sc(kB, kB, kB)'))

    def test_trainee_continue_et_halo(self):
        self.assertIn('for (let k = 1; k <= 40; k++) { const p = posBalle(t - k * 0.002); if (!p) break;', BLOC)
        self.assertNotIn('TRACE.forEach((p, k) => passe(', BLOC)                 # plus de pointillés
        self.assertIn('const kh = kB * 2.2;', BLOC)

    def test_ombre(self):
        self.assertIn('if (b && b.y < 9) { const so = 0.13 * kB * (1 + 0.2 * b.y);', BLOC)


class Coups(unittest.TestCase):
    def test_sillage_de_raquette(self):
        self.assertIn('noterSillage(i, t, raquette ? M4.pt(raquette, [0, 0.46, 0]) : null);', BLOC)  # centre du tamis
        self.assertIn('if (dtk <= 0 || dd / dtk < 7) continue;', BLOC)          # seulement quand elle va vite
        self.assertIn('while (S.length && t - S[0].t > 0.12) S.shift();', BLOC)


class Camera(unittest.TestCase):
    def test_araignee(self):
        self.assertIn("cam.araignee = src.gagnant === 0 ? -1 : 1;", BLOC)
        i = BLOC.index('if (cam.araignee) {')
        self.assertIn('5.2, ez]', BLOC[i:i + 600])
        self.assertIn('cl(FILM.az + s * 7.5, -HL - 7, HL + 7)', BLOC[i:i + 600])  # jamais dans les tribunes

    def test_le_reste_de_la_realisation_garde(self):
        self.assertIn('cam.dos2 = src.gagnant === 1 ? 1 : -1;', BLOC)          # 2e angle de la balle de match
        self.assertIn("if (cam.inverse) {", BLOC)


class Decor(unittest.TestCase):
    def test_glissades_terre_battue(self):
        self.assertIn("if (!R || E.surface !== 'Clay') return;", BLOC)
        self.assertIn('if (sp < 0.5 || Math.abs(j.z) < 4.5) return;', BLOC)
        self.assertIn("if (E.surface === 'Clay') for (const g of GLISSE.marques) {", BLOC)

    def test_flashs(self):
        self.assertIn('scene.sieges = pos;', BLOC)
        self.assertIn('if (!E.jour && grandPoint && !RAL.actif && scene.sieges', BLOC)
        self.assertIn('if (grandPoint && t !== undefined) flashDepuis = t;', BLOC)          # aussi après le ralenti
        self.assertNotIn('Math.random', BLOC[BLOC.index('const hasard = n =>'):BLOC.index('function dessiner(t, dt)')])


class Regles(unittest.TestCase):
    def test_rien_d_interdit(self):
        bas = BLOC.lower()
        for mot in ('pinnacle', 'gamesetalgo.com'):
            self.assertNotIn(mot, bas)


if __name__ == '__main__':
    unittest.main()
