"""Essai Blender (paquet 278, 18/11/2026, Lucas : « Installe blender »). Blender s'installe sur la machine de
GitHub, rend notre court et mesure le temps par image ; rien de public sauf les temps."""
import json
import py_compile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
YML = (RACINE / '.github' / 'workflows' / 'essai_blender.yml').read_text(encoding='utf-8')
PY = (RACINE / 'scripts' / 'blender_essai.py').read_text(encoding='utf-8')


class EssaiBlender(unittest.TestCase):
    def test_lancement_a_la_main_seulement(self):
        self.assertIn('workflow_dispatch:', YML)
        self.assertNotIn('schedule:', YML)
        self.assertIn('contents: read', YML)

    def test_rien_de_public_hors_les_temps(self):
        self.assertNotIn('upload-artifact', YML)
        self.assertNotIn('git push', YML)
        self.assertIn('${{ secrets.TELEGRAM_TOKEN }}', YML)
        self.assertIn('GITHUB_STEP_SUMMARY', YML)

    def test_blender_installe_sur_github(self):
        self.assertIn('https://download.blender.org/release/Blender', YML)
        self.assertIn('-P scripts/blender_essai.py', YML)
        self.assertIn('continue-on-error: true', YML)                          # EEVEE sans carte graphique : non bloquant

    def test_eevee_en_opengl_logiciel(self):                                     # paquet 279
        self.assertIn('sudo apt-get update', YML)
        self.assertIn('libgl1-mesa-dri', YML)
        self.assertIn('xvfb-run -a', YML)
        self.assertIn('LIBGL_ALWAYS_SOFTWARE=1', YML)
        self.assertIn('if: inputs.cycles', YML)
        self.assertIn('sc.eevee.taa_render_samples', PY)

    def test_regle_de_decision_ecrite_avant(self):
        self.assertIn("moins de 3 h de machine par langue", YML)

    def test_script(self):
        py_compile.compile(str(RACINE / 'scripts' / 'blender_essai.py'), doraise=True)
        for mot in ('cote', 'pinnacle', 'workers.dev', 'github.io'):
            self.assertNotIn(mot, PY.lower())
        self.assertIn("'video_85s_25ips_heures'", PY)
        self.assertIn('L, W, S, SL = 23.77, 10.97, 8.23, 6.40', PY)            # le vrai court

    def test_rapport_public(self):
        d = json.loads((RACINE / 'simulateur' / 'rapport_essai_blender.json').read_text(encoding='utf-8'))
        self.assertEqual(d['paquet'], 279)
        self.assertEqual(d['essai_1']['cycles_s_par_image']['moyenne'], 44.5)
        self.assertIn('regle_decision', d)


if __name__ == '__main__':
    unittest.main()
