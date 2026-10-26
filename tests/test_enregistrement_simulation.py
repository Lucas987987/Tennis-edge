"""Vérifie le retrait complet de l'enregistrement local des simulations."""
import os
import unittest


class AbsenceEnregistrementSimulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chemin = os.path.join(os.path.dirname(__file__), '..', 'algo', 'index.html')
        with open(chemin, encoding='utf-8') as f:
            cls.html = f.read()

    def test_bouton_et_commandes_enregistrement_absents(self):
        self.assertNotIn('id="b-enregistrer"', self.html)
        self.assertNotIn("getElementById('b-enregistrer')", self.html)
        self.assertNotIn('enregistrer_aide', self.html)
        self.assertNotIn('enregistrement_', self.html)

    def test_capture_du_navigateur_absente(self):
        for code in ('getDisplayMedia', 'MediaRecorder', 'enregistrerSimulation',
                     'arreterCapture', 'capture'):
            with self.subTest(code=code):
                self.assertNotIn(code, self.html)

    def test_commandes_de_simulation_conservees(self):
        self.assertIn('id="b-accel"', self.html)
        self.assertIn('id="b-fin"', self.html)
        self.assertIn('document.getElementById(\'b-accel\').onclick = () => borne.accelerer()', self.html)
        self.assertIn('document.getElementById(\'b-fin\').onclick = () => borne.finir()', self.html)

    def test_rejeu_du_scenario_modal_conserve(self):
        self.assertIn('if (seed == null && traceTop)', self.html)
        self.assertIn('const traceActive = enCoursTop && traceTop', self.html)


if __name__ == '__main__':
    unittest.main()
