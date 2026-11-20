"""Paquet 270 : correction du niveau « correct » en Challenger (pente 1,142) et sa règle de retrait automatique."""
import copy
import datetime as dt
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import pronostics_du_jour as P  # noqa: E402
import etude_niveaux_fiabilite as NF  # noqa: E402


def _lg(p):
    return math.log(p / (1 - p))


class EnPlace(unittest.TestCase):
    def test_fichier_challenger_correct(self):
        C = P.corrections_niveaux(str(RACINE))
        self.assertEqual(C, {'CH': {'correct': 1.142}})

    def test_retiree_n_est_plus_lue(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            json.dump({'corrections': {'CH': {'correct': {'pente': 1.142, 'retiree': True}}}},
                      open(os.path.join(d, 'simulateur', 'correction_niveaux.json'), 'w'))
            self.assertEqual(P.corrections_niveaux(d), {})

    def test_pente_appliquee_en_dernier(self):
        src = (RACINE / 'simulateur' / 'pronostics_du_jour.py').read_text(encoding='utf-8')
        self.assertIn("sh_ = dict(sh_ or {}, niveau_fiabilite=(float(pf_) - 1.0) * L0_)", src)
        # logit final = pente × (logit de base + autres signaux) : un 65 % devient ≈ 67,0 %
        p, autres, k = 0.65, 0.0, 1.142
        L0 = _lg(p) + autres
        q = 1 / (1 + math.exp(-(L0 + (k - 1) * L0)))
        self.assertAlmostEqual(q, 1 / (1 + math.exp(-k * _lg(p))))
        self.assertTrue(0.668 < q < 0.671)

    def test_seuls_les_matchs_vises_sont_refaits_et_la_fiabilite_reste(self):
        doc = {'matchs': [
            {'uid': 'a', 'circuit': 'CH', 'combinaison': {'p_home': .65}, 'fiabilite': {'niveau': 'correct', 'note': 70}, 'p_premier': .64},
            {'uid': 'b', 'circuit': 'CH', 'combinaison': {'p_home': .6}, 'fiabilite': {'niveau': 'solide'}},
            {'uid': 'c', 'circuit': 'ATP', 'combinaison': {'p_home': .7}, 'fiabilite': {'niveau': 'correct'}}]}
        appels = []

        def faux_construire(racine, maintenant, uids=None, pentes_forcees=None):
            appels.append((uids, pentes_forcees))
            return {'matchs': [{'uid': 'a', 'circuit': 'CH', 'combinaison': {'p_home': .666}, 'fiabilite': {'niveau': 'solide'}}]}
        n = P.appliquer_corrections_niveaux(str(RACINE), doc, dt.datetime(2026, 11, 18), {}, faux_construire)
        self.assertEqual(n, 1)
        self.assertEqual(appels, [({'a'}, {'a': 1.142})])
        a = doc['matchs'][0]
        self.assertEqual(a['combinaison']['p_home'], .666)
        self.assertEqual(a['fiabilite']['niveau'], 'correct')                  # niveau du pronostic sans correction
        self.assertEqual(a['fiabilite']['correction_niveau']['p_home_sans_correction'], .65)
        self.assertEqual(a['fiabilite']['correction_niveau']['p_home_avec_correction'], .666)
        self.assertEqual(a['p_premier'], .64)
        self.assertEqual(doc['matchs'][1]['combinaison']['p_home'], .6)
        self.assertEqual(doc['matchs'][2]['combinaison']['p_home'], .7)


class Retrait(unittest.TestCase):
    def _M(self, n, avec, sans, gagne):
        return [{'circuit': 'CH', 'niveau': 'correct', 'p_a': avec, 'a_gagne': gagne(k), 'm': {
            'fiabilite': {'niveau': 'correct', 'correction_niveau': {'niveau': 'correct', 'p_home_avec_correction': avec,
                                                                     'p_home_sans_correction': sans}},
            'reel': {'gagnant': 'home' if gagne(k) else 'away'}}} for k in range(n)]

    def _racine(self, d):
        os.makedirs(os.path.join(d, 'simulateur'))
        json.dump({'corrections': {'CH': {'correct': {'pente': 1.142, 'retiree': False}}}},
                  open(os.path.join(d, 'simulateur', 'correction_niveaux.json'), 'w'))

    def test_retiree_si_la_correction_fait_pire(self):
        with tempfile.TemporaryDirectory() as d:
            self._racine(d)
            M = self._M(120, .70, .62, lambda k: k % 5 < 3)                    # réel 60 % : la correction en rajoute
            suivi, nouveau = NF.suivi_corrections(d, M)
        self.assertEqual(suivi['CH|correct']['verdict'], 'retirée')
        self.assertTrue(nouveau['corrections']['CH']['correct']['retiree'])

    def test_gardee_si_elle_aide_et_trop_tot_sous_100(self):
        with tempfile.TemporaryDirectory() as d:
            self._racine(d)
            suivi, nouveau = NF.suivi_corrections(d, self._M(120, .70, .62, lambda k: k % 10 < 7))
            self.assertEqual((suivi['CH|correct']['verdict'], nouveau), ('gardée', None))
            suivi, _ = NF.suivi_corrections(d, self._M(99, .70, .62, lambda k: k % 5 < 3))
            self.assertEqual(suivi['CH|correct']['verdict'], 'trop tôt')

    def test_regle_dans_l_en_tete_et_workflow(self):
        self.assertIn('RETRAIT d\'une correction en place', NF.__doc__)
        wf = (RACINE / '.github' / 'workflows' / 'a_ou_b.yml').read_text(encoding='utf-8')
        self.assertIn('simulateur/correction_niveaux.json', wf)


if __name__ == '__main__':
    unittest.main()
