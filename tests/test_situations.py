"""Livraison 52 (23/10/2026) : sortis des qualifications, changement de surface (même règle que les
nouveaux venus), abandons et forfaits sortis des bilans."""
import datetime as dt
import json
import math
import os
import random
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import entrainement_progressif as EP  # noqa: E402
import facteurs as FA  # noqa: E402
import bilan_algo as BA  # noqa: E402
import pronostics_du_jour as PJ  # noqa: E402

sg = lambda z: 1 / (1 + math.exp(-z))
J = 86400


class Parcours(unittest.TestCase):
    def fiches(self):
        t0 = 1_790_000_000.0
        f = lambda t, tr, tour, h, a, su='Hardcourt indoor': {'debut': t, 'tournoi_id': tr, 'tour': tour, 'surface': su,
                                                             'home': {'nom': h}, 'away': {'nom': a}}
        return t0, [f(t0, 7, 'Qualification Round 1', 'Ana Bel', 'Cora Dix'), f(t0 + J, 7, 'Qualification Final', 'Ana Bel', 'Eva Fox'),
                    f(t0 - 20 * J, 3, 'Round of 32', 'Gil Hob', 'Ana Bel', 'Red clay'), f(t0 - 5 * J, 4, 'Round of 32', 'Gil Hob', 'Ivy Jo')]

    def test_qualifie(self):
        t0, F = self.fiches()
        Q, Sf = FA.parcours_des_fiches(F)
        a = FA.E.cle('Ana Bel')
        self.assertEqual(FA.qualifie(Q, a, '7', t0 + 2 * J), 1.0)
        self.assertEqual(FA.qualifie(Q, a, '8', t0 + 2 * J), 0.0)                 # autre tournoi
        self.assertEqual(FA.qualifie(Q, a, '7', t0 + 15 * J), 0.0)                # trop ancien
        self.assertEqual(FA.qualifie(Q, FA.E.cle('Gil Hob'), '7', t0 + 2 * J), 0.0)

    def test_transition(self):
        t0, F = self.fiches()
        Q, Sf = FA.parcours_des_fiches(F)
        g = FA.E.cle('Gil Hob')
        self.assertEqual(FA.transition(Sf, g, 'Hard', t0), 0.0)                   # a joué sur dur il y a 5 jours
        self.assertEqual(FA.transition(Sf, g, 'Grass', t0), 1.0)                  # vient de la terre et du dur
        self.assertEqual(FA.transition(Sf, FA.E.cle('Zed Zo'), 'Grass', t0), 0.0)  # inconnu : rien à dire

    def test_contexte_aller_retour(self):
        t0, F = self.fiches()
        H = FA.Historique()
        H.qualifs, H.surfaces = FA.parcours_des_fiches(F)
        doc = json.loads(json.dumps(FA.contexte(H, {}, {'7': 'Ortisei, Italy'}, t0 + 2 * J)))
        C = FA.Contexte(doc)
        self.assertEqual(C.qualifie(FA.E.cle('Ana Bel'), 'Ortisei', t0 + 2 * J), 1.0)
        self.assertEqual(C.transition(FA.E.cle('Gil Hob'), 'Grass', t0), 1.0)


class Correction(unittest.TestCase):
    def test_qualifie_sous_estime(self):
        rnd = random.Random(2)
        H, sit = [], {}
        lim = dt.date(2026, 9, 10)
        for k in range(6000):
            z = rnd.gauss(0, 1)
            qa, qb = (rnd.random() < 0.15) * 1.0, (rnd.random() < 0.15) * 1.0
            y = rnd.random() < sg(z + 0.7 * (qa - qb))                         # le qualifié gagne plus que prévu
            f = (lambda p: p) if y else (lambda p: 1 - p)
            x = {'circuit': 'CH', 'jour': dt.date(2026, 6, 1) + dt.timedelta(days=k * 140 // 6000)}
            H.append((x, f(sg(z)), f(sg(z))))
            sit[id(x)] = (qa, qb) if y else (qb, qa)
        r = EP.correction_situation(H, {'elo': 0.5, 'simulation': 0.5}, lim, lambda x: sit.get(id(x)), 'qualifies')
        self.assertTrue(r['adopte'], r['raison'])
        self.assertGreater(r['delta'], 0.3)
        self.assertIn('le qualifié est sous-estimé', r['raison'])

    def test_pronostic(self):
        PJ.AJUSTEMENTS.clear()
        PJ.AJUSTEMENTS.update({'delta_qualifies': 0.5, 'delta_transition': -0.4})
        try:
            p = PJ.ajuster_combinaison(0.5, 'ATP', 0.5, 0.5, 200, 200, {'qualifies': (1.0, 0.0), 'transition': (0.0, 0.0)})
            self.assertAlmostEqual(p, sg(0.5))
            p = PJ.ajuster_combinaison(0.5, 'ATP', 0.5, 0.5, 200, 200, {'qualifies': (0.0, 0.0), 'transition': (1.0, 0.0)})
            self.assertAlmostEqual(p, sg(-0.4))
            PJ.AJUSTEMENTS.pop('delta_qualifies')
            p = PJ.ajuster_combinaison(0.5, 'ATP', 0.5, 0.5, 200, 200, {'qualifies': (1.0, 0.0)})
            self.assertEqual(p, 0.5)                                            # non adopté : rien
        finally:
            PJ.AJUSTEMENTS.clear()


class Interruptions(unittest.TestCase):
    def test_interruption(self):
        self.assertEqual(PJ.interruption({'statut': {'texte': 'Retired'}}), 'abandon')
        self.assertEqual(PJ.interruption({'statut': {'texte': 'Walkover'}}), 'forfait')
        self.assertIsNone(PJ.interruption({'statut': {'texte': 'Ended'}}))
        self.assertIsNone(PJ.interruption(None))

    def test_bilan_ne_compte_pas(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'Tennis_Edge_Lab', 'live'))
            m = lambda ok, it=None: {'debut': '2026-10-20T14:00', 'home': 'A', 'away': 'B', 'tournoi': 'ATP X', 'circuit': 'ATP',
                                     'reel': {'gagnant': 'home', 'interrompu': it},
                                     'premier': {'combinaison': {'vainqueur_juste': ok, 'proba_du_vainqueur': 0.6}}}
            with open(os.path.join(d, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), 'w') as f:
                json.dump({'matchs': [m(True), m(False, 'abandon')]}, f)
            old = BA.ICI
            BA.ICI = d
            try:
                t, _ = BA.construire(d, dt.datetime(2026, 10, 26, 3, 0))
            finally:
                BA.ICI = old
        self.assertIn('1 matchs joués', t)
        self.assertIn('1 abandon(s) ou forfait(s) non compté(s)', t)
        self.assertIn('vainqueur 1/1', t)


if __name__ == '__main__':
    unittest.main()
