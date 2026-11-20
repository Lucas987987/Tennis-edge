"""Points 1, 2, 9 (22/10/2026) : Elo amélioré (options neutres par défaut, Elo pondéré par le
score, incertitude), combinaison simulation + Elo (poids retrouvés, règle d'adoption), calibration."""
import datetime as dt
import math
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import elo as E  # noqa: E402
import backtest_match_simule as BMS  # noqa: E402
import match_simule as S  # noqa: E402

sg = lambda z: 1 / (1 + math.exp(-z))
lg = lambda p: math.log(p / (1 - p))


class EloOptions(unittest.TestCase):
    def test_defaut_identique_a_la_formule(self):
        e = E.Elo()
        for _ in range(5):
            e.maj('a', 'b', 'Hard')
        d = e.note('a', 'Hard') - e.note('b', 'Hard')
        self.assertAlmostEqual(e.proba('a', 'b', 'Hard'), 1 / (1 + 10 ** (-d / 400)), places=12)

    def test_welo_norme_score_inconnu_comme_classique(self):
        a, b = E.Elo(), E.Elo(welo='norme')
        for e in (a, b):
            e.maj('x', 'y', 'Clay')
        self.assertAlmostEqual(a.note('x'), b.note('x'), places=9)
        c = E.Elo(welo='norme')
        c.maj('x', 'y', 'Clay', part=E.part_jeux([(6, 0), (6, 0)]))         # victoire écrasante : bouge plus
        self.assertGreater(c.note('x'), a.note('x'))
        d = E.Elo(welo='brut')
        d.maj('x', 'y', 'Clay')
        self.assertLess(d.note('x'), a.note('x'))                           # version publiée : × 0,661 en moyenne

    def test_part_jeux(self):
        self.assertAlmostEqual(E.part_jeux([(6, 4), (7, 6)]), 13 / 23)
        self.assertIsNone(E.part_jeux(None))
        self.assertIsNone(E.part_jeux('2-0'))

    def test_incertitude_rapproche_de_50(self):
        e, f = E.Elo(), E.Elo(incertitude=5.0)
        for x in (e, f):
            for _ in range(3):
                x.maj('a', 'b')
        self.assertLess(abs(f.proba('a', 'b') - 0.5), abs(e.proba('a', 'b') - 0.5))
        self.assertGreater(f.proba('a', 'b'), 0.5)

    def test_poids_surface_et_export(self):
        e = E.Elo(poids_surface=0.3)
        e.maj('a', 'b', 'Grass')
        g, s_ = e._g('a'), e._s('a', 'Grass')
        self.assertAlmostEqual(e.note('a', 'Grass'), 0.7 * g + 0.3 * s_)
        f = E.Elo.importer(e.exporter({}), e.options())
        self.assertEqual(f.options(), e.options())
        self.assertAlmostEqual(f.proba('a', 'b', 'Grass'), e.proba('a', 'b', 'Grass'), places=1)


def lignes(n, graine=3, debut=dt.date(2024, 1, 1)):
    """Matchs synthétiques : vrai niveau z ; l'Elo et la simulation en voient chacun une version bruitée
    (bruits indépendants) : les combiner doit aider."""
    rnd = random.Random(graine)
    L = []
    for k in range(n):
        z = rnd.gauss(0, 1.0)
        pe, ps = sg(z + rnd.gauss(0, 0.7)), sg(1.4 * (z + rnd.gauss(0, 0.7)))   # simulation trop sûre d'elle
        y = rnd.random() < sg(z)
        f = (lambda p: p) if y else (lambda p: 1 - p)                          # vu du vrai vainqueur
        L.append({'date': debut + dt.timedelta(days=k * 760 // n), 'circuit': 'ATP' if k % 2 else 'WTA', 'connus': k % 60,
                  'elo': f(pe), 'simulation_pure': f(ps), 'simulation_pure_ajustee': f(ps), 'pinnacle': f(sg(z))})
    return L


class Combinaison(unittest.TestCase):
    def test_poids_et_adoption(self):
        L = lignes(6000)
        cb = BMS.combinaison(L, 'simulation_pure')
        self.assertTrue(cb['adopte'], cb['raison'])
        self.assertGreater(cb['poids']['elo'], 0.2)
        self.assertGreater(cb['poids']['simulation'], 0.1)
        self.assertLess(cb['poids']['simulation'], 0.7)                  # la simulation trop sûre est réduite
        J = cb['jugement']
        self.assertLess(J['combinaison']['log_loss'], J['elo']['log_loss'])
        self.assertLess(J['combinaison']['log_loss'], J['simulation']['log_loss'])
        cal = BMS.calibration_detaillee(L, 'simulation_pure', cb)
        self.assertIn('combinaison', cal['ATP'])
        self.assertGreater(cal['un joueur à moins de 30 matchs']['elo']['n'], 0)

    def test_pas_adoptee_si_la_simulation_napporte_rien(self):
        L = lignes(6000)
        for x in L:
            x['simulation_pure'] = 0.5
        cb = BMS.combinaison(L, 'simulation_pure')
        # la simulation à 50 % ne sait rien : la combinaison ne fait pas mieux que l'Elo seul (au bruit près)
        self.assertLess(abs(cb['poids_appris_2024']['simulation']), 1.0)
        J = cb['jugement']
        self.assertGreaterEqual(J['combinaison']['log_loss'], J['elo_recalibre']['log_loss'] - 1e-9)

    def test_melange(self):
        self.assertAlmostEqual(S.melange({'elo': 1.0, 'simulation': 0.0}, 0.7, 0.2), 0.7, places=9)
        self.assertAlmostEqual(S.melange({'elo': 0.5, 'simulation': 0.5}, 0.7, 0.3), 0.5, places=9)

    def test_trop_peu_de_matchs(self):
        self.assertFalse(BMS.combinaison(lignes(200), 'simulation_pure')['adopte'])


if __name__ == '__main__':
    unittest.main()


class ReglageSimulation(unittest.TestCase):
    def test_amplifier(self):
        c = S.borner({'f': 0.62, 'a': 0.14, 'w1': 0.76, 'd': 0.07, 'w2j': 0.55})
        moy = S.borner({'f': 0.62, 'a': 0.10, 'w1': 0.72, 'd': 0.08, 'w2j': 0.55})
        self.assertIs(S.amplifier(c, moy, 1.0), c)
        x = S.amplifier(c, moy, 1.5)
        self.assertGreater(x['w1'], c['w1'])                    # écart à la moyenne agrandi
        self.assertGreater(x['a'], c['a'])
        self.assertLess(x['d'], c['d'])
        self.assertAlmostEqual(x['w2j'], c['w2j'], places=9)     # déjà à la moyenne : inchangé

    def test_choix_du_reglage(self):
        L = lignes(6000)
        for x in L:                                              # monde où σ = 0 aide, et la couche « résultats » aussi
            p = x['pinnacle']                                   # la vraie probabilité du monde synthétique
            x['grille'] = {'0|0.15|1|0': 0.5 + 0.6 * (p - 0.5), '0|0|1|0': 0.5 + 0.8 * (p - 0.5), '0|0|1|0.04': p,
                           '0|0.15|1|0.04': 0.5 + 0.7 * (p - 0.5)}
        r = BMS.choisir_reglage(L)
        self.assertEqual(r['cle'], '0|0|1|0.04')
        self.assertTrue(r['adopte'])
        self.assertEqual((r['sigma'], r['amplification'], r['jeux'], r['resultats']), (0.0, 1.0, 0.0, 0.04))
        self.assertTrue(r['apport_des_resultats_2025']['adopte'])
        self.assertLess(r['apport_des_resultats_2025']['avec'], r['apport_des_resultats_2025']['sans'])

    def test_la_couche_resultats_ne_defait_pas_le_reglage(self):
        L = lignes(6000)
        for x in L:                                              # couche bonne en 2024, mauvaise ensuite
            p = x['pinnacle']
            mauvais = x['date'] >= BMS.DEBUT_JUGE_COMB
            x['grille'] = {'0|0.15|1|0': 0.5 + 0.6 * (p - 0.5), '0|0|1|0': 0.5 + 0.8 * (p - 0.5),
                           '0|0|1|0.04': 0.5 + (0.2 if mauvais else 1.0) * (p - 0.5)}
        r = BMS.choisir_reglage(L)
        self.assertEqual(r['cle'], '0|0|1|0')                   # σ = 0 reste adopté, la couche non
        self.assertTrue(r['adopte'])
        self.assertEqual(r['resultats'], 0.0)
        self.assertFalse(r['apport_des_resultats_2025']['adopte'])

    def test_poids_selon_le_contexte(self):
        L = lignes(6000)
        for k, x in enumerate(L):                               # sur gazon, la simulation voit juste, l'Elo non
            x['surface'] = 'Grass' if k % 3 == 0 else 'Hard'
            x['bo'] = 3
            if x['surface'] == 'Grass':
                x['simulation_pure'] = x['pinnacle']
                x['elo'] = 0.5 + 0.3 * (x['elo'] - 0.5)
        cb = BMS.combinaison(L, 'simulation_pure')
        r = BMS.contexte_poids(L, 'simulation_pure', cb)
        self.assertTrue(r['adopte'], r['raison'])
        c = r['corrections']
        self.assertGreater(c['sim_gazon'], 0.1)                  # plus de poids à la simulation sur gazon
        P = dict(cb['poids'], contexte=c)
        gazon, dur = S.contexte_match('Grass', 'ATP', 3), S.contexte_match('Hard', 'ATP', 3)
        self.assertGreater(S.melange_contexte(P, gazon, 0.5, 0.8), S.melange_contexte(P, dur, 0.5, 0.8))
        self.assertAlmostEqual(S.melange_contexte(cb['poids'], gazon, 0.6, 0.7), S.melange(cb['poids'], 0.6, 0.7))

    def test_contexte_neutre(self):
        self.assertEqual(S.contexte_match('Hard', 'ATP', 3), {'gazon': 0.0, 'terre': 0.0, 'wta': 0.0, '5sets': 0.0})
        self.assertEqual(S.contexte_match('Clay', 'WTA', 5), {'gazon': 0.0, 'terre': 1.0, 'wta': 1.0, '5sets': 1.0})
