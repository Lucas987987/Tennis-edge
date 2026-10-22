"""Match simulé avant l'heure (22/10/2026) : la simulation point par point retrouve le moteur exact,
les feuilles de match sont cohérentes (comptes, breaks, jeux), l'ancrage tient la probabilité de
victoire, les profils de service sont point-in-time et retrouvent la vérité."""
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
import match_simule as S  # noqa: E402
import modele as M  # noqa: E402
import profils_service as PS  # noqa: E402

MOY = {'f': 0.62, 'a': 0.12, 'd': 0.07, 'w1': 0.73, 'w2j': 0.56, 'ra': 0.12, 'r1': 0.73, 'r2j': 0.56}
GROS = dict(MOY, f=0.58, a=0.25, w1=0.80, d=0.09, w2j=0.55, ra=0.10, r1=0.75, r2j=0.58)
RELANCEUR = dict(MOY, f=0.68, a=0.06, w1=0.70, d=0.04, w2j=0.58, ra=0.07, r1=0.68, r2j=0.50)


class Moteur(unittest.TestCase):
    def test_victoire_rapide_identique_au_moteur_exact(self):
        for sg in (2, 3):
            for pa, pb in ((0.66, 0.61), (0.58, 0.70)):
                self.assertAlmostEqual(S.victoire(pa, pb, sg), M.match(pa, pb, sg)['victoire'], places=12)
            a1 = S.ancrer_rapide(0.66, 0.6, 0.72, sg, 0.15)
            a2 = M.ancrer_forme(0.66, 0.6, 0.72, sg, 0.15, iterations=30)
            self.assertAlmostEqual(a1[0], a2[0], places=9)
            self.assertAlmostEqual(a1[1], a2[1], places=9)

    def test_ajuster_et_composantes(self):
        c = S.composantes(GROS, RELANCEUR, MOY)
        self.assertLess(c['a'], GROS['a'])                       # bon relanceur : moins d'aces
        self.assertLess(c['w1'], GROS['w1'])
        c2 = S.ajuster(c, 0.70)
        self.assertAlmostEqual(S.p_service(c2), 0.70, places=6)
        self.assertEqual((c2['f'], c2['d']), (c['f'], c['d']))  # le style ne bouge pas, seul le niveau
        self.assertLessEqual(c2['a'], 0.95 * c2['w1'])

    def test_simulation_retrouve_le_moteur_exact(self):
        cA, cB = S.composantes(GROS, RELANCEUR, MOY), S.composantes(RELANCEUR, GROS, MOY)
        for sg, p in ((2, 0.64), (3, 0.78)):
            r = S.simuler(cA, cB, p, sg, 4000, 0.15, cle=f't{sg}')
            se = math.sqrt(p * (1 - p) / 4000)
            self.assertLess(abs(r['victoire_A'] - p), 4 * se)    # niveau ancré : la simulation tombe sur p
            a, b = S.ancrer_rapide(S.p_service(cA), S.p_service(cB), p, sg, 0.15)
            ex = M.match_forme(a, b, sg, 0.15)
            for k, v in ex['sets'].items():
                self.assertLess(abs(r['sets'].get(k, 0) - v), 0.03, k)
            self.assertLess(abs(r['jeux']['moy'] - M.moyenne(ex['total_jeux'])), 0.5)
            self.assertLess(abs(r['tiebreak'] - ex['tiebreak']), 0.03)

    def test_feuille_coherente(self):
        cA, cB = S.composantes(GROS, RELANCEUR, MOY), S.composantes(RELANCEUR, GROS, MOY)
        rnd = random.Random(5)
        for _ in range(300):
            g, sets, st, br, ntb = S.un_match(cA, cB, 2, 7, rnd, rnd.random() < 0.5)
            ga, gb = sum(a for a, _ in sets), sum(b for _, b in sets)
            self.assertEqual((st[0][S.JEUX], st[1][S.JEUX]), (ga, gb))
            self.assertEqual(sum(x[S.SVPT] for x in st), sum(x[S.PTS] for x in st))   # chaque point a un vainqueur
            self.assertEqual(ntb, sum(a + b == 13 for a, b in sets))
            for i in (0, 1):
                x = st[i]
                self.assertLessEqual(x[S.ACE], x[S.W1])
                self.assertLessEqual(x[S.W1], x[S.IN1])
                self.assertLessEqual(x[S.W2] + x[S.DF], x[S.SVPT] - x[S.IN1])
                self.assertLessEqual(x[S.BPS], x[S.BPF])
                perdus = x[S.SG] - x[S.SGW]
                self.assertEqual(perdus, x[S.BPF] - x[S.BPS])                  # un jeu perdu = une balle de break convertie
                self.assertEqual(perdus, sum(1 for b in br if b[3] == 1 - i))
            self.assertEqual(g, 0 if sum(a > b for a, b in sets) > sum(b > a for a, b in sets) else 1)

    def test_reproductible_et_match_type(self):
        cA, cB = S.composantes(GROS, RELANCEUR, MOY), S.composantes(RELANCEUR, GROS, MOY)
        r1 = S.simuler(cA, cB, 0.6, 2, 500, 0.15, cle='x')
        r2 = S.simuler(cA, cB, 0.6, 2, 500, 0.15, cle='x')
        self.assertEqual(r1, r2)
        self.assertEqual(r1['match_type']['score'], r1['scores'][0][0])
        self.assertGreater(r1['feuille'][0]['aces']['moy'], r1['feuille'][1]['aces']['moy'])    # le gros serveur
        f = r1['feuille'][0]['aces']
        self.assertLessEqual(f['p10'], f['moy'])
        self.assertLessEqual(f['moy'], f['p90'])


def _match(jour, g, p, dg, dl, surface='Hard', circuit='ATP'):
    return {'date': jour, 'fin': jour + dt.timedelta(days=8), 'circuit': circuit, 'surface': surface, 'bo': 3,
            'gagnant': g, 'perdant': p, 'nom_g': g, 'nom_p': p, 'detail': {'w': dg, 'l': dl}}


class Profils(unittest.TestCase):
    def setUp(self):
        rnd = random.Random(11)
        self.M = []
        mu = MOY
        jour = dt.date(2023, 1, 2)
        for k in range(160):
            a, b = ('gros', 'autre') if k % 2 else ('relanceur', 'autre')
            pa, pb = (GROS if a == 'gros' else RELANCEUR), MOY
            cA, cB = S.composantes(pa, pb, mu), S.composantes(pb, pa, mu)
            g, sets, st, br, ntb = S.un_match(cA, cB, 2, 7, rnd, True)
            det = lambda x, y: (x[S.SVPT], x[S.IN1], x[S.W1], x[S.W2], x[S.ACE], x[S.DF], x[S.BPF], x[S.BPS], x[S.SG])
            dA, dB = det(st[0], st[1]), det(st[1], st[0])
            self.M.append(_match(jour, a, b, dA, dB) if g == 0 else _match(jour, b, a, dB, dA))
            jour += dt.timedelta(days=3)

    def test_retrouve_les_styles(self):
        P = PS.construire(self.M)
        jour = dt.date(2024, 6, 1)
        g, n = P.profil('gros', 'ATP', 'Hard', jour)
        r, _ = P.profil('relanceur', 'ATP', 'Hard', jour)
        self.assertGreater(n, 500)
        self.assertGreater(g['a'], 2 * r['a'])
        self.assertLess(g['f'], r['f'])
        self.assertGreater(g['d'], r['d'])
        self.assertLess(r['ra'], g['ra'] + 0.05)
        inconnu, n0 = P.profil('personne', 'ATP', 'Hard', jour)
        self.assertEqual(n0, 0.0)
        for k, v in P.moyenne('ATP', 'Hard').items():
            self.assertAlmostEqual(inconnu[k], v, places=9)                   # inconnu : moyenne du circuit
        self.assertEqual(P.moyenne('CH', 'Hard'), P.moyenne('ATP', 'Hard'))   # repli Challenger -> ATP

    def test_point_in_time(self):
        coupe = self.M[80]['date']
        P = PS.construire(self.M, jusqu_au=coupe)
        n_attendu = sum(m['detail']['w'][0] + m['detail']['l'][0] for m in self.M if m['fin'] < coupe)
        tot = P.m[('ATP', 'all')][PS.I['svpt']] / P._poids(coupe)
        self.assertGreater(tot, 0.5 * n_attendu)                               # pondéré dans le temps, mais
        self.assertLessEqual(tot, n_attendu + 1e-6)                            # jamais un match d'après

    def test_export_import(self):
        P = PS.construire(self.M)
        jour = self.M[-1]['date']
        doc = json.loads(json.dumps(P.exporter(jour)))
        Q = PS.Profils.importer(doc)
        a, _ = P.profil('gros', 'ATP', 'Clay', jour)
        b, _ = Q.profil('gros', 'ATP', 'Clay', Q.jour_export)
        for k in a:
            self.assertAlmostEqual(a[k], b[k], places=3)


class Pronostics(unittest.TestCase):
    def test_match_simule_dans_les_pronostics(self):
        import pronostics_du_jour as PJ
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            json.dump(PS.Profils().exporter(dt.date(2026, 6, 2)), open(os.path.join(d, 'simulateur', 'profils_service.json'), 'w'))
            Q = PJ.charger_profils(d)
            self.assertIsNotNone(Q)
            old = PJ.SIMULATIONS
            PJ.SIMULATIONS = 400
            try:
                r = PJ.match_simule(Q, 'x', 'y', 'ATP', 'Hard', 2, 0.7, 'u|stats')
            finally:
                PJ.SIMULATIONS = old
            self.assertEqual(r['n'], 400)
            self.assertEqual(r['profil_connu'], [False, False])
            self.assertLess(abs(r['victoire_A'] - 0.7), 0.08)            # profils vides : valeurs de repli


if __name__ == '__main__':
    unittest.main()


class Reglages(unittest.TestCase):
    def test_reglages_elargissent_et_recalent(self):
        cA, cB = S.composantes(GROS, RELANCEUR, MOY), S.composantes(RELANCEUR, GROS, MOY)
        a = S.simuler(cA, cB, 0.6, 2, 1500, 0.15, cle='r')
        b = S.simuler(cA, cB, 0.6, 2, 1500, 0.15, cle='r', reglages={'ace_facteur': 1.1, 'tau_f': 0.3})
        la = a['feuille'][0]['premiere_pct']['p90'] - a['feuille'][0]['premiere_pct']['p10']
        lb = b['feuille'][0]['premiere_pct']['p90'] - b['feuille'][0]['premiere_pct']['p10']
        self.assertGreater(lb, la + 2)                                   # fourchette de la 1re balle plus large
        self.assertGreater(b['feuille'][0]['aces']['moy'], a['feuille'][0]['aces']['moy'])
        self.assertLess(abs(b['victoire_A'] - 0.6), 0.04)                # le niveau reste ancré
        self.assertEqual(S.simuler(cA, cB, 0.6, 2, 300, 0.15, cle='r', reglages=None),
                         S.simuler(cA, cB, 0.6, 2, 300, 0.15, cle='r'))  # sans réglage : identique

    def test_regle_d_adoption(self):
        import reglage_match_simule as RG
        base = {'aces': {'prevu_moy': 4.3, 'reel_moy': 4.8, 'mae': 2.2}, 'premiere_pct': {'couverture_80_pct': 71, 'mae': 5.5},
                'breaks': {'mae': 1.4}}
        bon = {'aces': {'prevu_moy': 4.7, 'reel_moy': 4.8, 'mae': 2.2}, 'premiere_pct': {'couverture_80_pct': 79, 'mae': 5.5},
               'breaks': {'mae': 1.41}}
        pire = dict(bon, breaks={'mae': 1.5})
        self.assertTrue(RG.adopter(base, bon)[0])
        self.assertFalse(RG.adopter(base, pire)[0])                     # un écart moyen monte de plus de 2 %
        self.assertFalse(RG.adopter({}, bon)[0])
        var, tau = RG.moments_f([(100, 62, 0.62), (100, 70, 0.62), (100, 54, 0.62)])
        self.assertGreater(tau, 0)
        self.assertEqual(RG.moments_f([(100, 62, 0.62)] * 3)[0], 0.0)


class SimulationPure(unittest.TestCase):
    def test_c_est_la_simulation_qui_designe_le_vainqueur(self):
        cA, cB = S.composantes(GROS, RELANCEUR, MOY), S.composantes(RELANCEUR, GROS, MOY)
        r = S.simuler(cA, cB, None, 2, 4000, 0.15, cle='pure')
        p = S.victoire_pure(cA, cB, 2, 0.15)
        self.assertLess(abs(r['victoire_A'] - p), 4 * math.sqrt(p * (1 - p) / 4000))   # limite exacte des simulations
        meilleur = dict(GROS, w1=0.84, w2j=0.62)
        cA2 = S.composantes(meilleur, RELANCEUR, MOY)
        self.assertGreater(S.victoire_pure(cA2, cB, 2, 0.15), p)                          # mieux servir = gagner plus souvent
        self.assertAlmostEqual(S.victoire_pure(cA, cA, 2, 0.15), 0.5, places=9)          # deux joueurs identiques
        self.assertAlmostEqual(r['set1_A'] + 0, r['set1_A'])
        self.assertGreaterEqual(r['remontee'][0], 0)
