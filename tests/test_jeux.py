"""Couche « jeux » (22/10/2026) : la simulation apprend aussi des matchs SANS feuille détaillée, à partir
des jeux gagnés ; retrouve la force cachée des joueurs ; ignore les matchs avec feuille ; point-in-time."""
import datetime as dt
import os
import random
import statistics
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import ajustement as AJ  # noqa: E402
import modele as Mo  # noqa: E402


class Plat:
    def taux(self, *a):
        return {'f': 0.62, 'a': 0.1, 'w1': 0.70, 'd': 0.07, 'w2j': 0.52}


def monde(graine=1, n=6000):
    rnd = random.Random(graine)
    J = [f"p{i}" for i in range(30)]
    force = {p: rnd.gauss(0, 0.25) for p in J}
    M, d0 = [], dt.date(2025, 1, 1)
    for _ in range(n):
        a, b = rnd.sample(J, 2)
        d = force[a] - force[b]
        pa = AJ._p_service(AJ._decale(Plat().taux(), d))
        pb = AJ._p_service(AJ._decale(Plat().taux(), -d))
        ga = sum((rnd.random() < Mo.p_jeu(pa)) if g % 2 == 0 else (rnd.random() > Mo.p_jeu(pb)) for g in range(22))
        gb = 22 - ga
        w, l, sc = (a, b, (ga, gb)) if ga >= gb else (b, a, (gb, ga))
        M.append({'date': d0, 'fin': d0, 'detail': None, 'complet': True, 'sets': [sc], 'nom_g': w, 'nom_p': l,
                  'circuit': 'ITF', 'surface': 'Hard'})
    return M, force, J


class Jeux(unittest.TestCase):
    def test_retrouve_la_force(self):
        M, force, J = monde()
        G = AJ.ajuster_jeux(M, dt.date(2025, 2, 1), lambda n: n, Plat(), lam=20)
        xs, ys = [force[p] for p in J], [G.get(p, 0) for p in J]
        self.assertGreater(statistics.correlation(xs, ys), 0.97)
        t = AJ.avec_jeux(Plat().taux(), G, 'p0', 'p1')
        self.assertEqual(t['w1'] > 0.70, G.get('p0', 0) > G.get('p1', 0))

    def test_point_in_time_et_feuilles_ignorees(self):
        M, _, _ = monde(n=200)
        self.assertEqual(AJ.ajuster_jeux(M, dt.date(2025, 1, 1), lambda n: n, Plat()), {})     # rien de fini avant
        for m in M:
            m['detail'] = {'w': (), 'l': ()}
        self.assertEqual(AJ.ajuster_jeux(M, dt.date(2025, 2, 1), lambda n: n, Plat()), {})     # déjà dans les points
        self.assertIs(AJ.avec_jeux(Plat().taux(), {}, 'a', 'b')['w1'], 0.70)


if __name__ == '__main__':
    unittest.main()
