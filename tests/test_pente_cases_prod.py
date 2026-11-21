"""Paquet 318 : pente des cases en Challenger (production) et son retrait."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import pronostics_du_jour as P  # noqa: E402
import fiabilite as FI  # noqa: E402
import pente_cases as PC  # noqa: E402

_ACTIVES = P.pente_cases_actives


def match(uid, c, niveau, n=(40, 400)):
    return {'uid': uid, 'circuit': c, 'combinaison': {'p_home': 0.7}, 'matchs_joues': list(n),
            'fiabilite': {'niveau': niveau}, 'controle': {}}


class Production(unittest.TestCase):
    def tearDown(self):
        P.pente_cases_actives = _ACTIVES

    def test_pente_de_la_case(self):
        a = FI.pente_v3(match('x', 'CH', 'fragile'))
        self.assertIsNotNone(a)
        self.assertLess(a, 1.0)                                                      # Challenger peu documenté : trop confiant
        self.assertIsNone(FI.pente_v3(dict(match('x', 'CH', 'fragile'), matchs_joues=[None, 3])))

    def test_fichier_en_place(self):
        self.assertEqual(P.pente_cases_actives(str(RACINE)), set())                  # paquet 319 : retirée (rejeu comme en production)

    def test_application(self):
        P.pente_cases_actives = lambda racine: {'CH'}                                  # comme si elle était en place
        vus = {}

        def faux_construire(racine, maintenant, uids=None, pentes_forcees=None):
            vus.update(pentes_forcees)
            return {'matchs': [dict(match(u, 'CH', 'x'), combinaison={'p_home': 0.66}) for u in uids]}
        doc = {'matchs': [match('a', 'CH', 'fragile'), match('b', 'CH', 'correct'), match('c', 'ATP', 'fragile')]}
        n = P.appliquer_corrections_niveaux(str(RACINE), doc, None, {}, construire_=faux_construire)
        self.assertEqual(n, 2)
        self.assertEqual(vus['b'], 1.142)                                            # « correct » : sa correction, pas deux
        self.assertAlmostEqual(vus['a'], round(FI.pente_v3(match('a', 'CH', 'fragile')), 4))
        self.assertNotIn('c', vus)                                                   # ATP : rien
        src = {m['uid']: m['fiabilite']['correction_niveau']['source'] for m in doc['matchs'] if m['uid'] in vus}
        self.assertEqual(src, {'a': 'simulateur/pente_cases.json', 'b': 'simulateur/correction_niveaux.json'})

    def test_libelle_neutre(self):
        html = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
        self.assertIn("niveau_fiabilite: L==='fr'?'% étalonné selon la fiabilité du match (Challenger)'", html)


class Retrait(unittest.TestCase):
    def _racine(self, d, n, gagne):
        os.makedirs(os.path.join(d, 'simulateur')); os.makedirs(os.path.join(d, 'Tennis_Edge_Lab', 'live'))
        json.dump({'circuits': {'CH': {'retire': False}}}, open(os.path.join(d, 'simulateur', 'pente_cases.json'), 'w'))
        R = [{'circuit': 'CH', 'reel': {'gagnant': 'home' if gagne(k) else 'away', 'interrompu': None},
              'fiabilite': {'correction_niveau': {'source': 'simulateur/pente_cases.json',
                                                  'p_home_avec_correction': 0.66, 'p_home_sans_correction': 0.72}}} for k in range(n)]
        json.dump({'matchs': R}, open(os.path.join(d, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), 'w'))

    def test_retire_garde_trop_tot(self):
        with tempfile.TemporaryDirectory() as d:
            self._racine(d, 220, lambda k: k % 100 < 80)                 # 80 % : adoucir fait pire
            r, nouveau = PC.suivi(d)
            self.assertEqual(r['CH']['verdict'], 'retirée')
            self.assertTrue(nouveau['circuits']['CH']['retire'])
        with tempfile.TemporaryDirectory() as d:
            self._racine(d, 220, lambda k: k % 100 < 64)                 # 64 % : adoucir aide
            self.assertEqual(PC.suivi(d)[0]['CH']['verdict'], 'gardée')
        with tempfile.TemporaryDirectory() as d:
            self._racine(d, 150, lambda k: k % 100 < 80)
            self.assertEqual(PC.suivi(d)[0]['CH']['verdict'], 'trop tôt')

    def test_hebdomadaire(self):
        wf = (RACINE / '.github' / 'workflows' / 'a_ou_b.yml').read_text(encoding='utf-8')
        self.assertIn('python simulateur/pente_cases.py .', wf)
        self.assertIn('simulateur/pente_cases.json', wf)


if __name__ == '__main__':
    unittest.main()
