"""Paquet 327 (21/11/2026, Lucas : « officiels vivants, transitions, image plus nette »)."""
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
BLOC = HTML[HTML.index('const G3D = (() => {'):HTML.index('// Vue du direct choisie par le visiteur')]
WF = (RACINE / '.github' / 'workflows' / 'video_simulation.yml').read_text(encoding='utf-8')


class Officiels(unittest.TestCase):
    def test_animes(self):
        self.assertIn('officielsAnimes(tReel).forEach((o, k) =>', BLOC)
        self.assertIn("Math.abs(t - OFF_T) < 1 / 15", BLOC)                                   # 15 fois par seconde au plus
        self.assertIn("nom: 'MX_Assis', u: t / MOD.clips.MX_Assis.dur + k * 0.31", BLOC)      # chacun à son rythme


class Transitions(unittest.TestCase):
    def test_sens_stabilise_et_fondu(self):
        self.assertIn("(L.dirT = (L.dirT || 0) + dt) > 0.12", BLOC)
        self.assertIn("L.prec.f -= dt / 0.2", BLOC)
        self.assertIn("L.brasW = lerp(L.brasW ?? 1, L.capte ? 0 : 1,", BLOC)

    def test_attente_en_douceur(self):
        self.assertIn("else if (P && P.wc > 0.01 && P.nom === 'MX_Idle')", BLOC)

    def test_entree_du_service(self):
        self.assertIn("const we = cl((t - (vol.t - 1.25)) / 0.3, 0, 1);", BLOC)


class Nettete(unittest.TestCase):
    def test_echelle(self):
        vs = (RACINE / 'scripts' / 'video_simulation.py').read_text(encoding='utf-8')
        self.assertIn("ap.add_argument('--echelle'", vs)
        self.assertIn('&echelle=', vs)
        self.assertIn("""--echelle "${{ inputs.echelle || '0.85' }}\"""", WF)
        self.assertIn('--echelle 0.85', (RACINE / '.github' / 'workflows' / 'video_resume.yml').read_text(encoding='utf-8'))
        self.assertIn('timeout-minutes: 100', WF)


if __name__ == '__main__':
    unittest.main()
