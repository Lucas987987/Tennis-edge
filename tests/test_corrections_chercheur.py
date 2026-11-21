"""Paquet 322 : correction venue du chercheur — Challenger sur terre battue, pente 1,065, et son retrait."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import pronostics_du_jour as P  # noqa: E402
import corrections_chercheur as CC  # noqa: E402

_ACTIVES = P.pente_cases_actives


def match(uid, c, surface, niveau='prudent'):
    return {'uid': uid, 'circuit': c, 'surface': surface, 'combinaison': {'p_home': 0.7},
            'matchs_joues': [40, 400], 'fiabilite': {'niveau': niveau}, 'controle': {}}


class EnPlace(unittest.TestCase):
    def test_fichier(self):
        self.assertEqual(CC.actives(str(RACINE)), [{'id': 'CH_terre', 'circuit': 'CH', 'surface': 'Clay', 'pente': 1.065}])
        doc = json.loads((RACINE / CC.SOURCE).read_text(encoding='utf-8'))
        self.assertIn('200 matchs', doc['regle_retrait'])
        bas = json.dumps(doc, ensure_ascii=False).lower()
        for mot in ('march', 'cote', 'pinnacle'):
            self.assertNotIn(mot, bas)

    def test_cible(self):
        corr = CC.actives(str(RACINE))
        self.assertEqual(CC.pente_du_match({'circuit': 'CH', 'surface': 'Clay'}, corr), (1.065, 'CH_terre'))
        for c, s in (('CH', 'Hard'), ('ATP', 'Clay'), ('WTA', 'Clay'), ('CH', None)):
            self.assertEqual(CC.pente_du_match({'circuit': c, 'surface': s}, corr), (None, None))


class Application(unittest.TestCase):
    def tearDown(self):
        P.pente_cases_actives = _ACTIVES

    def test_seulement_challenger_terre_sans_double_correction(self):
        vus = {}

        def faux(racine, maintenant, uids=None, pentes_forcees=None):
            vus.update(pentes_forcees)
            return {'matchs': [dict(match(u, 'CH', 'Clay'), combinaison={'p_home': 0.72}) for u in uids]}
        doc = {'matchs': [match('a', 'CH', 'Clay'), match('b', 'CH', 'Clay', 'correct'), match('c', 'CH', 'Hard'),
                          match('d', 'ATP', 'Clay'), dict(match('e', 'CH', 'Clay'), combinaison=None)]}
        n = P.appliquer_corrections_niveaux(str(RACINE), doc, None, {}, construire_=faux)
        self.assertEqual(n, 2)
        self.assertEqual(vus['a'], (1.065, 'terre_challenger'))
        self.assertEqual(vus['b'], 1.142)                     # « correct » : sa propre correction, pas les deux
        for u in 'cde':
            self.assertNotIn(u, vus)
        k = {m['uid']: m['fiabilite'].get('correction_niveau') for m in doc['matchs']}
        self.assertEqual(k['a']['source'], CC.SOURCE)
        self.assertEqual(k['a']['correction'], 'CH_terre')
        self.assertEqual(k['a']['pente'], 1.065)
        self.assertEqual(k['a']['p_home_sans_correction'], 0.7)
        self.assertEqual(k['a']['p_home_avec_correction'], 0.72)
        self.assertEqual(k['b']['source'], 'simulateur/correction_niveaux.json')

    def test_nom_affiche(self):
        html = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
        self.assertIn("terre_challenger: L==='fr'?'Challenger sur terre battue (% moins prudent)'", html)

    def test_chercheur_part_de_la_production(self):
        src = (RACINE / 'simulateur' / 'chercheur.py').read_text(encoding='utf-8')
        self.assertIn('corr = CC.actives(racine)', src)
        self.assertIn("'corrections_en_place'", src)


class Retrait(unittest.TestCase):
    def _racine(self, d, n, gagne, ident='CH_terre'):
        os.makedirs(os.path.join(d, 'simulateur'))
        os.makedirs(os.path.join(d, 'Tennis_Edge_Lab', 'live'))
        json.dump({'corrections': [{'id': 'CH_terre', 'circuit': 'CH', 'surface': 'Clay', 'pente': 1.065, 'retire': False}]},
                  open(os.path.join(d, 'simulateur', 'corrections_chercheur.json'), 'w'))
        R = [{'circuit': 'CH', 'reel': {'gagnant': 'home' if gagne(k) else 'away', 'interrompu': None},
              'fiabilite': {'correction_niveau': {'source': CC.SOURCE, 'correction': ident,
                                                  'p_home_avec_correction': 0.72, 'p_home_sans_correction': 0.70}}}
             for k in range(n)]
        json.dump({'matchs': R}, open(os.path.join(d, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), 'w'))

    def test_verdicts(self):
        with tempfile.TemporaryDirectory() as d:
            self._racine(d, 220, lambda k: k % 100 < 60)               # 60 % : plus tranché fait pire
            r, nouveau = CC.suivi(d)
            self.assertEqual(r['CH_terre']['verdict'], 'retirée')
            self.assertTrue(nouveau['corrections'][0]['retire'])
            json.dump(nouveau, open(os.path.join(d, CC.SOURCE), 'w'))
            self.assertEqual(CC.actives(d), [])
        with tempfile.TemporaryDirectory() as d:
            self._racine(d, 220, lambda k: k % 100 < 75)               # 75 % : plus tranché aide
            r, nouveau = CC.suivi(d)
            self.assertEqual(r['CH_terre']['verdict'], 'gardée')
            self.assertIsNone(nouveau)
        with tempfile.TemporaryDirectory() as d:
            self._racine(d, 150, lambda k: k % 100 < 60)
            self.assertEqual(CC.suivi(d)[0]['CH_terre']['verdict'], 'trop tôt')
        with tempfile.TemporaryDirectory() as d:
            self._racine(d, 220, lambda k: k % 100 < 60, ident='autre')  # autre correction : pas comptée
            self.assertEqual(CC.suivi(d)[0]['CH_terre']['n'], 0)

    def test_hebdomadaire(self):
        wf = (RACINE / '.github' / 'workflows' / 'a_ou_b.yml').read_text(encoding='utf-8')
        self.assertIn('python simulateur/corrections_chercheur.py .', wf)
        self.assertIn('simulateur/corrections_chercheur.json', wf[wf.index('git add'):])


if __name__ == '__main__':
    unittest.main()
