"""Étude de la forme du jour (22/10/2026) : retrouve une forme simulée (et son absence),
le signe adversaires, et la variation de la 1re balle, sur des feuilles set par set synthétiques."""
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import etude_forme_du_jour as EF  # noqa: E402

sg = lambda z: 1 / (1 + math.exp(-z))
lg = lambda p: math.log(p / (1 - p))


def fiches(sigma, tau_f, n_matchs=2500, graine=1):
    rnd = random.Random(graine)
    joueurs = {f"Joueur {chr(97 + i // 26)}{chr(97 + i % 26)}": (rnd.gauss(0.55, 0.15), rnd.gauss(0.5, 0.2)) for i in range(120)}
    noms = list(joueurs)
    out = []
    for k in range(n_matchs):
        a, b = rnd.sample(noms, 2)
        d = rnd.gauss(0, sigma)
        fa, fb = rnd.gauss(0, tau_f), rnd.gauss(0, tau_f)
        per = {}
        for s, nom_p in enumerate(('1ST', '2ND', '3RD')[:rnd.choice((2, 3))]):
            ligne = {}
            vals = []
            for (j, dd, ff) in ((a, d, fa), (b, -d, fb)):
                n = 30 + rnd.randint(0, 15)
                p = sg(joueurs[j][0] + dd)
                f = sg(joueurs[j][1] + ff)
                vals.append((n, sum(rnd.random() < p for _ in range(n)), sum(rnd.random() < f for _ in range(n))))
            (n1, k1, f1), (n2, k2, f2) = vals
            ligne['firstServeAccuracy'] = [f1, n1, f2, n2]
            ligne['servicePointsScored'] = [k1, None, k2, None]
            per[nom_p] = ligne
        out.append({'id': k, 'categorie': 'ATP', 'statut': {'texte': 'Ended'}, 'home': {'nom': a}, 'away': {'nom': b}, 'stats': per})
    return out


class Forme(unittest.TestCase):
    def mesurer(self, sigma, tau_f):
        M = EF.preparer(fiches(sigma, tau_f))
        R = EF.residus(M)
        z = EF.mesures(R, M, random.Random(3))
        pq = sum(x['p'] * (1 - x['p']) for x in R) / len(R)
        return z, pq

    def test_forme_retrouvee(self):
        z, pq = self.mesurer(0.35, 0.0)
        forme = z['A_meme_match'] - z['A_temoin']
        self.assertAlmostEqual(EF.en_sigma(forme, pq), 0.35, delta=0.12)
        self.assertLess(z['B_meme_set'] - z['B_temoin'], 0)                    # adversaires : signe négatif

    def test_pas_de_forme(self):
        z, pq = self.mesurer(0.0, 0.0)
        self.assertLess(abs(EF.en_sigma(z['A_meme_match'] - z['A_temoin'], pq)), 0.15)

    def test_premiere_balle(self):
        M = EF.preparer(fiches(0.0, 0.3))
        R = EF.residus(M)
        z = EF.mesures(R, M, random.Random(3))
        fq = sum(x['f'] * (1 - x['f']) for x in R) / len(R)
        self.assertAlmostEqual(EF.en_sigma(z['C_meme_match'] - z['C_temoin'], fq), 0.3, delta=0.12)


if __name__ == '__main__':
    unittest.main()
