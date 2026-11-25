"""Paquet 450 : note de fiabilité Challenger réapprise (application immédiate) et son garde-fou hebdomadaire."""
import datetime as dt
import json
import math
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import fiabilite as FI  # noqa: E402
import note_v3_challenger as NC  # noqa: E402
import pronostics_du_jour as P  # noqa: E402


def _sg(z):
    return 1 / (1 + math.exp(-z))


class Decision(unittest.TestCase):
    def test_fichier(self):
        d = json.load(open(RACINE / 'simulateur' / 'note_v3_challenger.json', encoding='utf-8'))
        self.assertEqual(d['paquet'], 450)
        self.assertEqual(set(d['pentes']), {'0', '1', '2', '3', '_circuit'})
        self.assertIn('regle_retrait', d)
        self.assertNotIn('marché', json.dumps(d, ensure_ascii=False))

    def test_note_challenger_et_ancienne(self):
        FI._MODELE_CH.clear()
        if json.load(open(RACINE / 'simulateur' / 'note_v3_challenger.json', encoding='utf-8')).get('retire'):
            self.skipTest('retirée par le garde-fou')
        m = {'circuit': 'CH', 'matchs_joues': [50, 400]}
        self.assertEqual(FI.note_v3(m), 97)                       # pente 1,0337 → 97
        self.assertNotEqual(FI.note_v3(m, ancienne=True), FI.note_v3(m))
        self.assertEqual(FI.note_v3({'circuit': 'CH', 'matchs_joues': [350, 400]}), 78)
        atp = {'circuit': 'ATP', 'matchs_joues': [50, 400]}
        self.assertEqual(FI.note_v3(atp), FI.note_v3(atp, ancienne=True))   # ATP / WTA : rien ne change

    def test_retiree_rend_l_ancienne(self):
        FI._MODELE_CH.clear()
        FI._MODELE_CH['m'] = None
        try:
            m = {'circuit': 'CH', 'matchs_joues': [50, 400]}
            self.assertEqual(FI.note_v3(m), FI.note_v3(m, ancienne=True))
        finally:
            FI._MODELE_CH.clear()


class CorrectionInchangee(unittest.TestCase):
    def test_la_correction_suit_l_ancien_niveau(self):
        doc = {'matchs': [
            {'uid': 'a', 'circuit': 'CH', 'combinaison': {'p_home': .65},
             'fiabilite': {'niveau': 'solide', 'niveau_ancien': 'correct', 'niveau_correction': 'correct'}},
            {'uid': 'b', 'circuit': 'CH', 'combinaison': {'p_home': .6},
             'fiabilite': {'niveau': 'correct', 'niveau_ancien': 'solide', 'niveau_correction': 'solide'}}]}
        appels = []

        def faux(racine, maintenant, uids=None, pentes_forcees=None):
            appels.append((uids, pentes_forcees))
            return {'matchs': [{'uid': 'a', 'circuit': 'CH', 'combinaison': {'p_home': .666}, 'fiabilite': {}}]}
        n = P.appliquer_corrections_niveaux(str(RACINE), doc, dt.datetime(2026, 11, 26), {}, faux)
        self.assertEqual(n, 1)
        self.assertEqual(appels, [({'a'}, {'a': 1.142})])
        f = doc['matchs'][0]['fiabilite']
        self.assertEqual(f['niveau'], 'solide')                                  # l'étiquette affichée est la nouvelle
        self.assertEqual(f['correction_niveau']['niveau'], 'correct')            # la règle de retrait 270 voit l'ancien


class GardeFou(unittest.TestCase):
    def _racine(self, z_nouveau_juste, n=2000):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, 'simulateur'))
        os.makedirs(os.path.join(d, 'Tennis_Edge_Lab', 'live'))
        dec = json.load(open(RACINE / 'simulateur' / 'note_v3_challenger.json', encoding='utf-8'))
        dec.update(retire=False, active_le='2026-11-25')
        json.dump(dec, open(os.path.join(d, 'simulateur', 'note_v3_challenger.json'), 'w', encoding='utf-8'))
        rnd = random.Random(7)
        M = []
        for i in range(n):
            z0 = rnd.gauss(0, 1.5)
            a_vrai = 1.0 if (i % 2 == 0) else 0.5          # moitié des matchs : % justes ; moitié : % trop sûrs
            juste = rnd.random() < _sg(a_vrai * z0)
            # bonne note : 100 sur les % justes, 50 sur les trop sûrs ; mauvaise : 90 partout (« correct »)
            bon = ('solide', 100) if a_vrai == 1.0 else ('fragile', 50)
            mauvais = ('correct', 90)
            (nv, nn), (av, an) = (bon, mauvais) if z_nouveau_juste else (mauvais, bon)
            M.append({'circuit': 'CH', 'debut': '2026-11-30T10:00', 'p_affiche': _sg(z0),
                      'reel': {'gagnant': 'home' if juste else 'away', 'interrompu': None},
                      'fiabilite': {'niveau': nv, 'note': nn, 'niveau_ancien': av, 'note_ancienne': an}})
        M.append({'circuit': 'CH', 'debut': '2026-11-20T10:00', 'p_affiche': .6, 'reel': {'gagnant': 'home'},
                  'fiabilite': {'niveau': 'solide', 'note': 97, 'niveau_ancien': 'fragile',
                                                'note_ancienne': 70}})                       # avant l'activation
        json.dump({'matchs': M}, open(os.path.join(d, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), 'w'))
        return d

    def test_gardee_quand_elle_fait_mieux(self):
        d = self._racine(True)
        c = NC.verifier(d, dt.date(2026, 12, 7))
        self.assertEqual(c["matchs"], 2000)
        self.assertEqual(c['verdict'], 'gardée')
        self.assertFalse(json.load(open(os.path.join(d, NC.FICHIER)))['retire'])

    def test_retiree_quand_elle_fait_pire(self):
        d = self._racine(False)
        c = NC.verifier(d, dt.date(2026, 12, 7))
        self.assertTrue(c['verdict'].startswith('RETIRÉE'))
        self.assertTrue(json.load(open(os.path.join(d, NC.FICHIER)))['retire'])

    def test_trop_tot(self):
        d = self._racine(False, n=150)
        c = NC.verifier(d, dt.date(2026, 12, 7))
        self.assertTrue(c['verdict'].startswith('pas encore jugée'))
        self.assertFalse(json.load(open(os.path.join(d, NC.FICHIER)))['retire'])

    def test_lundi(self):
        wf = (RACINE / '.github' / 'workflows' / 'pronostic.yml').read_text(encoding='utf-8')
        self.assertIn('python simulateur/note_v3_challenger.py . --telegram', wf)
        self.assertIn('git add -- simulateur/note_v3_challenger.json', wf)


if __name__ == '__main__':
    unittest.main()
