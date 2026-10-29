# -*- coding: utf-8 -*-
"""Livraison 113 (29/10/2026) : chaîne courte avant fusion, désaccords WTA, donnees.json allégé, note de fiabilité v2."""
import datetime as dt
import math
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import entrainement_progressif as EP  # noqa: E402
import fiabilite as FI  # noqa: E402
import vitrine as V  # noqa: E402
from backtest_match_simule import ajuster_poids  # noqa: E402


class Chaine(unittest.TestCase):
    def test_workflow(self):
        with open(os.path.join(ICI, '..', '.github', 'workflows', 'appliquer_paquet.yml'), encoding='utf-8') as f:
            w = f.read()
        for x in ('backtest_pronostic.py /tmp/sackmann .', 'pronostics_du_jour.py .', 'vitrine.py .',
                  'validation_vitrine.py .', "PRONOSTICS_MAX: '3'", 'discover -s simulateur/tests', '/tmp/chaine'):
            self.assertIn(x, w)
        a = w.index('Chaîne courte (classement'); b = w.index('Branche, demande de fusion')
        self.assertLess(a, b)                                   # avant la fusion


class Compact(unittest.TestCase):
    def test_somme_et_validation(self):
        D = [{'score': [[6, 0], [6, 0]], 'vainqueur': 0, 'probabilite': 0.6}] + \
            [{'score': [[6, i], [6, 0]], 'vainqueur': 0, 'probabilite': 0.4 / 800} for i in range(800)]
        doc = {'matchs': [{'distribution_scores': D}]}
        V.compacter(doc)
        m = doc['matchs'][0]
        self.assertEqual(len(m['distribution_scores']), 1)
        self.assertAlmostEqual(sum(r['probabilite'] for r in m['distribution_scores']) + m['distribution_reste'], 1.0, places=10)


class DesaccordWTA(unittest.TestCase):
    def test_regle(self):
        rnd, H, exp = random.Random(4), [], {}
        sg = lambda z: 1 / (1 + math.exp(-z))
        for k in range(3000):
            c = ('ATP', 'WTA', 'CH')[k % 3]
            z = rnd.gauss(0, 1)
            ze, zs = z + rnd.gauss(0, .4), z + rnd.gauss(0, .4)
            if c == 'WTA' and rnd.random() < .3:
                zs = -ze                                      # désaccord : en WTA la simulation se trompe
            y = rnd.random() < sg(1.3 * z)
            f = (lambda p: p) if y else (lambda p: 1 - p)
            x = {'circuit': c, 'jour': dt.date(2026, 6, 1) + dt.timedelta(days=k * 140 // 3000), 'surface': 'Hard', 'bo': 3}
            H.append((x, f(sg(zs)), f(sg(ze))))
            exp[id(x)] = (50, 50)
        r = EP.desaccord_wta(H, {'elo': .5, 'simulation': .5}, dt.date(2026, 9, 1), ajuster_poids, exp, {})
        self.assertIn('désaccords WTA', r['raison'])
        if r['adopte']:
            self.assertGreater(r['poids']['elo'], r['poids']['simulation'])
        import pronostics_du_jour as PJ
        PJ.AJUSTEMENTS.clear()
        PJ.AJUSTEMENTS['poids_desaccord_wta'] = {'elo': 1.0, 'simulation': 0.0}
        try:
            self.assertAlmostEqual(PJ.ajuster_combinaison(.45, 'WTA', .7, .3, 50, 50), .7, places=6)   # suit l'Elo
            self.assertEqual(PJ.ajuster_combinaison(.45, 'ATP', .7, .3, 50, 50), .45)                    # ATP : inchangé
            self.assertEqual(PJ.ajuster_combinaison(.65, 'WTA', .7, .6, 50, 50), .65)                    # accord : inchangé
        finally:
            PJ.AJUSTEMENTS.clear()


class NoteV2(unittest.TestCase):
    def test_sans_calibration(self):
        m = {'combinaison': {'p_home': .7}, 'stats': {'p_home': .7}, 'simulation': {'p_home': .68},
             'matchs_joues': [60, 60], 'style_connu': [True, True], 'circuit': 'ATP', 'surface': 'Hard', 'uid': 'u'}
        a = FI.evaluer(m, [])
        hist = [{'uid': str(i), 'p': .7, 'y': i % 2, 'circuit': 'ATP', 'surface': 'Hard'} for i in range(300)]   # calibration ratée
        b = FI.evaluer(m, hist)
        self.assertNotEqual(a['note'], b['note'])
        self.assertEqual(b['version_v2'], FI.VERSION_V2)
        self.assertIn(b['niveau_v2'], FI.NIVEAUX)

    def test_cohorte(self):
        M = [{'fiabilite': {'niveau': 'correct', 'niveau_v2': 'solide', 'version_v2': FI.VERSION_V2,
                            'version_fiabilite': FI.VERSION_FIABILITE}, 'pronostique_le': j, 'debut': j,
              'reel': {'gagnant': 'home'}, 'dernier': {'combinaison': {'p_home': .7, 'vainqueur_juste': True}}}
             for j in ('2026-10-28T10:00', '2026-10-30T10:00')]
        out = V.validation_fiabilite({'matchs': M})
        self.assertEqual(out['v2']['par_niveau']['solide']['n'], 1)          # seulement à partir du 30/10


if __name__ == '__main__':
    unittest.main()
