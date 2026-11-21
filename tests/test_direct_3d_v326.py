"""Paquet 326 (21/11/2026, Lucas : « utiliser des mouvements de Mixamo ») — attente, pas chassés, recul, gestes, arbitre."""
import json
import struct
import subprocess
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
BLOC = HTML[HTML.index('const G3D = (() => {'):HTML.index('// Vue du direct choisie par le visiteur')]
BIN = RACINE / 'algo' / 'modeles' / 'joueurs3d.bin'
MX = {'MX_Idle', 'MX_StrafeG', 'MX_StrafeD', 'MX_Recul', 'MX_Saut', 'MX_Poing', 'MX_Victoire', 'MX_Joie', 'MX_Decu', 'MX_Non',
      'MX_Abattu', 'MX_Applaudit', 'MX_Assis'}


def entete():
    b = BIN.read_bytes(); n = struct.unpack('<I', b[4:8])[0]
    return b, json.loads(b[8:8 + n]), 8 + n


class Fichier(unittest.TestCase):
    def test_mouvements(self):
        b, J, B = entete()
        self.assertTrue(MX <= set(J['clips']))
        self.assertLess(len(b), 2_000_000)
        for nom in MX:
            c = J['clips'][nom]
            self.assertGreaterEqual(c['nf'], 2, nom)
            self.assertLessEqual(B + c['q'] + c['nf'] * 23 * 8, len(b), nom)
            self.assertLessEqual(B + c['t'] + c['nf'] * 12, len(b), nom)
        self.assertGreater(J['clips']['MX_StrafeG']['vitesse'], 3)                       # vitesse au sol de la boucle
        self.assertEqual(J['clips']['MX_StrafeG']['vitesse'], J['clips']['MX_StrafeD']['vitesse'])   # miroir
        self.assertTrue(J['clips']['MX_Idle']['boucle'] and not J['clips']['MX_Victoire']['boucle'])
        self.assertIn('Mixamo', J['licence'])
        self.assertIn('ne sont pas distribués', (RACINE / 'algo' / 'modeles' / 'LICENCE.txt').read_text(encoding='utf-8'))

    def test_aucun_fichier_mixamo_dans_le_depot(self):
        self.assertEqual([p for p in RACINE.rglob('*.fbx') if '.git' not in p.parts], [])

    def test_quaternions_unitaires(self):
        import numpy as np
        b, J, B = entete()
        for nom in MX:
            c = J['clips'][nom]
            q = np.frombuffer(b, dtype=np.int16, count=c['nf'] * 23 * 4, offset=B + c['q']).reshape(-1, 4) / 32767
            self.assertLess(np.abs(np.linalg.norm(q, axis=1) - 1).max(), 2e-3, nom)


class Moteur(unittest.TestCase):
    def test_branchements(self):
        self.assertIn("fetch('modeles/joueurs3d.bin?v=326')", BLOC)                         # nouveau fichier : nouvelle clé de cache
        self.assertIn("return dir.type === 'gauche' ? [['MX_StrafeG', 1]] : dir.type === 'droite' ? [['MX_StrafeD', 1]] : [['MX_Recul', 1]];", BLOC)
        self.assertIn("(loco.brasW ?? (loco.capte ? 0 : 1))", BLOC)                       # bras en attente (paquet 327 : en douceur)
        self.assertIn("o = { nom: 'MX_Idle'", BLOC)
        self.assertIn("bras: !sert", BLOC)                                                   # le serveur garde la balle en main
        self.assertIn("nom: 'MX_Assis'", BLOC)
        self.assertIn('fin_match: dernier', HTML)

    def test_rendu_avec_mouvements(self):
        S = json.loads(subprocess.run(['node', '-e', r'''
const fs = require('fs'), src = fs.readFileSync(process.argv[1], 'utf-8');
const a = src.indexOf('const G3D = (() => {'), b = src.indexOf('// Vue du direct choisie par le visiteur');
global.court = n => n; global.esc = x => x; eval(src.slice(a, b).replace('const G3D =', 'global.G3D ='));
const f = fs.readFileSync(process.argv[2]), buf = f.buffer.slice(f.byteOffset, f.byteOffset + f.length);
G3D._modele(buf);
const out = {};
for (const [nom, u, boucle] of [['MX_Victoire', 0.5, false], ['MX_Abattu', 0.6, false], ['MX_Idle', 0.3, true], ['MX_Assis', 0.2, true]]) {
  const P = G3D._modele(buf, G3D._poses.poseAttente(0), { w: 0, phase: 0, mix: [], ov: { nom, u, w: 1, boucle, bras: true, jambes: true, tete: true } });
  out[nom] = Array.from(P.skin).every(Number.isFinite) && (!P.raquette || P.raquette.every(Number.isFinite));
}
const C = G3D._modele(buf, G3D._poses.poseAttente(0), { w: 1, phase: 0.4, mix: [['MX_StrafeG', 1]], capte: true });
out.pas = Array.from(C.skin).every(Number.isFinite);
console.log(JSON.stringify(out));
''', str(RACINE / 'algo' / 'index.html'), str(BIN)], capture_output=True, text=True, check=True).stdout)
        self.assertTrue(all(S.values()), S)


if __name__ == '__main__':
    unittest.main()
