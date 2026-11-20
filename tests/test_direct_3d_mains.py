"""Direct et vidéo 3D, paquet 293 (19/11/2026, Lucas : « gros problème au niveau des mains, de la raquette, des
doigts »). Les bouts de doigts restés hors du poing dans le fichier des modèles sont ramenés dans le poing ; le manche
passe dans le poing ; plus de rayures entre peau et bandeau ; bandeau des femmes au-dessus des sourcils."""
import json
import struct
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
G3D = HTML[HTML.index('const G3D = (() => {'):HTML.index('// Vue du direct choisie par le visiteur')]
BIN = RACINE / 'algo' / 'modeles' / 'joueurs3d.bin'


def egares(seuil_cm=1.5):
    """Nombre de sommets de chaque main au-delà du poing, dans le fichier des modèles (même règle que la page)."""
    b = BIN.read_bytes()
    n = struct.unpack('<I', b[4:8])[0]
    J = json.loads(b[8:8 + n])
    B = 8 + n
    noms = J['os']['noms']
    out = {}
    for s, C in ((s, J['corps'][s]['corps']) for s in J['corps']):
        nv = C['n']
        pos = struct.unpack(f'<{nv * 3}f', b[B + C['pos']:B + C['pos'] + nv * 12])
        jnt, wgt = b[B + C['jnt']:B + C['jnt'] + nv * 4], b[B + C['wgt']:B + C['wgt'] + nv * 4]
        for h, sg in ((noms.index('hand_r'), -1), (noms.index('hand_l'), 1)):
            main = [v for v in range(nv) if sum(wgt[v * 4 + k] for k in range(4) if jnt[v * 4 + k] == h) / 255 > 0.5]
            pouce = min(main, key=lambda v: pos[v * 3 + 1])
            seuil = pos[pouce * 3] * sg + seuil_cm / 100
            out[(s, h)] = sum(1 for v in main if pos[v * 3] * sg > seuil)
    return out


class Mains(unittest.TestCase):
    def test_correction_branchee(self):
        self.assertIn('function corrigerMains(pos, nor, jnt, wgt, idx, mains) {', G3D)
        self.assertIn("const mains = [J.os.noms.indexOf('hand_r'), J.os.noms.indexOf('hand_l')];", G3D)
        self.assertIn('corps: prim(J.corps[s].corps, mains), yeux: prim(J.corps[s].yeux)', G3D)
        self.assertIn('const seuil = pos[pouce * 3] * sg + 0.015,', G3D)

    @unittest.skipUnless(BIN.exists(), 'modèles absents')
    def test_le_fichier_a_bien_des_bouts_de_doigts_a_replier(self):
        e = egares()
        self.assertTrue(all(80 <= v <= 200 for v in e.values()), e)              # 121 (hommes) et 131 (femmes) par main

    def test_raquette_dans_le_poing(self):
        self.assertIn("const G = sexe === 'F' ? [-0.065, 0.01, 0.023] : [-0.038, 0.106, 0.016]", G3D)
        self.assertIn('osModele(J[i], pose, LOCO[i], A.sexe)', G3D)
        self.assertIn('function osModele(j, pose, loco, sexe) {', G3D)

    def test_front_et_bandeau(self):
        self.assertIn('if (vB.y > uTenue[0].y - 0.08 && k > 0 && k < 7) k = 0;', G3D)
        self.assertIn("femme ? 1.705 : 1.752", G3D)
        self.assertNotIn('1.668', G3D)

    def test_pouce_replie(self):                                                    # paquet 294
        self.assertIn('let th = Math.atan2(-0.94, -0.35) - Math.atan2(uz, uy);', G3D)
        self.assertIn('let k = Math.min(1, d / 0.012); k = k * k * (3 - 2 * k);', G3D)
        self.assertIn('if (d <= 0 || Math.abs(orig[v * 3] - T[0]) >= 0.025) continue;', G3D)

    def test_rapport(self):
        d = json.loads((RACINE / 'simulateur' / 'rapport_3d_site.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(d['paquet'], 293)
        self.assertIn('mains', d)


if __name__ == '__main__':
    unittest.main()
