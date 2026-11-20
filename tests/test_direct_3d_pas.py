"""Les pas des joueurs 3D (paquet 309, 20/11/2026, Lucas : « pas mal de replacements ou déplacements qui restent
figés »). Sous la vitesse de course, chaque pied est posé au sol et ne glisse pas ; quand le corps s'en éloigne, il
se lève et va se reposer un peu en avant du mouvement. Affichage seulement : le % ne change pas."""
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
const X = G3D._pas(), J = G3D._J, HL = 23.77 / 2, dt = 1 / 60;
const out = {};
for (const [nom, vx, vz] of [['cote', 1.6, 0], ['vite', -2.8, 0], ['recule', 0, -1.2], ['diagonale', 1.0, 0.8], ['lent', 0.4, 0]]) {
  X.PAS[0] = null; J[0].x = 0; J[0].z = -HL - 0.7; J[0].cap = 0;
  let pas = 0, glisse = 0, ecartMax = 0, ecartPied = 0, enAir2 = 0, pre = null;
  for (let k = 0; k < 150; k++) {
    const t = k * dt, bouge = k < 100;
    J[0].vx = bouge ? vx : 0; J[0].vz = bouge ? vz : 0; J[0].x += J[0].vx * dt; J[0].z += J[0].vz * dt;
    const p = G3D._poses.poseAttente(t); p.ecart = 0.36;
    X.pasDe(0, t, dt, p, 1);
    const P = X.PAS[0], M = X.os(J[0], p).M;
    for (const [c, os] of [['D', 11], ['G', 14]]) {
      const f = P[c];
      if (pre && f.u >= 0 && pre[c] < 0) pas++;
      if (pre && f.u < 0 && pre[c] < 0 && Math.hypot(f.x - pre[c + 'x'], f.z - pre[c + 'z']) > 1e-9) glisse++;
      if (f.u < 0) ecartPied = Math.max(ecartPied, Math.hypot(M[os][12] - f.x, M[os][14] - f.z));
      const sd = c === 'D' ? -1 : 1, ix = J[0].x + sd * 0.36, iz = J[0].z + 0.02;
      ecartMax = Math.max(ecartMax, Math.hypot(f.x - ix, f.z - iz));
    }
    if (P.D.u >= 0 && P.G.u >= 0) enAir2++;
    pre = { D: P.D.u, G: P.G.u, Dx: P.D.x, Dz: P.D.z, Gx: P.G.x, Gz: P.G.z };
  }
  const P = X.PAS[0], fin = ['D', 'G'].map(c => P[c].u < 0);
  out[nom] = { pas, glisse, ecartMax, ecartPied, enAir2, fin };
}
// demi-tour sur place : les pieds suivent par petits pas
{ X.PAS[0] = null; J[0].x = 0; J[0].z = -HL - 0.7; J[0].cap = 0; J[0].vx = J[0].vz = 0; let pas = 0, pre = null;
  for (let k = 0; k < 120; k++) { const t = 10 + k * dt; J[0].cap = Math.min(1.2, k * 0.02);
    const p = G3D._poses.poseAttente(t); p.ecart = 0.36; X.pasDe(0, t, dt, p, 1);
    const P = X.PAS[0]; for (const c of ['D', 'G']) if (pre && P[c].u >= 0 && pre[c] < 0) pas++; pre = { D: P.D.u, G: P.G.u }; }
  out.tourne = { pas }; }
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which('node'), 'node absent')
class Pas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as d:
            js = Path(d) / 's.js'; js.write_text(SCENARIO, encoding='utf-8')
            r = subprocess.run(['node', str(js), str(RACINE / 'algo' / 'index.html')], capture_output=True, text=True, timeout=120)
            if r.returncode:
                raise AssertionError(r.stderr[-2000:])
            cls.R = json.loads(r.stdout.strip().splitlines()[-1])

    def test_des_pas_et_aucune_glissade(self):
        for nom, r in self.R.items():
            if nom == 'tourne':
                continue
            with self.subTest(nom=nom):
                self.assertGreaterEqual(r['pas'], 3 if nom == 'lent' else 5)     # le joueur marche, il ne glisse plus
                self.assertEqual(r['glisse'], 0)                                 # un pied posé ne bouge pas
                self.assertLess(r['ecartPied'], 0.03)                            # la jambe atteint bien le pied posé
                self.assertLess(r['ecartMax'], 0.5)                             # le pied ne reste jamais loin derrière
                self.assertEqual(r['fin'], [True, True])                         # à l'arrêt : les deux pieds à terre

    def test_tourner_sur_place(self):
        self.assertGreaterEqual(self.R['tourne']['pas'], 2)

    def test_un_pied_a_la_fois_le_plus_souvent(self):
        for nom, r in self.R.items():
            if nom == 'tourne':
                continue
            self.assertLessEqual(r['enAir2'], 25, nom)


class Statique(unittest.TestCase):
    def test_branchements(self):
        self.assertIn('function pasDe(i, t, dt, p, w)', BLOC)
        self.assertIn('function jambe(p, s, pied, h = 0)', BLOC)
        self.assertIn("const wPas = (cible.geste ? 1 : 1 - cl(cible.coup || 0, 0, 1)) * (1 - cl(LOCO[i].w, 0, 1));", BLOC)
        self.assertIn('p.ecart = lerp(0.155, 0.36, wA);', BLOC)


if __name__ == '__main__':
    unittest.main()
