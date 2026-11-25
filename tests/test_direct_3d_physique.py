"""Direct en 3D, paquet 275 (18/11/2026, Lucas : « la 3D est mauvaise » — mouvements, rendu, réalisme des échanges).

La balle suit une vraie trajectoire (pesanteur, freinage de l'air, effet Magnus : le lift plonge, le slice flotte),
rebondit selon la surface, et l'adversaire la prend derrière sa ligne de fond à hauteur de hanche ou d'épaule.
Pas chassés de côté, juges de ligne et ramasseurs dessinés avec le vrai modèle. Échanges illustratifs : rien de
tout cela ne change le %."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
DEBUT, FIN = 'const G3D = (() => {', '// Vue du direct choisie par le visiteur'
BLOC = HTML[HTML.index(DEBUT):HTML.index(FIN)]

SCENARIO = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf-8');
const a = src.indexOf('const G3D = (() => {'), b = src.indexOf('// Vue du direct choisie par le visiteur');
global.court = n => n; global.esc = x => String(x);
let graine = 12345; Math.random = () => { graine = (graine * 16807) % 2147483647; return graine / 2147483647; };
eval(src.slice(a, b).replace('const G3D =', 'global.G3D ='));
const P = G3D._phys, HL = 23.77 / 2, W = 10.97, out = { surfaces: {}, lift_vs_slice: null, officiels: [], filet: [] };
const rnd = (x, y) => x + (y - x) * Math.random();
for (const surf of ['Hard', 'Clay', 'Grass']) {
  P.surface(surf);
  const r = { n: 0, contact_y: [], contact_z: [], passe: 0, dedans: 0, rebond_vh: [] };
  for (let k = 0; k < 150; k++) {
    const sens = k % 2 ? 1 : -1, a0 = { x: rnd(-3.5, 3.5), y: rnd(0.9, 1.3), z: -sens * (HL + rnd(0.6, 1.8)) };
    const cible = { x: rnd(-3.8, 3.8), y: 0, z: sens * rnd(HL - 5.5, HL - 2.2) };
    const st = P.styleCoup(0, 'echange'), c = P.coupPhysique(a0, cible, st.V, st.s, 'rebond', { hc: rnd(0.85, 1.15) });
    r.n++;
    let hf = null; for (const q of c.vols[0].pts) if (q[3] * sens >= 0) { hf = q[2]; break; }
    if (hf !== null && hf >= P.hauteurFilet(0) + 0.03) r.passe++;
    const imp = c.vols[0].b; if (Math.abs(imp.x) <= W / 2 && sens * imp.z > 0 && sens * imp.z <= HL) r.dedans++;
    if (c.vols[1]) { r.contact_y.push(c.ex.y); r.contact_z.push(Math.abs(c.ex.z)); }
  }
  // vitesse horizontale juste après le rebond, même coup sur chaque surface
  const c = P.coupPhysique({ x: 0, y: 1, z: -13 }, { x: 0, y: 0, z: 9 }, 30, 0.7, 'rebond', { hc: 1 });
  const p = c.vols[1].pts; r.vh_rebond = Math.hypot(p[3][1] - p[0][1], p[3][3] - p[0][3]) / (p[3][0] - p[0][0]);
  out.surfaces[surf] = r;
}
P.surface('Hard');
// même vitesse, même angle : le lift retombe plus court que le slice
const vol = s => P.voler({ x: 0, y: 1, z: -12 }, [0, 30 * Math.sin(0.12), 30 * Math.cos(0.12)], s, [1, 0, 0], null).p[2];
out.lift_vs_slice = [vol(0.7), vol(-0.6)];
// une balle visée « dans le filet » s'arrête au filet
const f = P.coupPhysique({ x: 0, y: 1, z: -12 }, { x: 0, y: 0, z: 0.05 }, 28, 0.6, 'filet');
out.filet = [f.raison, Math.abs(f.ex.z)];
out.officiels = P.officiels().map(o => [o.x, o.z]);
out.pas_chasses = [P.seuilCourse(0), P.laterale(0)];
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which('node'), 'node absent')
class PhysiqueBalle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as d:
            js = Path(d) / 's.js'; js.write_text(SCENARIO, encoding='utf-8')
            r = subprocess.run(['node', str(js), str(RACINE / 'algo' / 'index.html')], capture_output=True, text=True, timeout=120)
            if r.returncode:
                raise AssertionError(r.stderr[-2000:])
            cls.R = json.loads(r.stdout.strip().splitlines()[-1])

    def test_echanges_passent_le_filet_et_tombent_dans_le_court(self):
        for surf, r in self.R['surfaces'].items():
            self.assertGreaterEqual(r['passe'] / r['n'], 0.97, surf)
            self.assertGreaterEqual(r['dedans'] / r['n'], 0.95, surf)

    def test_prise_de_balle_realiste(self):
        # derrière la ligne de fond (au plus 2,8 m), à hauteur de hanche ou d'épaule — plus jamais au-dessus de la tête
        for surf, r in self.R['surfaces'].items():
            ys, zs = sorted(r['contact_y']), sorted(r['contact_z'])
            med = lambda x: x[len(x) // 2]
            self.assertTrue(0.8 <= med(ys) <= 1.6, (surf, med(ys)))
            self.assertLessEqual(max(ys), 2.0, surf)
            self.assertLessEqual(max(zs), 23.77 / 2 + 2.8 + 0.05, surf)
            self.assertTrue(23.77 / 2 - 1 <= med(zs) <= 23.77 / 2 + 2.6, (surf, med(zs)))

    def test_surfaces_differentes(self):
        s = self.R['surfaces']
        self.assertLess(s['Clay']['vh_rebond'], s['Hard']['vh_rebond'])      # la terre freine
        self.assertLess(s['Hard']['vh_rebond'], s['Grass']['vh_rebond'])     # le gazon fuse

    def test_lift_plonge_slice_flotte(self):
        lift, sl = self.R['lift_vs_slice']
        self.assertLess(lift, sl - 1.0)

    def test_balle_dans_le_filet(self):
        raison, z = self.R['filet']
        self.assertEqual(raison, 'filet'); self.assertLess(z, 0.2)

    def test_officiels_hors_du_court(self):
        o = self.R['officiels']
        self.assertEqual(len(o), 12)                                              # 4 juges de ligne, 8 ramasseurs
        for x, z in o:
            self.assertTrue(abs(x) > 10.97 / 2 + 0.5 or abs(z) > 23.77 / 2 + 2, (x, z))

    def test_pas_chasses(self):
        seuil, lat = self.R['pas_chasses']
        self.assertGreaterEqual(seuil, 2.0)


class Statique(unittest.TestCase):
    def test_modele_pour_les_officiels_et_blocs_en_repli(self):
        self.assertIn('function officielsPoses()', BLOC)
        self.assertIn('scene.officiels = {', BLOC)                              # blocs seulement sans le vrai modèle
        self.assertIn('function poseChasse(', BLOC)

    def test_camera_tv_plus_basse(self):
        self.assertIn('tv: { yaw: 0, pitch: 0.31, dist: 21.5', BLOC)   # paquet 285 : un peu plus près

    def test_sol_hors_court_distinct(self):
        import re
        for surf in ('Hard', 'Clay', 'Grass'):
            m = re.search(surf + r": \{ in: '(#[0-9a-f]{6})', out: '(#[0-9a-f]{6})'", BLOC)
            self.assertIsNotNone(m, surf); self.assertNotEqual(m.group(1), m.group(2))

    def test_rien_de_public_interdit(self):
        bas = BLOC.lower()
        for mot in ('pinnacle', 'leovegas', '4casters'):
            self.assertNotIn(mot, bas)


class RapportPublic(unittest.TestCase):
    def test_rapport_sans_nom_ni_mot_interdit_et_regle_de_retrait(self):
        f = RACINE / 'simulateur' / 'rapport_3d_echanges.json'
        txt = f.read_text(encoding='utf-8'); d = json.loads(txt)
        for mot in ('cote', 'pinnacle', 'march', 'sinner', 'alcaraz', 'swiatek', 'sabalenka'):
            self.assertNotIn(mot, txt.lower())
        self.assertFalse(d['retrait_declenche'])
        import importlib.util
        spec = importlib.util.spec_from_file_location('c3d', RACINE / 'simulateur' / 'controle_3d.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        ok = {'passent_le_filet_pct': 100, 'dans_le_court_pct': 100, 'prise_hauteur_mediane_m': 1.1}
        self.assertFalse(m.retrait({'Hard': ok}))
        self.assertTrue(m.retrait({'Hard': ok, 'Clay': {**ok, 'prise_hauteur_mediane_m': 1.9}}))
        self.assertTrue(m.retrait({'Hard': {**ok, 'passent_le_filet_pct': 95}}))


if __name__ == '__main__':
    unittest.main()
