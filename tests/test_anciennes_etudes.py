# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 247) — les études d'avant l'audit rejouées avec l'Elo de la production."""
import datetime as dt
import json
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
SIM = os.path.join(RACINE, 'simulateur')
sys.path.insert(0, SIM)
import donnees as DN  # noqa: E402
import elo as E  # noqa: E402
import etude_anciennes_etudes as A  # noqa: E402


class Rejeu(unittest.TestCase):
    def test_decalage_par_tour(self):
        d0 = dt.date(2025, 3, 3)
        M = [{'date': d0, 'fin': d0 + dt.timedelta(days=8), 'tour': t, 'num': n} for t, n in ((10, 1), (0, 2), (6, 3), (6, 1))]
        M = DN.decaler_par_tour(M)
        self.assertEqual([m['tour'] for m in M], [0, 6, 6, 10])
        self.assertEqual(M[0]['date'], d0)
        self.assertEqual(M[1]['date'], d0 + dt.timedelta(days=6))
        self.assertEqual(M[-1]['date'], d0 + dt.timedelta(days=8))      # borné à la fin du tournoi
        self.assertEqual([m['num'] for m in M[1:3]], [1, 3])

    def test_elo_de_production_le_temps_du_rejeu(self):
        options, bas = E.options_production(RACINE)
        Base = E.Elo
        with A.elo_de_production(RACINE):
            el = E.Elo()
            self.assertEqual(el.options(), E.de_production(RACINE)[0].options())
            el.presenter('x', 1200.0)
            ref = Base(**options)
            ref.presenter('x', bas or 1200.0)
            ref.presenter('y', 1500.0)
            el.presenter('y', 1500.0)
            self.assertAlmostEqual(el.proba('x', 'y', 'Hard'), ref.proba('x', 'y', 'Hard'), places=12)
        self.assertIs(E.Elo, Base)

    def test_comparaison(self):
        a = {'circuits': {'ATP': {'x': {'retenue': True}}, 'CH': {'x': {'retenue': True}}, 'WTA': {'x': {'retenue': False}}}}
        n = {'circuits': {'ATP': {'x': {'retenue': False}}, 'CH': {'x': {'retenue': False}}, 'WTA': {'x': {'retenue': True}}}}
        c = {x['verdict']: x['suite'] for x in A.comparer('etude_set_decisif', a, n)['changements']}
        self.assertIn('retirer', c['circuits/ATP/x/retenue'])
        self.assertIn('non concluant', c['circuits/CH/x/retenue'])
        self.assertIn('fantôme', c['circuits/WTA/x/retenue'])
        c = {x['verdict']: x['suite'] for x in A.comparer('etude_age', a, n)['changements']}
        self.assertIn('233', c['circuits/ATP/x/retenue'])


class Rapport(unittest.TestCase):
    def setUp(self):
        self.r = json.load(open(os.path.join(SIM, 'rapport_anciennes_etudes.json'), encoding='utf-8'))

    def test_toutes_rejouees(self):
        self.assertEqual(set(self.r['etudes']), set(A.ETUDES))
        for n, v in self.r['etudes'].items():
            self.assertNotIn('erreur', v, n)
        self.assertIn('conclusion', self.r)

    def test_ce_qui_est_en_production_reste_justifie(self):
        import pronostics_du_jour as PJ
        b = PJ.charger_betas_combines(RACINE)
        self.assertNotIn('favori_outsider', b.get('ATP', {}))           # devenu négatif : déjà hors production (233)
        self.assertNotIn('parcours_tournoi', b.get('ATP', {}))
        v = self.r['etudes']['etude_profils_contexte']['changements']
        self.assertFalse([c for c in v if c['verdict'].startswith('favori_outsider/WTA')])   # le WTA reste positif

    def test_public(self):
        t = json.dumps(self.r, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'cote', 'value'):
            self.assertNotIn(mot, t)


class SuiviEnDirect(unittest.TestCase):
    def test_elo_de_production(self):
        s = open(os.path.join(SIM, 'etude_live_reevaluation.py'), encoding='utf-8').read()
        self.assertIn('E.de_production(racine)', s)
        self.assertIn('donnees.decaler_par_tour(', s)


if __name__ == '__main__':
    unittest.main()
