"""En direct (22/10/2026, point 8) : au premier point, le % est celui d'avant-match ; depuis un état
en cours, il correspond à des simulations jouées depuis cet état ; la forme du jour est revue
dans le bon sens d'après le score."""
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import direct as D  # noqa: E402
import match_simule as S  # noqa: E402
import modele as M  # noqa: E402


def simule_depuis(pA, pB, sa, sb, ga, gb, a_premier, pts, sg, n, graine=1):
    """Monte-Carlo naïf, point par point, depuis l'état (référence indépendante)."""
    rnd = random.Random(graine)
    gagne = 0
    for _ in range(n):
        Sa, Sb, Ga, Gb, prem, (x, y) = sa, sb, ga, gb, a_premier, pts
        while Sa < sg and Sb < sg:
            decisif = Sa == sg - 1 and Sb == sg - 1
            cible = (10 if sg == 3 else 7) if decisif else 7
            if Ga == 6 and Gb == 6:
                while not ((x >= cible and x - y >= 2) or (y >= cible and y - x >= 2)):
                    k = x + y
                    sert_a = (((k + 1) // 2) % 2 == 0) == prem
                    if rnd.random() < (pA if sert_a else 1 - pB):
                        x += 1
                    else:
                        y += 1
                a_set = x > y
                n_j = 13
            else:
                sert_a = ((Ga + Gb) % 2 == 0) == prem
                p = pA if sert_a else pB
                u, v = (x, y) if sert_a else (y, x)
                while not ((u >= 4 and u - v >= 2) or (v >= 4 and v - u >= 2)):
                    if rnd.random() < p:
                        u += 1
                    else:
                        v += 1
                serveur_gagne = u > v
                if serveur_gagne == sert_a:
                    Ga += 1
                else:
                    Gb += 1
                x, y = 0, 0
                if not ((Ga >= 6 and Ga - Gb >= 2) or (Gb >= 6 and Gb - Ga >= 2)):
                    continue
                a_set, n_j = Ga > Gb, Ga + Gb
            Sa, Sb = Sa + a_set, Sb + (not a_set)
            prem = prem if n_j % 2 == 0 else not prem
            Ga = Gb = 0
            x = y = 0
        gagne += Sa == sg
    return gagne / n


class Direct(unittest.TestCase):
    def test_premier_point_egal_avant_match(self):
        a, b = 0.66, 0.62
        avant = sum(w * S.victoire(S._sg(S._lg(a) + 0.15 * z), S._sg(S._lg(b) - 0.15 * z), 2) for z, w in zip(M._Z, M._W))
        r = 0.5 * (D.en_direct(a, b, [], 0, 0, True)['p_home'] + D.en_direct(a, b, [], 0, 0, False)['p_home'])
        self.assertAlmostEqual(r, avant, places=9)
        for sg in (2, 3):
            v = 0.5 * (D.match_depuis(a, b, 0, 0, 0, 0, True, (0, 0), sg) + D.match_depuis(a, b, 0, 0, 0, 0, False, (0, 0), sg))
            self.assertAlmostEqual(v, S.victoire(a, b, sg), places=9)

    def test_depuis_un_etat_comme_des_simulations(self):
        n = 20000
        for etat in ((1, 0, 3, 4, False, (1, 2), 2), (1, 1, 6, 6, True, (4, 5), 2), (0, 1, 5, 5, True, (3, 3), 3)):
            sa, sb, ga, gb, prem, pts, sg = etat
            p = D.match_depuis(0.64, 0.6, sa, sb, ga, gb, prem, pts, sg)
            mc = simule_depuis(0.64, 0.6, sa, sb, ga, gb, prem, pts, sg, n)
            self.assertLess(abs(p - mc), 4 * math.sqrt(p * (1 - p) / n) + 1e-3, etat)

    def test_forme_revue_dans_le_bon_sens(self):
        a, b = 0.64, 0.64
        x = D.en_direct(a, b, [(6, 1)], 4, 0, True)
        self.assertGreater(x['forme'], 0.1)                      # home domine : meilleur jour supposé
        self.assertGreater(x['p_home'], x['p_home_sans_mise_a_jour'])
        y = D.en_direct(a, b, [(1, 6)], 0, 4, True)
        self.assertLess(y['forme'], -0.1)
        self.assertAlmostEqual(D.en_direct(a, b, [], 0, 0, True, sigma=0)['p_home'], D.match_depuis(a, b, 0, 0, 0, 0, True), places=12)

    def test_jeu_et_tie_break(self):
        self.assertAlmostEqual(D.jeu_depuis(0.6, 0, 0), M.p_jeu(0.6), places=12)
        self.assertAlmostEqual(D.tb_depuis(0.6, 0.6, 0, 0, True), M.p_tiebreak(0.6, 0.6, True), places=9)
        self.assertEqual(D.jeu_depuis(0.6, 4, 2), 1.0)


if __name__ == '__main__':
    unittest.main()
