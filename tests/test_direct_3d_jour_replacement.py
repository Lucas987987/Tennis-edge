"""Direct 3D, paquet 285 (18/11/2026, Lucas : rendu du direct et mouvements des joueurs). Lumière de jour pour les
matchs en plein air entre 8 h et 18 h (heure locale), caméra télé plus proche, et replacement des joueurs entre deux
frappes (ils reviennent vers le milieu, puis partent vers la balle quand l'adversaire frappe)."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
BLOC = HTML[HTML.index('const G3D = (() => {'):HTML.index('// Vue du direct choisie par le visiteur')]

JS = r"""
const fs = require('fs');
const h = fs.readFileSync(process.argv[2], 'utf-8');
const src = h.slice(h.indexOf('const G3D = (() => {'), h.indexOf('// Vue du direct choisie par le visiteur'));
global.court = n => n; global.esc = x => String(x);
let a = 5; Math.random = () => { a = (a * 16807) % 2147483647; return a / 2147483647; };
eval(src.replace('const G3D =', 'global.G3D ='));
const r = s => ({ inverse: false, x: { serveur: 'home', score_home: { sets: [6, 3], point: s }, score_away: { sets: [4, 2], point: '15' } } });
const jour = [];
for (const [meteo, en_salle] of [[{ interieur: false, heure: { h: 15 } }, false], [{ interieur: false, heure: { h: 20 } }, false],
                                 [{ interieur: true, heure: { h: 14 } }, false], [{ interieur: false, heure: { h: 14 } }, true], [null, false]]) {
  G3D._maj({ uid: 'j' + jour.length, home: 'A B', away: 'C D', circuit: 'ATP', surface: 'Hard', meteo, en_salle }, r('0'), false);
  jour.push(G3D._etat.jour);
}
const m = { uid: 'd', home: 'A B', away: 'C D', circuit: 'ATP', surface: 'Clay' };
G3D._reinit(); G3D._maj(m, r('30'), false); G3D.film.point(m, r('30'), 0, { minL: 7, fin: 'coup_droit' });
let t = 0, R = null; const pos = [];
for (let k = 0; k < 500; k++) { const S = G3D._simuler(t); if (!R && S.R) R = S.R; pos.push([t, S.J[0].x, S.J[0].z]); t += 0.05; }
const frappes = R.vols.filter(v => v.qui >= 0).map(v => ({ qui: v.qui, t: v.t, x: v.a.x }));
// au moment où l'adversaire frappe, le joueur 0 s'est rapproché du milieu par rapport à sa dernière frappe
const mesures = [];
for (const f of frappes.filter(f => f.qui === 1).slice(1)) {
  const avant = frappes.filter(g => g.qui === 0 && g.t < f.t).pop(); if (!avant) continue;
  const p = pos.reduce((b, q) => Math.abs(q[0] - f.t) < Math.abs(b[0] - f.t) ? q : b);
  mesures.push([Math.abs(avant.x), Math.abs(p[1])]);
}
console.log(JSON.stringify({ jour, mesures }));
"""


@unittest.skipUnless(shutil.which('node'), 'node absent')
class JourEtReplacement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'j.js'; f.write_text(JS, encoding='utf-8')
            r = subprocess.run(['node', str(f), str(RACINE / 'algo' / 'index.html')], capture_output=True, text=True, timeout=120)
            if r.returncode:
                raise AssertionError(r.stderr[-1500:])
            cls.R = json.loads(r.stdout.strip().splitlines()[-1])

    def test_jour_seulement_en_plein_air_et_en_journee(self):
        self.assertEqual(self.R['jour'], [True, False, False, False, False])

    def test_replacement_vers_le_milieu(self):
        m = self.R['mesures']
        self.assertGreaterEqual(len(m), 2)
        for frappe_x, x_quand_adversaire_frappe in m:
            if frappe_x > 2.5:
                self.assertLess(x_quand_adversaire_frappe, frappe_x - 1.0)


class Statique(unittest.TestCase):
    def test_ambiances_et_camera(self):
        self.assertIn('jour: { fond: [0.53, 0.71, 0.92]', BLOC)
        self.assertIn("if (scene.faisceaux && QUALITE === 'haute' && !E.jour)", BLOC)
        self.assertIn("tv: { yaw: 0, pitch: 0.31, dist: 21.5", BLOC)


if __name__ == '__main__':
    unittest.main()
