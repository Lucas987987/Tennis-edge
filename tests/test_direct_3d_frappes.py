"""Direct et vidéo 3D, paquet 296 (19/11/2026) : au contact, la raquette est sur la balle — lissage serré pendant la
frappe, pose ajustée à la hauteur de la balle, point de contact mesuré sur le modèle et tourné avec le joueur."""
import json
import subprocess
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
G3D = HTML[HTML.index('const G3D = (() => {'):HTML.index('// Vue du direct choisie par le visiteur')]


class Frappes(unittest.TestCase):
    def test_lissage_serre_pendant_la_frappe(self):
        self.assertIn("1 - Math.exp(-dt * (cible.coup >= 0.5 && !cible.geste ? 70 : 16))", G3D)

    def test_hauteur(self):
        self.assertIn('function poseCle(nom, u, dy = 0) {', G3D)
        self.assertIn("const HAUT_TAMIS = { cd: 1.0, rv: 1.03, sl: 0.99, vd: 1.38, vr: 1.4 };", G3D)
        self.assertIn("dy = vol.a.y - HAUT_TAMIS[k];", G3D)

    def test_contact_mesure_et_tourne(self):
        self.assertIn('function contactModele(k, y, sexe) {', G3D)
        self.assertIn("if (v.ock !== k) { v.oc = contactModele(k, v.a.y, sexe) || CONTACTS[sexe][k]; v.ock = k; }", G3D)
        self.assertIn("const c = (j.cap || 0) - (i === 0 ? 0 : Math.PI), ox = face * o[0], oz = face * o[1];", G3D)

    def test_baisse_pour_une_balle_basse(self):
        out = subprocess.run(['node', '-e', r'''
const src = require('fs').readFileSync(process.argv[1], 'utf-8');
const a = src.indexOf('const G3D = (() => {'), b = src.indexOf('// Vue du direct choisie par le visiteur');
global.court = n => n; global.esc = x => x; eval(src.slice(a, b).replace('const G3D =', 'global.G3D ='));
const P = G3D._poses, h = p => G3D._squelette(p).raquette[13];
const r = ['cd', 'rv'].map(k => { const f = k === 'cd' ? P.poseCoupDroit : P.poseRevers; return [h(f(0.55, 0)), h(f(0.55, -0.4)), h(f(0.55, 0.4)), f(0.55, -0.4).accroupi > f(0.55, 0).accroupi]; });
console.log(JSON.stringify(r));
''', str(RACINE / 'algo' / 'index.html')], capture_output=True, text=True, check=True).stdout
        for neutre, bas, haut, plie in json.loads(out):
            self.assertLess(bas, neutre - 0.15)
            self.assertGreater(haut, neutre + 0.1)
            self.assertTrue(plie)

    def test_rapport(self):
        d = json.loads((RACINE / 'simulateur' / 'rapport_3d_site.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(d['paquet'], 296)
        self.assertIn('frappes', d)


if __name__ == '__main__':
    unittest.main()
