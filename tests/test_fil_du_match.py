"""Fil du match en direct (13/11/2026, paquet 257) : le récit tiré du point par point, du score en direct et des
statistiques — breaks, balles sauvées, 0-40, sets, tie-breaks, jeux à rallonge, séries, aces, doubles fautes."""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')

PREPARER = r"""
import fs from 'node:fs';
const src = fs.readFileSync(process.argv[2], 'utf-8');
function fn(name){
  const i = src.indexOf('function ' + name + '(');
  if (i < 0) throw new Error(name);
  let k = src.indexOf('{', i), d = 0;
  for (; k < src.length; k++){ const c = src[k]; if (c === '{') d++; else if (c === '}') { d--; if (!d) break; } }
  return src.slice(i, k+1);
}
function trad(debut, fin){
  const a = src.indexOf(debut), b = src.indexOf(fin, a);
  return src.slice(src.lastIndexOf('\n', a), b);
}
const FR = trad("fl_titre:'Fil du match'", "lv_imp_BM:(n,ok)=>`Balle de match");
const EN = trad("fl_titre:'Match feed'", "lv_imp_BM:(n,ok)=>`Match point");
const code = `
export const TR = { fr: {${FR} lv_set:n=>\`\${n}e set\`, lv_set1:'1er set'}, en: {${EN} lv_set:n=>\`Set \${n}\`, lv_set1:'Set 1'} };
export const ETAT = { L: 'fr' };
const t = (k, ...a) => { const v = TR[ETAT.L][k]; return typeof v === 'function' ? v(...a) : v; };
const court = n => { const p = String(n).trim().split(/\\s+/); return p.length>1 ? p.slice(1).join(' ') : n; };
const esc = x => String(x).replace(/</g, '&lt;'); const pc0 = p => Math.round(100*p) + ' %';
export const LIVE = { filSt: {}, filTout: false, points: {} };
function pAvecPoints(){ return 0.5; }
${fn('detailJeu')}
${fn('derouleLive')}
${fn('noterFilStats')}
${fn('enjeuDirect')}
${fn('filDuMatch')}
${fn('rendFil')}
export { derouleLive, filDuMatch, rendFil, enjeuDirect, noterFilStats };`;
fs.writeFileSync(process.argv[3], code);
"""

SCENARIO = r"""
const M = await import(process.argv[2]);
const sortie = {};
const m = { uid: 'u', home: 'Jannik Sinner', away: 'Carlos Alcaraz', p_home: 0.55, simulation: { sets_gagnants: 2 } };
// orientation du site : home = Sinner ; dans TennisApi (inverse) Sinner est « away » → les 1/2 et H/A s'échangent
const jeuxSite = [
  [1,1,1,'HHHH',1], [1,2,2,'AAHHHH',1], [1,3,1,'AAAHHHHH',1], [1,4,2,'AAAA',2], [1,5,1,'HAHAHAHAHAAA',2],
  [1,6,2,'AAAA',2], [1,7,1,'HHHH',1], [1,8,2,'HHHH',1], [1,9,1,'AAAA',2], [1,10,2,'HHHAH',1],
  [2,1,1,'HHHH',1], [2,2,2,'AAAA',2], [2,3,1,'HHHH',1], [2,4,2,'AAAA',2], [2,5,1,'HHHH',1], [2,6,2,'HHH', null]];
const inverser = J => J.map(([s, g, sv, q, v]) => [s, g, 3 - sv, [...q].map(c => c === 'H' ? 'A' : 'H').join(''), v ? 3 - v : null]);
const direct = inv => ({ inverse: inv, x: { serveur: inv ? 'home' : 'away',
  score_home: inv ? { sets: [4, 3], gagnes: 0, point: '30' } : { sets: [6, 2], gagnes: 1, point: '40' },
  score_away: inv ? { sets: [6, 2], gagnes: 1, point: '40' } : { sets: [4, 3], gagnes: 0, point: '30' } } });
for (const [cle, inv] of [['droit', false], ['inverse', true]]) {
  M.ETAT.L = 'fr';
  const r = direct(inv), J = inv ? inverser(jeuxSite) : jeuxSite;
  M.LIVE.filSt = {}; M.LIVE.points.u = J.slice(0, 3);
  const hA = inv ? 2 : 0, aA = inv ? 0 : 2;                         // index TennisApi de Sinner / Alcaraz
  const av = { aces: [0,0,0,0], doubleFaults: [0,0,0,0] }, ap = { aces: [0,0,0,0], doubleFaults: [0,0,0,0] };
  ap.aces[hA] = 1; ap.doubleFaults[aA] = 2;
  M.noterFilStats('u', r, av, ap);
  const ab = { aces: [0,0,0,0], doubleFaults: [0,0,0,0] }; ab.aces[hA] = 40;   // saut incohérent : ignoré
  M.noterFilStats('u', r, ap, ab);
  const dr = M.derouleLive(m, r, J);
  sortie[cle] = M.filDuMatch(m, r, dr, M.LIVE.filSt.u, false);
  sortie[cle + '_html'] = M.rendFil(m, r, dr, false);
  M.ETAT.L = 'en';
  sortie[cle + '_en'] = M.filDuMatch(m, r, dr, M.LIVE.filSt.u, false).map(x => x.txt);
}
// match terminé : 6-4 6-0
M.ETAT.L = 'fr'; M.LIVE.filSt = {};
const fin = jeuxSite.slice(0, 10).concat([[2,1,1,'HHHH',1],[2,2,2,'HHHH',1],[2,3,1,'HHHH',1],[2,4,2,'HHHH',1],[2,5,1,'HHHH',1],[2,6,2,'HHHH',1]]);
const rf = direct(false);
sortie.fini = M.filDuMatch(m, rf, M.derouleLive(m, rf, fin), [], true);
// tie-break au 2e set
const tb = jeuxSite.slice(0, 10);
for (let g = 1; g <= 12; g++) tb.push([2, g, g % 2 ? 1 : 2, g % 2 ? 'HHHH' : 'AAAA', g % 2 ? 1 : 2]);
tb.push([2, 13, 1, 'HAHAHAHAHAHHH', 1]);
sortie.tb = M.filDuMatch(m, rf, M.derouleLive(m, rf, tb), [], true).map(x => x.txt);
console.log(JSON.stringify(sortie));
"""


@unittest.skipUnless(shutil.which('node'), 'node absent')
class FilDuMatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as d:
            prep, mod, sc = Path(d, 'prep.mjs'), Path(d, 'mod.mjs'), Path(d, 'sc.mjs')
            prep.write_text(PREPARER, encoding='utf-8')
            sc.write_text(SCENARIO, encoding='utf-8')
            subprocess.run(['node', str(prep), str(RACINE / 'algo' / 'index.html'), str(mod)], check=True)
            out = subprocess.run(['node', str(sc), mod.as_uri()], capture_output=True, text=True, check=True).stdout
        cls.S = json.loads(out)

    def textes(self, cle):
        return [x['txt'] for x in self.S[cle]]

    def test_recit_du_premier_set(self):
        T = self.textes('droit')
        for attendu in ('Jeu blanc de Sinner : 1-0',
                        'Break ! Sinner prend le service d’Alcaraz : 2-0',
                        'Sinner revient de 0-40 et tient son service : 3-0',
                        'Jeu à rallonge : 3 égalités, 12 points ; Alcaraz finit par breaker : 3-2',
                        'Break ! Alcaraz prend le service de Sinner : 3-2',
                        'Alcaraz sauve une balle de set',
                        'Sinner remporte le 1er set 6-4'):
            self.assertIn(attendu, T)
        self.assertLess(T.index('Alcaraz sauve une balle de set'), T.index('Sinner remporte le 1er set 6-4'))

    def test_en_ce_moment_depuis_le_score_en_direct(self):
        dernier = self.S['droit'][-1]
        self.assertEqual(dernier['tag'], 'now')
        self.assertEqual(dernier['txt'], 'Balle de break pour Sinner (40-30)')

    def test_aces_et_doubles_fautes_entre_deux_mises_a_jour(self):
        T = self.textes('droit')
        self.assertIn('Ace de Sinner (1er du match)', T)
        self.assertIn('2 doubles fautes d’Alcaraz (2 dans le match)', T)
        self.assertFalse([x for x in T if '40' in x and 'ace' in x.lower()], 'saut de 39 aces en une minute : ignoré')
        ace = next(x for x in self.S['droit'] if x['tag'] == 'ace')
        self.assertEqual(ace['g'], 3)                                     # placé dans le jeu en cours quand il est vu

    def test_meme_recit_quel_que_soit_le_sens_de_la_source(self):
        self.assertEqual(self.textes('droit'), self.textes('inverse'))
        self.assertEqual(self.S['droit_en'], self.S['inverse_en'])

    def test_anglais(self):
        self.assertIn('Sinner wins Set 1 6-4', self.S['droit_en'])
        self.assertIn('Break point for Sinner (40-30)', self.S['droit_en'])

    def test_match_termine_et_tie_break(self):
        T = [x['txt'] for x in self.S['fini']]
        self.assertEqual(T[-1], 'Victoire de Sinner : 6-4 6-0')
        self.assertFalse([x for x in self.S['fini'] if x['tag'] == 'now'])
        self.assertIn('Sinner enchaîne 7 jeux de suite', T)
        self.assertIn('Victoire de Sinner : 6-4 7-6', self.S['tb'])

    def test_rendu_court_puis_tout_le_fil(self):
        h = self.S['droit_html']
        self.assertLessEqual(h.count('<li'), 10)
        self.assertIn('Tout le fil (', h)
        self.assertIn('le fil ne change pas le %', h)
        self.assertTrue(h.split('<li', 2)[1].startswith(' class="fl-now"'))      # « en ce moment » en tête

    def test_textes_publics_propres(self):
        bloc = HTML[HTML.index("fl_titre:'Fil du match'"):HTML.index("lv_imp_BM:(n,ok)=>`Balle de match")]
        for mot in ('marché', 'cote', 'pinnacle', 'value', 'pari'):
            self.assertNotIn(mot, bloc.lower())

    def test_page_valide(self):
        js = re.search(r'<script>([\s\S]*?)</script>', HTML).group(1)
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(js)
        subprocess.run(['node', '--check', f.name], check=True)


if __name__ == '__main__':
    unittest.main()
