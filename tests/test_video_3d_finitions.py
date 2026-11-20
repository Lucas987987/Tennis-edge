"""Vidéo et direct 3D, paquet 288 (19/11/2026, Lucas : « on est bon sur le temps de création des vidéos. On doit encore
améliorer la 3D »). Vidéo en pleine définition, caméra télé plus proche qui suit la balle, balle de match rejouée sous
deux angles, gros plans jamais masqués par un officiel, ramasseurs du fond sortis du cadre, poussière plus fine."""
import json
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
G3D = HTML[HTML.index('const G3D = (() => {'):HTML.index('// Vue du direct choisie par le visiteur')]
FILM = HTML[HTML.index('async function filmDuJour('):HTML.index('/* ───────────── carte de stats (?carte=1)')]


class Finitions(unittest.TestCase):
    def test_pleine_definition(self):
        self.assertIn('FILM.echelle = o.echelle || 0.67;', G3D)
        self.assertIn("echelle: Number(Q.get('echelle') || 0.67)", FILM)
        self.assertNotIn('|| 1;', G3D[G3D.index('FILM.echelle ='):][:40])

    def test_camera_tele(self):
        self.assertIn('Object.assign(VUES.tv, { pitch: 0.27, dist: 22.5 });', G3D)
        self.assertIn('cl(bv.x * 0.5, -3.4, 3.4)', G3D)
        self.assertIn('cl(bv.z * 0.1, -1.2, 1.2)', G3D)
        self.assertNotIn('window.__P', G3D)

    def test_deux_angles_balle_de_match(self):
        self.assertIn('RAL.src.grand && RAL.src.rejouer', G3D)
        self.assertIn("RAL.prevu = { at: t, R: RAL.src, angle: 2 }", G3D)
        self.assertIn('cam.dos2 = src.gagnant === 1 ? 1 : -1', G3D)
        self.assertIn('finRalenti(t)', G3D)
        self.assertIn('await attendre(e => !e.ralenti, 26000)', FILM)            # les deux ralentis tiennent

    def test_gros_plans_degages(self):
        self.assertIn('if (masque(OFFICIELS[k].x, OFFICIELS[k].z)) return;', G3D)
        self.assertIn('sx = j.x > 0.5 ? -1 : 1', G3D)
        self.assertIn('return { vp, lvp, eye, cible };', G3D)

    def test_ramasseurs_du_fond(self):
        self.assertNotIn('s * 3.2, HL + 4.6', G3D)
        self.assertEqual(G3D.count('s * (W / 2 + 0.9), HL + 4.6'), 2)              # blocs et vrai modèle au même endroit

    def test_rapport(self):
        d = json.loads((RACINE / 'simulateur' / 'rapport_3d_site.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(d['paquet'], 288)
        texte = json.dumps(d['video'], ensure_ascii=False).lower() + d['ramasseurs_du_fond'] + d['poussiere_terre_battue']
        for mot in ('cote', 'pinnacle', 'march', 'value'):
            self.assertNotIn(mot, texte)

    def test_rien_d_interdit_dans_le_film(self):
        bas = (FILM + G3D[G3D.index('const FILM = {'):]).lower()
        for mot in ('pinnacle', 'march', 'value'):
            self.assertNotIn(mot, bas)


if __name__ == '__main__':
    unittest.main()
