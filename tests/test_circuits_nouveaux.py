"""Livraison 51 (22/10/2026) : fiabilité par circuit, poids propres aux Challenger, nouveaux venus
(règles fixées d'avance, entrainement_progressif.py), application dans les pronostics, bilan du mois."""
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
import backtest_match_simule as BMS  # noqa: E402
import bilan_algo as BA  # noqa: E402

sg = lambda z: 1 / (1 + math.exp(-z))
J0 = dt.date(2026, 6, 1)
LIM = dt.date(2026, 9, 10)


def hors_synthetique(n=3000, graine=4, ch_sim_meilleure=False, biais_nouveau=0.0):
    """(x, p_sim, p_elo) vus du vrai vainqueur. En Challenger, la simulation peut voir plus juste que l'Elo."""
    rnd = random.Random(graine)
    H, exp = [], {}
    for k in range(n):
        c = ('ATP', 'WTA', 'CH')[k % 3]
        z = rnd.gauss(0, 1.0)
        bruit_s, bruit_e = (0.2, 1.2) if (c == 'CH' and ch_sim_meilleure) else (0.9, 0.6)
        zs, ze = z + rnd.gauss(0, bruit_s), z + rnd.gauss(0, bruit_e)
        na, nb = rnd.choice((2, 10, 50, 200)), rnd.choice((2, 10, 50, 200))
        zt = z + biais_nouveau * (EP.nouveau(na) - EP.nouveau(nb))              # la vérité tient compte du biais
        y = rnd.random() < sg(zt)
        f = (lambda p: p) if y else (lambda p: 1 - p)
        x = {'circuit': c, 'jour': J0 + dt.timedelta(days=k * 140 // n)}
        H.append((x, f(sg(zs)), f(sg(ze))))
        exp[id(x)] = (na, nb) if y else (nb, na)
    return H, exp


class Challenger(unittest.TestCase):
    def test_poids_propres_adoptes_quand_la_simulation_y_voit_mieux(self):
        H, _ = hors_synthetique(ch_sim_meilleure=True)
        P = {'elo': 0.7, 'simulation': 0.3}
        r = EP.poids_challenger(H, P, LIM, BMS.ajuster_poids)
        self.assertTrue(r['adopte'], r['raison'])
        self.assertGreater(r['poids']['simulation'], r['poids']['elo'])

    def test_pas_adoptes_si_meme_monde(self):
        H, _ = hors_synthetique(ch_sim_meilleure=False, n=1500)
        av = [h for h in H if h[0]['jour'] < LIM]
        w = BMS.ajuster_poids([[EP._lg(pe), EP._lg(ps)] for _, ps, pe in av])
        r = EP.poids_challenger(H, {'elo': w[0], 'simulation': w[1]}, LIM, BMS.ajuster_poids)
        self.assertIn('raison', r)

    def test_par_circuit(self):
        H, _ = hors_synthetique(n=900)
        r = EP.par_circuit(H, {'elo': 0.7, 'simulation': 0.3}, LIM)
        self.assertEqual(set(r), {'ATP', 'WTA', 'CH'})
        self.assertEqual(r['CH']['circuit'], 'Challenger')
        self.assertIsNotNone(r['CH']['six_dernieres_semaines']['combinaison'])


class NouveauxVenus(unittest.TestCase):
    def test_surestimes_corriges(self):
        H, exp = hors_synthetique(n=6000, biais_nouveau=-0.8)      # le nouveau venu gagne moins que prévu
        r = EP.nouveaux_venus(H, {'elo': 0.5, 'simulation': 0.5}, LIM, exp)
        self.assertTrue(r['adopte'], r['raison'])
        self.assertLess(r['delta'], -0.2)
        self.assertIn('surestimé', r['raison'])

    def test_sans_biais_delta_faible(self):
        H, exp = hors_synthetique(n=6000, biais_nouveau=0.0)
        r = EP.nouveaux_venus(H, {'elo': 0.5, 'simulation': 0.5}, LIM, exp)
        self.assertLess(abs(r['delta_appris_avant']), 0.25)

    def test_nouveau(self):
        self.assertEqual(EP.nouveau(0), 1.0)
        self.assertEqual(EP.nouveau(30), 0.0)
        self.assertAlmostEqual(EP.nouveau(15), 0.5)


class Pronostics(unittest.TestCase):
    def test_ajuster_combinaison(self):
        import pronostics_du_jour as PJ
        PJ.AJUSTEMENTS.clear()
        self.assertEqual(PJ.ajuster_combinaison(0.6, 'CH', 0.7, 0.5, 5, 200), 0.6)
        PJ.AJUSTEMENTS.update({'poids_CH': {'elo': 0.2, 'simulation': 0.8}, 'delta_nouveaux': -0.5})
        try:
            p = PJ.ajuster_combinaison(0.6, 'CH', 0.7, 0.5, 200, 200)        # poids Challenger, pas de nouveau venu
            self.assertAlmostEqual(p, sg(0.2 * math.log(0.7 / 0.3)), places=6)
            self.assertLess(PJ.ajuster_combinaison(0.6, 'ATP', 0.7, 0.5, 0, 200), 0.6)   # home jamais vu : calmé
            self.assertGreater(PJ.ajuster_combinaison(0.6, 'ATP', 0.7, 0.5, 200, 0), 0.6)
            self.assertEqual(PJ.ajuster_combinaison(0.6, 'ATP', 0.7, 0.5, 200, 100), 0.6)
        finally:
            PJ.AJUSTEMENTS.clear()

    def test_charger(self):
        import pronostics_du_jour as PJ
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            json.dump({'poids_challenger': {'adopte': True, 'poids': {'elo': 0.3, 'simulation': 0.6}},
                       'nouveaux_venus': {'adopte': False, 'delta': -0.4}},
                      open(os.path.join(d, 'simulateur', 'choix_simulation.json'), 'w'))
            self.assertEqual(PJ.charger_ajustements(d), {'poids_CH': {'elo': 0.3, 'simulation': 0.6}})


class BilanDuMois(unittest.TestCase):
    def test_page(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'Tennis_Edge_Lab', 'live'))
            m = lambda c, ok, p, j: {'debut': f'2026-10-{j:02d}T10:00', 'circuit': c, 'home': 'A', 'away': 'B',
                                     'premier': {'combinaison': {'vainqueur_juste': ok, 'proba_du_vainqueur': p}}}
            json.dump({'matchs': [m('ATP', True, 0.72, 3), m('CH', False, 0.3, 5), m('CH', True, 0.65, 9), m('ITF', True, 0.9, 9),
                                  m('ATP', True, 0.8, 2 + 30 - 30)]},
                      open(os.path.join(d, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), 'w'))
            old = BA.ICI
            BA.ICI = d
            try:
                json.dump({'poids_challenger': {'adopte': False, 'raison': 'Challenger : poids propres 0,61 contre 0,60'}},
                          open(os.path.join(d, 'choix_simulation.json'), 'w'))
                J = [{'date': '2026-10-05', 'decisions': {'nouveaux venus': 'pas de correction', 'facteurs du match': 'styles'}},
                     {'date': '2026-10-26', 'decisions': {'nouveaux venus': 'corrigés (δ = -0.3)', 'facteurs du match': 'styles'}}]
                t = BA.bilan_du_mois(d, dt.datetime(2026, 11, 2, 3, 0), J)
            finally:
                BA.ICI = old
        self.assertIn('Bilan de octobre 2026', t)
        self.assertIn('4 matchs</b> sur tes circuits · vainqueur trouvé 3/4 (75 %)', t)
        self.assertIn('• Challenger : 1/2 (50 %) — moins de 30 matchs, ne pas conclure', t)
        self.assertIn('• 70–80 % → 50 % (2 matchs)', t)
        self.assertIn('• nouveaux venus : pas de correction → corrigés (δ = -0.3)', t)
        self.assertIn('• Poids propres aux Challenger : Challenger : poids propres 0,61 contre 0,60', t)

    def test_decisions(self):
        d = BA.decisions({'reglage_simulation': {'adopte': True, 'sigma': 0.0},
                          'combinaison': {'adopte': True, 'poids': {'elo': 0.78, 'simulation': 0.24}}}, {'adoptes': ['styles']})
        self.assertEqual(d['forme du jour (σ)'], 'σ = 0.0')
        self.assertEqual(d['mélange simulation + Elo'], "24 % simulation (appris sur l'archive)")
        self.assertEqual(d['facteurs du match'], 'styles')


if __name__ == '__main__':
    unittest.main()
