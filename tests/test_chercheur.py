"""Chercheur automatique (paquet 320, 21/11/2026) : règle écrite avant, rejeu comme en production, rien dans l'algo."""
import datetime as dt
import json
import math
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import chercheur as C  # noqa: E402

SRC = (RACINE / 'simulateur' / 'chercheur.py').read_text(encoding='utf-8')


def v(**k):
    x = {'rang': None, 'qualifie': False, 'invite': False, 'domicile': False, 'experience': 0, 'gaucher': False,
         'droitier': True, 'n_elo': 50, 'repos': None, 'charge14': 0}
    x.update(k)
    return x


class Regle(unittest.TestCase):
    def test_regle_ecrite_avant(self):
        self.assertIn("RÈGLE ÉCRITE LE 21/11/2026, AVANT DE REGARDER LES RÉSULTATS", SRC)
        self.assertEqual((C.MIN_JUGES, C.MARGE, C.MIN_ERREURS_TYPES), (1000, 0.001, 3.3))
        self.assertIn('MÊME SENS', C.regle())
        # le Challenger n'est jugé que là où l'Elo est nourri des résultats ITF hommes (juin 2024 et après)
        self.assertGreaterEqual(C.PERIODES['CH'][0][0], dt.date(2025, 1, 1))
        self.assertEqual(C.PERIODES['ATP'][1][0], dt.date(2023, 1, 1))

    def test_decalages(self):
        D = C.DECALAGES
        self.assertAlmostEqual(D['écart de classement'](v(rang=50), v(rang=200)), 2.0)
        self.assertAlmostEqual(D['jours de repos'](v(repos=30), v(repos=7)), 2.0)        # borné à 21 jours
        self.assertEqual(D['jours de repos'](v(), v(repos=7)), 0.0)
        self.assertEqual(D['gaucher contre droitier'](v(gaucher=True, droitier=False), v()), 1.0)
        self.assertAlmostEqual(D['expérience'](v(experience=99), v(experience=9)), math.log(10))

    def test_verdict(self):
        bon = {'matchs': 2000, 'gain': 0.002, 'erreurs_types': 3.5}
        self.assertEqual(C._verdict(bon, True), [])
        self.assertEqual(len(C._verdict(dict(bon, erreurs_types=3.0), True)), 1)
        self.assertEqual(len(C._verdict(bon, False)), 1)

    def test_message(self):
        doc = {'genere_le': '2026-11-23T05:41:00', 'pistes_testees': 3, 'candidates': 0, 'pistes': []}
        self.assertIn('aucune candidate', C.message(doc))

    def test_rapport_public(self):
        d = json.loads((RACINE / 'simulateur' / 'rapport_chercheur.json').read_text(encoding='utf-8'))
        self.assertEqual(d['paquet'], 320)
        self.assertGreater(d['pistes_testees'], 50)
        txt = json.dumps(d, ensure_ascii=False).lower()
        for mot in ('march', 'pinnacle', 'cote'):
            self.assertNotIn(mot, txt)

    def test_rien_dans_l_algo_et_workflow(self):
        prod = (RACINE / 'simulateur' / 'pronostics_du_jour.py').read_text(encoding='utf-8')
        self.assertNotIn('chercheur', prod)
        wf = (RACINE / '.github' / 'workflows' / 'chercheur.yml').read_text(encoding='utf-8')
        for k in ('/resultats_itf/', '/scripts/resultats_itf.py', '--telegram', "cron: '41 5 * * 1'", 'TELEGRAM_CHAT_ID'):
            self.assertIn(k, wf)
        self.assertNotIn('--force', wf)


if __name__ == '__main__':
    unittest.main()
