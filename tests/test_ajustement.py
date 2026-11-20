"""Ajustement au niveau des adversaires (22/10/2026) : un serveur de Challenger face à des relanceurs
faibles n'est plus surévalué contre un joueur du circuit principal ; point-in-time ; export/import."""
import datetime as dt
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import ajustement as AJ  # noqa: E402
import match_simule as S  # noqa: E402
import profils_service as PS  # noqa: E402

MOY = {'f': 0.62, 'a': 0.12, 'd': 0.07, 'w1': 0.73, 'w2j': 0.56, 'ra': 0.12, 'r1': 0.73, 'r2j': 0.56}
cle = lambda n: n


def monde(graine=5):
    """ATP : bons relanceurs. CH : relanceurs faibles. Même qualité de service partout ;
    des « passeurs » jouent sur les deux circuits et relient les échelles."""
    rnd = random.Random(graine)
    atp = [f"atp{i}" for i in range(20)]
    ch = [f"ch{i}" for i in range(20)]
    passeurs = [f"pas{i}" for i in range(6)]
    retour = {**{j: 0.68 for j in atp}, **{j: 0.78 for j in ch}, **{j: 0.73 for j in passeurs}}   # w1 concédé
    M = []
    d = dt.date(2024, 1, 1)
    for sem in range(80):
        for _ in range(25):
            circ = rnd.choice(('ATP', 'CH'))
            pool = (atp if circ == 'ATP' else ch) + passeurs
            a, b = rnd.sample(pool, 2)
            def det(srv, ret):
                c = {'f': 0.62, 'a': 0.10, 'w1': retour[ret], 'd': 0.07, 'w2j': 0.55}
                g, sets, st, br, ntb = S.un_match(c, c, 2, 7, rnd, True)
                x = st[0]
                return (x[S.SVPT], x[S.IN1], x[S.W1], x[S.W2], x[S.ACE], x[S.DF], x[S.BPF], x[S.BPS], x[S.SG])
            M.append({'date': d, 'fin': d + dt.timedelta(days=7), 'circuit': circ, 'surface': 'Hard',
                      'nom_g': a, 'nom_p': b, 'gagnant': a, 'perdant': b, 'detail': {'w': det(a, b), 'l': det(b, a)}})
        d += dt.timedelta(days=7)
    return M


class Ajustement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.M = monde()
        cls.date = dt.date(2025, 9, 1)
        cls.A = AJ.ajuster(cls.M, cls.date, cle)

    def test_retour_des_challengers_reconnu_plus_faible(self):
        R = self.A.eff['w1']['R']
        r_atp = sum(R.get(f"atp{i}", 0) for i in range(20)) / 20
        r_ch = sum(R.get(f"ch{i}", 0) for i in range(20)) / 20
        self.assertGreater(r_atp, r_ch + 0.15)

    def test_challenger_plus_surevalue_face_au_circuit_principal(self):
        # vérité : un joueur de CH qui sert contre un relanceur ATP gagne 68 % derrière la 1re
        ajuste = self.A.taux('ch3', 'atp5', 'ATP', 'Hard')['w1']
        P = PS.construire(self.M, jusqu_au=self.date)
        mu = P.moyenne('ATP', 'Hard')
        brut = S.composantes(P.profil('ch3', 'ATP', 'Hard', self.date)[0], P.profil('atp5', 'ATP', 'Hard', self.date)[0], mu)['w1']
        self.assertLess(abs(ajuste - 0.68), abs(brut - 0.68))
        self.assertLess(abs(ajuste - 0.68), 0.03)

    def test_point_in_time_et_export(self):
        tot = len(AJ.observations(self.M, dt.date(2024, 6, 1), cle))
        self.assertEqual(tot, 2 * sum(1 for m in self.M if m['fin'] < dt.date(2024, 6, 1)))
        B = AJ.Ajuste.importer(self.A.exporter())
        for c, v in self.A.taux('ch3', 'atp5', 'ATP', 'Hard').items():
            self.assertAlmostEqual(B.taux('ch3', 'atp5', 'ATP', 'Hard')[c], v, places=2)
        self.assertAlmostEqual(B.taux('x', 'y', 'ITFH', 'Clay')['w1'], B.taux('x', 'y', 'CH', 'Clay')['w1'], places=9)   # repli


if __name__ == '__main__':
    unittest.main()


class Integration(unittest.TestCase):
    def test_choix_du_prior_et_pronostics(self):
        M = monde(9)
        n0, sc = AJ.choisir_n0(M, cle, grille=(150.0, 500.0), dates=[dt.date(2024, 9, 1), dt.date(2025, 1, 1)], journal=lambda *_: None)
        self.assertIn(n0, (150.0, 500.0))
        self.assertEqual(set(sc), {150.0, 500.0})
        import pronostics_du_jour as PJ
        P = PS.construire(M, jusqu_au=dt.date(2025, 9, 1))
        doc = P.exporter(dt.date(2025, 8, 31))
        doc['ajuste'] = AJ.ajuster(M, dt.date(2025, 9, 1), cle, n0=n0).exporter()
        Q = PS.Profils.importer(doc)
        self.assertIsNotNone(Q.ajuste)
        old = (PJ.CHOIX, PJ.SIMULATIONS)
        PJ.SIMULATIONS = 600
        try:
            PJ.CHOIX = 'ajustees'
            r = PJ.match_simule(Q, 'atp1', 'ch2', 'ATP', 'Hard', 2, None, 'x|simulation')
            self.assertEqual(r['composantes'], 'ajustees')
            PJ.CHOIX = 'profils'
            r2 = PJ.match_simule(Q, 'atp1', 'ch2', 'ATP', 'Hard', 2, None, 'x|simulation')
            self.assertEqual(r2['composantes'], 'profils')
            # le joueur de Challenger (relanceurs faibles) n'est plus surévalué : sa victoire baisse une fois ajusté
            # atp1 relance mieux que ch2 (même service) : ajusté, il gagne plus souvent que ne le disent les profils bruts,
            # gonflés par le service de ch2 face aux relanceurs faibles du Challenger
            self.assertGreater(r['victoire_A'], r2['victoire_A'])
            self.assertGreater(r['victoire_A'], 0.5)
        finally:
            PJ.CHOIX, PJ.SIMULATIONS = old
