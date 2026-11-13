"""Direct en 3D (13/11/2026, paquet 258) : terrain, filet et joueurs en perspective (canvas, sans bibliothèque).
Score, serveur et côté de service réels ; échanges illustratifs, annoncés comme tels."""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')

SCENARIO = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf-8');
const a = src.indexOf('const T3D = (() => {'), b = src.indexOf('// Vue du direct choisie par le visiteur');
global.court = n => { const p = String(n).trim().split(/\s+/); return p.length > 1 ? p.slice(1).join(' ') : n; };
global.matchMedia = () => ({ matches: false });
eval(src.slice(a, b).replace('const T3D =', 'global.T3D ='));
const L = 23.77, W = 10.97, HL = L / 2, SL = 6.40;
const sortie = { cas: [] };
for (const [inverse, serveur, ph, pa, setsH, setsA] of [[false, 'home', '0', '0', [6, 3], [4, 2]], [false, 'home', '15', '0', [2], [1]],
    [true, 'home', '30', '15', [4, 2], [6, 3]], [false, 'away', '40', 'A', [6, 5], [4, 5]], [true, 'away', '3', '2', [6, 6], [4, 6]]]) {
  const sh = { sets: setsH, point: ph }, sa = { sets: setsA, point: pa };
  const r = { inverse, x: { serveur, score_home: sh, score_away: sa } };
  for (let essai = 0; essai < 40; essai++) {
    const T = T3D; T._reinit();
    T3D._maj({ home: 'Jannik Sinner', away: 'Carlos Alcaraz', surface: 'Clay' }, r, false);
    const E = T3D._etat;
    const o = T._simuler(0.01);
    const v0 = o.R.vols[0];
    const cas = { srv: E.srv, droite: E.droite, depart: [v0.a.x, v0.a.z], cible: [v0.b.x, v0.b.z], qui: v0.qui,
                  hors: 0, joueurs_hors: 0, alterne: true, h_max: 0 };
    let dernier = null;
    for (const v of o.R.vols) if (v.qui >= 0) { if (dernier !== null && v.qui === dernier) cas.alterne = false; dernier = v.qui; }
    for (let t = 0.05; t < o.R.fin; t += 0.05) {
      const s = T._simuler(t);
      if (s.balle) { cas.h_max = Math.max(cas.h_max, s.balle.y); if (Math.abs(s.balle.x) > W / 2 + 4 || Math.abs(s.balle.z) > HL + 7) cas.hors++; }
      for (const j of s.J) if (Math.abs(j.x) > W / 2 + 2 || Math.abs(j.z) > HL + 4) cas.joueurs_hors++;
    }
    sortie.cas.push(cas);
  }
}
console.log(JSON.stringify(sortie));
"""


@unittest.skipUnless(shutil.which('node'), 'node absent')
class Direct3D(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(SCENARIO)
        out = subprocess.run(['node', f.name, str(RACINE / 'algo' / 'index.html')], capture_output=True, text=True, check=True).stdout
        cls.C = json.loads(out)['cas']

    def groupe(self, k):
        return self.C[k * 40:(k + 1) * 40]

    def test_serveur_et_cote_reels(self):
        # 0-0 Sinner sert (côté égalité) ; 15-0 : avantage ; inverse : la source dit « home » = Alcaraz ;
        # 40-AD : 7 points joués → avantage ; tie-break 3-2 : 5 points → côté gauche
        attendus = [(0, True), (0, False), (1, False), (1, False), (0, False)]
        for k, (srv, droite) in enumerate(attendus):
            for c in self.groupe(k):
                self.assertEqual((c['srv'], c['droite']), (srv, droite), k)
                self.assertEqual(c['qui'], srv)

    def test_service_en_diagonale_dans_le_bon_carre(self):
        for k in range(5):
            for c in self.groupe(k):
                sens = 1 if c['srv'] == 0 else -1
                self.assertAlmostEqual(abs(c['depart'][1]), 23.77 / 2 + 0.15, places=2)
                self.assertEqual(c['depart'][1] < 0, c['srv'] == 0)                 # depuis sa ligne de fond
                self.assertTrue(0 < c['cible'][1] * sens < 6.40)                    # dans le carré de service adverse
                self.assertLess(c['depart'][0] * c['cible'][0], 0)                  # en diagonale
                droite_x = -sens                                                    # droite du serveur sur l'axe x
                self.assertEqual(c['depart'][0] * droite_x > 0, c['droite'])        # égalité à droite, avantage à gauche

    def test_echange_plausible(self):
        for c in self.C:
            self.assertTrue(c['alterne'])
            self.assertEqual(c['hors'], 0)
            self.assertEqual(c['joueurs_hors'], 0)
            self.assertLess(c['h_max'], 9)

    def test_page(self):
        for x in ("T3D.monter(h3, m, r, fini)", "te_direct_vue", "te3d-bascule", "data-vue=\"${v}\""):
            self.assertIn(x, HTML)
        self.assertIn('score réel ; chaque point est rejoué avec son vrai vainqueur', HTML)       # paquet 260
        self.assertIn('les trajectoires sont reconstituées', HTML)
        self.assertIn('real score; each point is replayed with its real winner', HTML)
        bloc = HTML[HTML.index('const T3D = (() => {'):HTML.index('// Vue du direct choisie par le visiteur')]
        for mot in ('marché', 'pinnacle', 'http'):
            self.assertNotIn(mot, bloc.lower())                                     # rien de chargé ailleurs
        for js in re.findall(r'<script>([\s\S]*?)</script>', HTML):
            with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
                f.write(js)
            subprocess.run(['node', '--check', f.name], check=True)


if __name__ == '__main__':
    unittest.main()
