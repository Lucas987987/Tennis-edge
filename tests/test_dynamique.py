"""Point 3 (22/10/2026) : statistiques qui évoluent dans le temps — la dérive récente voit un joueur
qui progresse depuis quelques semaines ; sans changement, elle reste proche de 0 ; export/import ;
choix sur 2023 qui préfère la dérive quand le monde dérive."""
import datetime as dt
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import ajustement as AJ  # noqa: E402
import etude_dynamique as ED  # noqa: E402
import match_simule as S  # noqa: E402

cle = lambda n: n


def monde(graine=7, debut=dt.date(2024, 1, 1), semaines=70, progres_des=60):
    """20 joueurs stables ; « monte » sert comme eux jusqu'à la semaine progres_des, puis bien mieux."""
    rnd = random.Random(graine)
    J = [f"j{i}" for i in range(20)] + ['monte']
    M = []
    d = debut
    for sem in range(semaines):
        for _ in range(30):
            a, b = rnd.sample(J, 2)

            def det(srv):
                w1 = 0.80 if (srv == 'monte' and sem >= progres_des) else 0.72
                c = {'f': 0.62, 'a': 0.10, 'w1': w1, 'd': 0.07, 'w2j': 0.55}
                g, sets, st, br, ntb = S.un_match(c, c, 2, 7, rnd, True)
                x = st[0]
                return (x[S.SVPT], x[S.IN1], x[S.W1], x[S.W2], x[S.ACE], x[S.DF], x[S.BPF], x[S.BPS], x[S.SG])
            M.append({'date': d, 'fin': d + dt.timedelta(days=6), 'circuit': 'ATP', 'surface': 'Hard', 'complet': True, 'bo': 3,
                      'nom_g': a, 'nom_p': b, 'gagnant': a, 'perdant': b, 'detail': {'w': det(a), 'l': det(b)}})
        d += dt.timedelta(days=7)
    return M


class Derive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.M = monde()
        cls.date = dt.date(2024, 1, 1) + dt.timedelta(weeks=70)
        cls.fond = AJ.ajuster(cls.M, cls.date, cle, n0=150)
        cls.D = AJ.ajuster_recent(cls.M, cls.date, cle, cls.fond, n0=150, demi_vie=45)

    def test_le_progres_recent_est_vu(self):
        vrai = 0.80
        f = self.fond.taux('monte', 'j1', 'ATP', 'Hard')['w1']
        d = self.D.taux('monte', 'j1', 'ATP', 'Hard')['w1']
        self.assertLess(abs(d - vrai), abs(f - vrai))
        self.assertGreater(self.D.ecart_recent('w1', 'monte', 'j1', 'Hard'), 0.05)

    def test_joueurs_stables_inchanges(self):
        e = [abs(self.D.ecart_recent('w1', f"j{i}", 'j0', 'Hard')) for i in range(1, 20)]
        self.assertLess(sum(e) / len(e), 0.05)
        self.assertEqual(self.D.recent.eff['w1']['mu'], {('ATP', 'Hard'): 0.0})        # moyennes : celles du fond

    def test_export_import_et_choix(self):
        B = AJ.importer(self.D.exporter())
        self.assertIsInstance(B, AJ.AjusteDeux)
        self.assertAlmostEqual(B.taux('monte', 'j1', 'ATP', 'Hard')['w1'], self.D.taux('monte', 'j1', 'ATP', 'Hard')['w1'], places=2)
        self.assertIsInstance(AJ.importer(self.fond.exporter()), AJ.Ajuste)
        dyn = {'adopte': True, 'demi_vie_fond': 365, 'demi_vie_recent': 45}
        A = AJ.ajuster_choisi(self.M, self.date, cle, n0=150, dyn=AJ.lire_dynamique({'dynamique': dyn}))
        self.assertIsInstance(A, AJ.AjusteDeux)
        self.assertIsNone(AJ.lire_dynamique({'dynamique': dict(dyn, adopte=False)}))
        self.assertIsInstance(AJ.ajuster_choisi(self.M, self.date, cle, n0=150, dyn=None), AJ.Ajuste)

    def test_choix_prefere_la_derive_quand_le_monde_derive(self):
        # « monte » progresse dès la semaine 30 : jugé sur les mois suivant la date de choix
        M = monde(graine=9, debut=dt.date(2022, 6, 6), semaines=60, progres_des=25)
        V = {'fond_365': {'demi_vie_fond': 365}, 'fond_365+recent_45': {'demi_vie_fond': 365, 'demi_vie_recent': 45}}
        best, sc = ED.choisir(M, 150, journal=lambda *_: None, variantes=V, dates=[dt.date(2023, 1, 30)])
        self.assertEqual(best, 'fond_365+recent_45', sc)


if __name__ == '__main__':
    unittest.main()
