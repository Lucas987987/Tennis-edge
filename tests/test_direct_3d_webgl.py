"""Direct en 3D, moteur WebGL maison (13/11/2026, paquet 259) : stade, public, arbitre, ramasseurs, joueurs articulés
et animés, ombres. Rien n'est chargé d'ailleurs ; score, serveur et côté réels ; échanges illustratifs."""
import json
import re
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
global.court = n => { const p = String(n).trim().split(/\s+/); return p.length > 1 ? p.slice(1).join(' ') : n; };
global.esc = x => String(x);
eval(src.slice(a, b).replace('const G3D =', 'global.G3D ='));
const HL = 23.77 / 2, W = 10.97;
const out = { cas: [], poses_finies: true, fins: {}, gagnants: [], tirages_ok: true, attente: null };
const finie = p => Object.values(p).every(v => Array.isArray(v) ? v.every(Number.isFinite) : Number.isFinite(v));
const ET = (sh, sa, ph, pa, srv) => G3D._etatDe([sh, sa], [ph, pa], srv);
// qui a gagné le point, d'un état du score au suivant
for (const [x, y] of [[ET([6, 3], [4, 2], '30', '15', 0), ET([6, 3], [4, 2], '40', '15', 0)],
    [ET([6, 3], [4, 2], '40', 'A', 0), ET([6, 3], [4, 2], '40', '40', 0)],
    [ET([6, 3], [4, 2], 'A', '40', 0), ET([6, 3], [4, 2], '40', '40', 0)],
    [ET([6, 5], [4, 4], '40', '30', 0), ET([6, 6], [4, 4], '0', '0', 1)],
    [ET([6, 6], [4, 6], '3', '2', 0), ET([6, 6], [4, 6], '3', '3', 1)],
    [ET([6, 3], [4, 2], '0', '0', 0), ET([6, 5], [4, 2], '0', '0', 0)],
    [ET([6, 3], [4, 2], '15', '0', 0), ET([6, 3], [4, 2], '15', '0', 0)]]) out.gagnants.push(G3D._gagnant(x, y));
for (let k = 0; k < 4000; k++) {
  const sv = G3D._tirage(null, true), rc = G3D._tirage(null, false);
  if (sv === 'doubles_fautes_adverses' || rc === 'aces' || rc === 'services_non_retournes') out.tirages_ok = false;
}
// sans point arrivé : on attend, la balle dans la main du serveur, aucun échange inventé
G3D._reinit();
G3D._maj({ uid: 'x', home: 'Jannik Sinner', away: 'Carlos Alcaraz', surface: 'Hard' },
  { inverse: false, x: { serveur: 'home', score_home: { sets: [6, 3], point: '30' }, score_away: { sets: [4, 2], point: '15' } } }, false);
const at = G3D._simuler(6);
out.attente = { R: at.R, enMain: !!at.enMain, balle: at.balle };
// un vrai point : le score (côté du site : [joueur 1, joueur 2]) passe de AVANT à APRÈS ; on rejoue ce point
for (const [inverse, serveur, avant, apres, sh, sa, g] of [
    [false, 'home', ['30', '15'], ['40', '15'], [6, 3], [4, 2], 0], [false, 'home', ['15', '0'], ['15', '15'], [2], [1], 1],
    [true, 'home', ['30', '15'], ['30', '30'], [4, 2], [6, 3], 1], [false, 'away', ['40', 'A'], ['40', '40'], [6, 5], [4, 5], 0],
    [true, 'away', ['3', '2'], ['4', '2'], [6, 6], [4, 6], 0]]) {
  for (let essai = 0; essai < 40; essai++) {
    G3D._reinit();
    const m = { uid: 'u' + essai + serveur + inverse, home: 'Jannik Sinner', away: 'Carlos Alcaraz', surface: 'Clay' };
    const r = (p) => ({ inverse, x: { serveur, score_home: { sets: sh, point: inverse ? p[1] : p[0] }, score_away: { sets: sa, point: inverse ? p[0] : p[1] } } });
    G3D._maj(m, r(avant), false);
    const srv = G3D._etat.srv, droite = G3D._etat.droite;
    G3D._maj(m, r(apres), false);
    const o = G3D._simuler(0.02), R = o.R;
    const cas = { attendu: g, gagnant: R ? R.gagnant : null, fin: R ? R.fin : null, srv, droite, hors: 0, joueurs_hors: 0, coherent: true };
    if (R) {
      const v0 = R.vols[0], frappes = R.vols.filter(v => v.qui >= 0);
      cas.qui0 = v0.qui; cas.depart = [v0.a.x, v0.a.z]; cas.cible = [v0.b.x, v0.b.z]; cas.faute0 = !!v0.faute;
      const der = frappes[frappes.length - 1];
      const erreur = ['fautes_provoquees', 'fautes_directes_adverses', 'services_non_retournes', 'doubles_fautes_adverses'].includes(R.fin);
      if (R.fin === 'doubles_fautes_adverses') cas.coherent = frappes.length === 2 && frappes.every(v => v.type === 'service' && v.faute && v.qui === 1 - g);
      else if (R.fin === 'aces') cas.coherent = frappes.length === 1 && frappes[0].qui === g;
      else cas.coherent = der.qui === (erreur ? 1 - g : g);
      for (let k = 1; k < frappes.length; k++) if (frappes[k].type !== 'service' && frappes[k].qui === frappes[k - 1].qui) cas.coherent = false;
      out.fins[R.fin] = (out.fins[R.fin] || 0) + 1;
      for (let t = 0.05; t < R.finT + 1; t += 0.05) {
        const s = G3D._simuler(t);
        if (s.balle && (Math.abs(s.balle.x) > W / 2 + 4 || Math.abs(s.balle.z) > HL + 7 || s.balle.y < -0.01)) cas.hors++;
        for (const j of s.J) if (Math.abs(j.x) > W / 2 + 2.5 || Math.abs(j.z) > HL + 4) cas.joueurs_hors++;
        if (!s.poses.every(finie)) out.poses_finies = false;
      }
      cas.annonce = G3D._simuler(R.finT + 1.5).dernier;
    }
    out.cas.push(cas);
  }
}
console.log(JSON.stringify(out));
"""

RENDU = r"""
import asyncio, sys, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'], **({'executable_path': sys.argv[2]} if sys.argv[2] else {}))
        pg = await b.new_page(viewport={'width': 400, 'height': 260})
        erreurs = []; pg.on('pageerror', lambda e: erreurs.append(str(e)))
        await pg.set_content('<div id="h" style="width:400px"></div><style>.g3d-cv{display:block;width:100%;aspect-ratio:16/10}</style>')
        await pg.add_script_tag(content=open(sys.argv[1], encoding='utf-8').read())
        res = await pg.evaluate('''() => { window.requestAnimationFrame = () => 0;
          const r = {inverse:false, x:{serveur:'home', score_home:{sets:[6,3], point:'30'}, score_away:{sets:[4,2], point:'15'}}};
          if (!G3D.monter(document.getElementById('h'), {home:'A Un', away:'B Deux', surface:'Grass'}, r, false)) return null;
          G3D._image(1.5);
          const c = document.querySelector('.g3d-cv'), gl = c.getContext('webgl2'), px = new Uint8Array(4 * 64);
          const couleurs = new Set();
          for (let k = 0; k < 64; k++) { gl.readPixels(Math.floor(c.width * (k % 8 + .5) / 8), Math.floor(c.height * (Math.floor(k / 8) + .5) / 8), 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px.subarray(k * 4)); couleurs.add(px.slice(k * 4, k * 4 + 3).join(',')); }
          return { couleurs: couleurs.size, tableau: document.querySelector('.g3d-tab').textContent }; }''')
        print(json.dumps({'res': res, 'erreurs': erreurs}))
        await b.close()
asyncio.run(main())
"""


@unittest.skipUnless(shutil.which('node'), 'node absent')
class MoteurWebGL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(SCENARIO)
        cls.S = json.loads(subprocess.run(['node', f.name, str(RACINE / 'algo' / 'index.html')], capture_output=True, text=True, check=True).stdout)

    def test_qui_a_gagne_le_point(self):
        # 30-15 → 40-15 ; 40-AD → 40-40 ; AD-40 → 40-40 ; jeu gagné ; tie-break ; deux jeux d'un coup ; rien
        self.assertEqual(self.S['gagnants'], [0, 0, 1, 0, 1, None, None])

    def test_facons_de_gagner_possibles(self):
        self.assertTrue(self.S['tirages_ok'])                                       # pas d'ace au retour, pas de double faute au service
        self.assertGreaterEqual(len(self.S['fins']), 7)

    def test_sans_point_on_attend(self):
        a = self.S['attente']
        self.assertIsNone(a['R'])
        self.assertTrue(a['enMain'])
        self.assertIsNone(a['balle'])

    def test_le_vrai_point_est_rejoue(self):
        for c in self.S['cas']:
            self.assertEqual(c['gagnant'], c['attendu'])                            # le vrai vainqueur
            self.assertEqual(c['qui0'], c['srv'])                                   # le vrai serveur
            sens = 1 if c['srv'] == 0 else -1
            self.assertEqual(c['depart'][0] * -sens > 0, c['droite'])               # le vrai côté (égalité / avantage)
            self.assertLess(c['depart'][0] * c['cible'][0], 0)                      # en diagonale
            if not c['faute0']:
                self.assertTrue(0 < c['cible'][1] * sens < 6.40)                    # dans le carré adverse
            self.assertTrue(c['coherent'], c['fin'])
            self.assertEqual(c['hors'], 0)
            self.assertEqual(c['joueurs_hors'], 0)
            self.assertEqual(c['annonce']['gagnant'], c['attendu'])                 # « Point X » à la fin
        self.assertTrue(self.S['poses_finies'])

    def test_rien_ne_vient_d_ailleurs(self):
        for motif in ('http', 'fetch(', 'import(', 'XMLHttpRequest', '.glb', 'new Image', 'src='):
            self.assertNotIn(motif, BLOC)
        for mot in ('marché', 'pinnacle'):
            self.assertNotIn(mot, BLOC.lower())
        self.assertIn('G3D.monter(h3, m, r, fini) && !T3D.monter(h3, m, r, fini)', HTML)   # repli sur la 3D simple

    def test_page_valide(self):
        for js in re.findall(r'<script>([\s\S]*?)</script>', HTML):
            with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
                f.write(js)
            subprocess.run(['node', '--check', f.name], check=True)

    def test_rendu_webgl(self):
        try:
            import playwright  # noqa: F401
        except ImportError:
            self.skipTest('playwright absent')
        with tempfile.TemporaryDirectory() as d:
            js = Path(d, 'g3d.js')
            js.write_text("function court(n){const p=String(n).trim().split(/\\s+/);return p.length>1?p.slice(1).join(' '):n}\nfunction esc(x){return String(x)}\n"
                          + BLOC.replace('const G3D =', 'window.G3D ='), encoding='utf-8')
            py = Path(d, 'r.py'); py.write_text(RENDU, encoding='utf-8')
            chrome = shutil.which('google-chrome') or ''
            try:
                r = subprocess.run(['python3', str(py), str(js), chrome], capture_output=True, text=True, timeout=120)
            except subprocess.TimeoutExpired:
                self.skipTest('navigateur trop lent')
            if r.returncode != 0:
                self.skipTest('navigateur indisponible : ' + r.stderr[-200:])
            o = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(o['erreurs'], [])
        if o['res'] is None:
            self.skipTest('WebGL 2 indisponible dans ce navigateur')
        self.assertGreater(o['res']['couleurs'], 20)                                # une vraie image, pas un aplat
        self.assertIn('Un', o['res']['tableau'])


if __name__ == '__main__':
    unittest.main()
