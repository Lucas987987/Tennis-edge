"""Alertes (21/10/2026) : suivi ROI dans les messages, H14 et H15 envoyés même en
doublon (mention « déjà signalé »), mesure inchangée (le champ `doublon` reste)."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import journal_direct as jd  # noqa: E402
import h13_signal as h13  # noqa: E402
import h14_signal as h14  # noqa: E402
import h15_signal as h15  # noqa: E402

VERDICTS = {'hypotheses': [
    {'code': 'H13', 'cible': 300, 'out_of_sample': {'n': 198, 'n_detectees': 236, 'gains': 88, 'taux': 44.4,
                                                    'seuil': 42.0, 'roi': 6.7, 'pnl': 13.3, 'clv_pin_moyen': -2.5}},
    {'code': 'H15', 'cible': 150, 'out_of_sample': {'n': 31, 'n_detectees': 55, 'gains': 15, 'taux': 48.4,
                                                    'seuil': 37.6, 'roi': 29.0, 'pnl': 9.0, 'clv_pin_moyen': -2.3}},
    {'code': 'H14', 'cible': 166, 'out_of_sample': {'n': 0, 'n_detectees': 3}},
]}
G = {'_home': 'Alpha Un', '_away': 'Beta Deux', '_tour': 'ATP Lyon'}


class Alertes(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        json.dump(VERDICTS, open('verdicts_direct.json', 'w', encoding='utf-8'))
        json.dump({'u1': {'t': '2026-10-21T10:00:00', 'cote': 2.45, 'book': 'unibet', 'envoye': True}},
                  open('h13_signal_state.json', 'w', encoding='utf-8'))

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_suivi_roi_dans_h13(self):
        m = h13.message(G, 'h', 2.45, 'unibet', 2.1, 300)
        self.assertIn('Suivi en direct', m)
        self.assertIn('198/300', m)
        self.assertIn('ROI +6.7 %', m)
        self.assertIn('CLV Pinnacle -2.5 %', m)

    def test_h15_doublon_envoye_avec_mention(self):
        deja = jd.deja_txt('h13', 'u1')
        self.assertEqual(deja, '🔁 Match déjà signalé par H13 (unibet @ 2.45).')
        m = h15.message(G, 'h', 2.45, 'unibet', 2.1, 300, deja=deja)
        self.assertIn('déjà signalé par H13', m)
        self.assertIn('ROI +29.0 %', m)
        self.assertNotIn('déjà signalé', h15.message(G, 'h', 2.45, 'unibet', 2.1, 300))

    def test_h14_sans_pari_denoue(self):
        m = h14.message(G, 'h', 2.0, 'unibet', 2.0, 600, 6.0, deja=jd.deja_txt('h13', 'u1'))
        self.assertIn('aucun pari dénoué', m)
        self.assertIn('3 détection(s)', m)
        self.assertIn('déjà signalé par H13', m)

    def test_statut_et_doublon_conserve(self):
        self.assertEqual(jd.statut_envoi(True, 'h13'), 'envoyé (déjà signalé par h13)')
        self.assertEqual(jd.statut_envoi(False, 'h13'), 'doublon')
        self.assertEqual(jd.statut_envoi(True, ''), 'envoyé')
        self.assertEqual(jd.deja_txt('', 'u1'), '')

    def test_sans_verdicts(self):
        os.remove('verdicts_direct.json')
        self.assertEqual(jd.suivi_txt('H13', 300), [])


if __name__ == '__main__':
    unittest.main()
