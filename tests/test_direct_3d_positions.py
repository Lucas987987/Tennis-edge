"""Direct et vidéo 3D, paquet 295 (19/11/2026, Lucas : « améliorer les mouvements et déplacements ; la position de
pause n'est pas bonne »). Position d'attente de tennis pendant l'échange, position relâchée entre les points."""
import json
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
G3D = HTML[HTML.index('const G3D = (() => {'):HTML.index('// Vue du direct choisie par le visiteur')]


def bloc(debut):
    i = G3D.index(debut)
    return G3D[i:G3D.index('\n  }\n', i)]


class Positions(unittest.TestCase):
    def test_attente(self):
        a = bloc('function poseAttente(t) {')
        self.assertIn('[p.hancheD, p.genouD] = jambe(p, -1, [-0.36, 0.02]); [p.hancheG, p.genouG] = jambe(p, 1, [0.36, 0.02]);', a)
        self.assertIn('p.accroupi = 0.17 + b; p.tronc = [0.4, 0, 0];', a)
        self.assertIn('p.epD = [0.164, 0.561, 1.221]; p.coudeD = 1.231; p.poignetD = [-1.102, 0, -1.085];', a)
        self.assertIn('p.epG = [-1.533, -0.213, 0.14]; p.coudeG = -0.033;', a)

    def test_repos_entre_les_points(self):
        r = bloc('function poseRepos(t) {')
        self.assertIn('p.accroupi = 0.02 + r * 0.3;', r)
        self.assertIn('p.epD = [0.117, 1.473, 0.328];', r)
        self.assertIn('const base = wA >= 1 ? poseAttente(t) : wA <= 0 ? poseRepos(t) : melange(poseRepos(t), poseAttente(t), wA);', G3D)
        self.assertIn('(E.dernier ? 1 - cl((t - E.dernier.t) / 0.8, 0, 1) : 0)', G3D)

    def test_course_et_pas_chasses(self):
        self.assertIn('p.piedD = p.piedG = -0.3; p.poignetD = [0.4, 0, 0.7];', G3D)          # la course garde son poignet
        c = bloc('function poseChasse(t, vl) {')
        self.assertNotIn('p.epD =', c)                                                     # raquette devant, à deux mains

    def test_rapport(self):
        d = json.loads((RACINE / 'simulateur' / 'rapport_3d_site.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(d['paquet'], 295)
        self.assertIn('positions', d)


if __name__ == '__main__':
    unittest.main()
