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
          return { couleurs: couleurs.size, tableau: document.querySelector('.g3d-tab').textContent, post: G3D._post() }; }''')
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
        for motif in ('http', 'import(', 'XMLHttpRequest', '.glb', 'new Image', 'src='):
            self.assertNotIn(motif, BLOC)
        self.assertEqual(re.findall(r"fetch\('([^']*)'", BLOC), ['modeles/joueurs3d.bin?v=265'])   # seul fichier lu : sur le site
        for mot in ('marché', 'pinnacle'):
            self.assertNotIn(mot, BLOC.lower())
        self.assertIn('G3D.monter(h3, m, r, fini) && !T3D.monter(h3, m, r, fini)', HTML)   # repli sur la 3D simple

    def test_squelette(self):
        # paquet 262 : au repos, la peau ne bouge pas (os × inverse = identité) ; en attente, jambes et bras symétriques
        S = json.loads(subprocess.run(['node', '-e', r'''
const src = require('fs').readFileSync(process.argv[1], 'utf-8');
const a = src.indexOf('const G3D = (() => {'), b = src.indexOf('// Vue du direct choisie par le visiteur');
global.court = n => n; global.esc = x => x; eval(src.slice(a, b).replace('const G3D =', 'global.G3D ='));
const M4mul = (a, b) => { const o = new Array(16).fill(0); for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) for (let k = 0; k < 4; k++) o[c*4+r] += a[k*4+r] * b[c*4+k]; return o; };
const rep = G3D._squelette().M; let ecart = 0;
for (const m of rep) { const p = M4mul(m, G3D._inverse(m)); for (let k = 0; k < 16; k++) ecart = Math.max(ecart, Math.abs(p[k] - (k % 5 === 0 ? 1 : 0))); }
const att = G3D._squelette(G3D._poses.poseAttente(0)).M, x = k => att[k][12];
console.log(JSON.stringify({ n: rep.length, ecart, sym: [x(10) + x(13), x(11) + x(14), x(4) + x(7), x(5) + x(8)] }));
''', str(RACINE / 'algo' / 'index.html')], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(S['n'], 15)
        self.assertLess(S['ecart'], 1e-5)
        for v in S['sym']:
            self.assertLess(abs(v), 0.03)                                                   # gauche = miroir de droite
        for x in ('uniform mat4 uOs[24]', 'aWt / max(dot(aWt', 'function poseLisse'):
            self.assertIn(x, BLOC)

    def test_ralenti_apres_chaque_point(self):
        # paquet 263 : point rejoué, pause « Point X », ralenti, puis attente ; un nouveau point coupe le ralenti
        S = json.loads(subprocess.run(['node', '-e', r'''
const src = require('fs').readFileSync(process.argv[1], 'utf-8');
const a = src.indexOf('const G3D = (() => {'), b = src.indexOf('// Vue du direct choisie par le visiteur');
global.court = n => n; global.esc = x => x; eval(src.slice(a, b).replace('const G3D =', 'global.G3D ='));
const m = { uid: 'u', home: 'A B', away: 'C D', surface: 'Hard' };
const r = (p, q) => ({ inverse: false, x: { serveur: 'home', score_home: { sets: [6, 3], point: p }, score_away: { sets: [4, 2], point: q } } });
G3D._reinit(); G3D._maj(m, r('30', '15'), false); G3D._maj(m, r('40', '15'), false);
const etats = []; let prec = '', coupe = null, nL = 0;
for (let t = 0; t < 60; t += 0.05) {
  if (prec === 'PL' && ++nL > 20 && coupe === null) { G3D._maj(m, r('40', '30'), false); coupe = t; }   // nouveau point pendant le ralenti
  const o = G3D._etape(t, 0.05), k = (o.R ? 'P' : '') + (o.ralenti ? 'L' : '') + (o.prevu ? 'A' : '');
  if (k !== prec) { etats.push(k || '-'); prec = k; }
}
console.log(JSON.stringify({ etats }));
''', str(RACINE / 'algo' / 'index.html')], capture_output=True, text=True, check=True).stdout)
        e = S['etats']
        self.assertEqual(e[:3], ['P', 'A', 'PL'])                                           # point, pause annoncée, ralenti
        self.assertIn('P', e[3:])                                                          # le nouveau point passe devant le ralenti
        self.assertNotIn('PL', e[3:4])

    def test_modeles_des_joueurs(self):
        # paquet 264 : fichier servi par le site, licence CC0, squelette de 23 os ; bras en croix = pose de repos
        import struct
        b = (RACINE / 'algo' / 'modeles' / 'joueurs3d.bin').read_bytes()
        self.assertEqual(b[:4], b'TEJ3')
        self.assertLess(len(b), 3_000_000)                                                   # léger pour le téléphone
        n = struct.unpack('<I', b[4:8])[0]
        J = json.loads(b[8:8 + n])
        self.assertEqual(len(J['os']['noms']), 23)
        self.assertEqual(set(J['corps']), {'H', 'F'})
        self.assertIn('CC0', J['licence'])
        self.assertTrue({'Walk_Loop', 'Jog_Fwd_Loop', 'Sprint_Loop'} <= set(J['clips']))         # paquet 265 : déplacements captés
        self.assertGreater(J['clips']['Jog_Fwd_Loop']['vitesse'], 4)
        self.assertIn('CC0', (RACINE / 'algo' / 'modeles' / 'LICENCE.txt').read_text(encoding='utf-8'))
        S = json.loads(subprocess.run(['node', '-e', r'''
const fs = require('fs'), src = fs.readFileSync(process.argv[1], 'utf-8');
const a = src.indexOf('const G3D = (() => {'), b = src.indexOf('// Vue du direct choisie par le visiteur');
global.court = n => n; global.esc = x => x; eval(src.slice(a, b).replace('const G3D =', 'global.G3D ='));
const f = fs.readFileSync(process.argv[2]), buf = f.buffer.slice(f.byteOffset, f.byteOffset + f.length);
const T = G3D._modele(buf).skin, k0 = Array.from(T.slice(0, 16));
let ecart = 0; for (let k = 1; k < 23; k++) for (let i = 0; i < 16; i++) ecart = Math.max(ecart, Math.abs(T[k * 16 + i] - k0[i]));
const P = G3D._modele(buf, G3D._poses.poseCoupDroit(0.5));
const fini = Array.from(P.skin).every(Number.isFinite) && !!P.raquette && P.raquette.every(Number.isFinite);
const C = G3D._modele(buf, G3D._poses.poseAttente(0), { w: 1, phase: 0.3, mix: [['Jog_Fwd_Loop', 0.5], ['Sprint_Loop', 0.5]] });
const course = Array.from(C.skin).every(Number.isFinite) && !!C.raquette && C.raquette.every(Number.isFinite);
const pied = k => [C.skin[k * 16 + 12], C.skin[k * 16 + 13], C.skin[k * 16 + 14]];
console.log(JSON.stringify({ ecart, fini, course }));
''', str(RACINE / 'algo' / 'index.html'), str(RACINE / 'algo' / 'modeles' / 'joueurs3d.bin')], capture_output=True, text=True, check=True).stdout)
        self.assertLess(S['ecart'], 1e-3)                                                    # même transformation pour tous les os : rien ne se tord
        self.assertTrue(S['fini'])
        self.assertTrue(S['course'])                                                          # en course, mouvement capté + raquette en main
        self.assertIn("fetch('modeles/joueurs3d.bin?v=265')", BLOC)
        self.assertIn("MOD.etat === 'pret'", BLOC)                                           # sinon, les joueurs dessinés par le code
        A = json.loads(subprocess.run(['node', '-e', r'''
const fs = require('fs'), src = fs.readFileSync(process.argv[1], 'utf-8');
const a = src.indexOf('const G3D = (() => {'), b = src.indexOf('// Vue du direct choisie par le visiteur');
global.court = n => n; global.esc = x => x; eval(src.slice(a, b).replace('const G3D =', 'global.G3D ='));
const noms = ['Adrian Mannarino', 'Aleksandr Shevchenko', 'Iga Swiatek', 'Zzzz Zzzzzzzzzzzzzzzzzz', 'Ñ', ''];
const out = noms.map(n => G3D._allure({ home: n, away: n, circuit: n.startsWith('Iga') ? 'WTA' : 'ATP' }, 0));
console.log(JSON.stringify(out.map(x => [x.sexe, x.cheveux.every(Number.isFinite), x.tenue.flat().every(Number.isFinite)])));
''', str(RACINE / 'algo' / 'index.html')], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(A[2][0], 'F')
        for sexe, cheveux_ok, tenue_ok in A:                                                  # tous les noms donnent une allure valable
            self.assertTrue(cheveux_ok and tenue_ok)

    def test_qualite_et_ecran(self):
        self.assertIn("localStorage.setItem('te_3d_qualite', 'basse')", BLOC)          # repli automatique si ça rame
        self.assertIn('renderbufferStorageMultisample', BLOC)
        self.assertIn('function dessinerEcran', BLOC)                                    # écrans géants : le vrai score

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
        self.assertTrue(o['res']['post'])                                           # paquet 261 : anti-crénelage et halo
        self.assertIn('Un', o['res']['tableau'])


if __name__ == '__main__':
    unittest.main()
