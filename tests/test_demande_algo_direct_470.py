"""26/11/2026 (paquet 470) : « Demande à l'algo » en direct — les thèmes Match et Jeux recalculés depuis le score réel
(même moteur que le % en direct), Stats et Historique restent ceux d'avant le match et le disent. Vérifié en
exécutant le vrai code de la page avec Node (scores fictifs)."""
import os
import re
import shutil
import subprocess
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(ICI, '..', 'algo', 'index.html')


def fonction(s, nom):
    i = s.index('function ' + nom + '(')
    j, d = s.index('{', i), 0
    for k in range(j, len(s)):
        d += {'{': 1, '}': -1}.get(s[k], 0)
        if d == 0:
            return s[i:k + 1]


HARNAIS = '''
const logit = p => Math.log(p/(1-p)), sig = z => 1/(1+Math.exp(-z));
const PT_LIVE = {'0':0,'15':1,'30':2,'40':3,'A':4,'AD':4};
let L = 'fr'; const esc = x => String(x);
const LIVE = {par_uid:{}, moteurs:{}, stats:{}, formes:{}};
const sigmaLive = () => 0, pointsServiceLive = () => null, formesLive = () => [];
const QA_LIVE = {maj:null, cache:{}}; const QA_LIVE_N = 4000;
%s
const m = {uid:'u', home:'Joueur Un', away:'Joueur Deux', circuit:'CH', p_home:0.66,
           simulation:{a:0.64, b:0.58, sets_gagnants:2, tb_final:7}};
function essai(sh, sa, ph, pa, serveur){
  LIVE.par_uid.u = {inverse:false, x:{score_home:{sets:sh, point:ph}, score_away:{sets:sa, point:pa}, serveur}};
  QA_LIVE.cache = {};
  const Lv = qaLive(m); if (!Lv) return null;
  const Q = qaCatalogueLive(m, Lv), g = id => Q.find(q => q.id === id);
  return {n: Lv.Z.n, gagne: g('gagne').rep(0).p, deux: g('deux').rep(0).p, set1: g('set1').rep(0),
          tb: g('tb').rep().p, total20: g('total').rep(0, 20).p, remonte: g('remonte').rep(0)};
}
console.log(JSON.stringify([essai([0],[0],'0','0','home'), essai([6,2],[4,1],'30','15','home'),
  essai([4,6],[6,5],'40','0','away'), essai([7,6],[6,6],'3','2',null), essai([6,6],[4,3],'0','0','home')]));
'''


class DemandeEnDirect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = open(PAGE, encoding='utf-8').read()

    def test_branche(self):
        p = self.page
        self.assertIn('data-qa-mode="live"', p)
        self.assertIn('if (QA_LIVE.maj) QA_LIVE.maj();', p)
        self.assertIn("x.theme === 'stats' || x.theme === 'histo'", p)
        self.assertIn('Réponse d’avant le match : elle n’est pas recalculée en direct.', p)
        bloc = p[p.index('function qaLive('):p.index('// 341 — la courbe')]
        for mot in ('fetch(', 'marché', 'Pinnacle'):
            self.assertNotIn(mot, bloc)

    @unittest.skipUnless(shutil.which('node'), 'node absent')
    def test_calcul_depuis_le_score(self):
        js = HARNAIS % '\n'.join(fonction(self.page, f) for f in
                                 ('rng', 'Moteur', 'calibre', 'etatLive', 'setFini', 'moteursLive', 'qaLive',
                                  'qaCatalogueLive', 'court'))
        import json
        out = subprocess.run(['node', '-e', js], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        a, b, c, d, fini = json.loads(out.stdout)
        self.assertEqual(a['n'], 4000)
        self.assertAlmostEqual(a['gagne'], 0.66, delta=0.03)          # 0-0 : le % publié
        self.assertGreater(b['gagne'], a['gagne'])                     # 6-4 2-1 : le favori a avancé
        self.assertEqual(b['set1']['connu'], 'Oui : déjà fait')
        self.assertIn('Ne peut plus arriver', b['remonte']['txt'])
        self.assertEqual(c['deux'], 0)                                 # 1er set perdu : plus de victoire en 2 sets
        self.assertEqual(c['total20'], 1)                              # déjà plus de 20 jeux
        self.assertEqual(d['tb'], 1)                                   # 7-6 déjà joué
        self.assertIsNone(fini)                                        # match fini : pas de mode direct


if __name__ == '__main__':
    unittest.main()
