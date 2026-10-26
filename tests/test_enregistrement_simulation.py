"""Garde-fous de l'enregistrement local du scénario modal."""
import os
import unittest


class EnregistrementSimulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chemin = os.path.join(os.path.dirname(__file__), '..', 'algo', 'index.html')
        with open(chemin, encoding='utf-8') as f:
            cls.html = f.read()

    def test_bouton_present_et_relie_au_match_affiche(self):
        self.assertIn('id="b-enregistrer"', self.html)
        self.assertIn('bE.onclick = () => enregistrerSimulation(m,bE,fin)', self.html)

    def test_enregistrement_local_avec_consentement(self):
        self.assertIn('navigator.mediaDevices.getDisplayMedia', self.html)
        self.assertIn('preferCurrentTab:true', self.html)
        self.assertIn('new MediaRecorder(flux', self.html)
        self.assertIn('new Blob(chunks,{type})', self.html)
        self.assertIn('a.download=nomVideo(m,extension)', self.html)
        self.assertNotIn('fetch(', self.html.split('async function enregistrerSimulation', 1)[1].split('function boutonSon', 1)[0])

    def test_fin_du_match_arrete_et_telecharge(self):
        self.assertIn("recorder.ondataavailable", self.html)
        self.assertIn('setTimeout(()=>arreterCapture(true),1600)', self.html)
        self.assertIn('a.click(); a.remove()', self.html)
        self.assertIn('URL.revokeObjectURL(url)', self.html)

    def test_annulation_erreur_et_navigation_ne_laissent_pas_de_capture(self):
        self.assertIn("e.name==='NotAllowedError'", self.html)
        self.assertIn('enregistrement_indisponible', self.html)
        self.assertIn('if (capture) arreterCapture(false)', self.html)
        self.assertIn('flux.getTracks().forEach(p=>p.stop())', self.html)

    def test_enregistrement_relance_le_meme_scenario_modal(self):
        self.assertIn('if (borne) borne.jouer()', self.html)
        self.assertIn('if (seed == null && traceTop)', self.html)


if __name__ == '__main__':
    unittest.main()
