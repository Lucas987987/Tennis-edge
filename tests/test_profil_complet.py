"""Profil de réaction par joueur (8 traits adverses) et modèle complet « rien n'écarter » (28/10/2026)."""
import datetime as dt
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import arbres as A  # noqa: E402
import facteurs as F  # noqa: E402

MOYEN = tuple(F.PF_CENTRE[:5])                              # joueur au centre de chaque trait
GROS = (MOYEN[0] + 0.5, MOYEN[1] + 0.2) + MOYEN[2:]          # gros serveur : aces et 1re balle


def ligne(a, b, st_a, st_b, res_a, res_b, n=80):
    return {'a': a, 'b': b, 'jour': dt.date(2026, 9, 1), 'style': (st_a, st_b),
            'srv': [{'res': res_a, 'n': n}, {'res': res_b, 'n': n}]}


class Profil(unittest.TestCase):
    def test_retourneur_qui_souffre_contre_les_gros_serveurs(self):
        H = F.Historique()
        for i in range(12):                        # 'r' perd 7 points de plus que prévu au retour face aux gros serveurs
            H.ajouter_profil(ligne(f'gros{i}', 'r', GROS, MOYEN, 7.0, 0.0))
        v = H.variables_profil('autre_gros', 'r', GROS, MOYEN)
        self.assertGreater(v['pf_ret_adv_ace'], 0.05)     # le gros serveur d'en face devrait mieux servir contre 'r'
        self.assertGreater(v['pf_ret_adv_srv1'], 0.05)
        neutre = H.variables_profil('moyen', 'r', MOYEN, MOYEN)
        self.assertAlmostEqual(neutre['pf_ret_adv_ace'], 0.0)   # face à un serveur moyen : rien
        self.assertEqual(len(v), 16)

    def test_gaucher_et_rappel_vers_zero(self):
        H = F.Historique()
        H.infos = {f'g{i}': {'main': 'gauche'} for i in range(10)}
        H.infos['s'] = {'main': 'droite'}
        H.ajouter_profil(ligne('s', 'g0', MOYEN, MOYEN, -5.0, 0.0))
        H.infos['g_nouveau'] = {'main': 'gauche'}
        un = H.variables_profil('s', 'g_nouveau', MOYEN, MOYEN)['pf_srv_gaucher']
        for i in range(1, 10):
            H.ajouter_profil(ligne('s', f'g{i}', MOYEN, MOYEN, -5.0, 0.0))
        dix = H.variables_profil('s', 'g_nouveau', MOYEN, MOYEN)['pf_srv_gaucher']
        self.assertLess(un, 0.0)                    # 's' sert moins bien contre les gauchers
        self.assertLess(dix, un)                    # plus de preuves → effet plus net

    def test_export_et_relecture(self):
        H = F.Historique()
        for i in range(6):
            H.ajouter_profil(ligne(f'gros{i}', 'r', GROS, MOYEN, 7.0, 0.0))
        C = F.Contexte(F.contexte(H, {}, {}, 1.8e9))
        a = H.variables_profil('x', 'r', GROS, MOYEN)
        b = C.H.variables_profil('x', 'r', GROS, MOYEN)
        for k in a:
            self.assertAlmostEqual(a[k], b[k], places=3)
        self.assertIn('profil', F.GROUPES)


class ModeleComplet(unittest.TestCase):
    def test_arbres_trouvent_une_interaction(self):
        rnd = random.Random(3)
        X, n, k, off = [], [], [], []
        for _ in range(5000):
            a, b = rnd.gauss(0, 1), rnd.gauss(0, 1)
            p = 1 / (1 + math.exp(-(0.5 + (0.4 if a > 0.5 and b < 0 else 0.0))))
            X.append([a, b, rnd.random()])
            n.append(30)
            k.append(sum(rnd.random() < p for _ in range(30)))
            off.append(0.5)
        m = A.apprendre_binomial(X, n, k, off, tours=40, feuille_min=300)
        self.assertGreater(A.correction(m, [1.5, -1.0, 0.5]), 0.15)
        self.assertLess(abs(A.correction(m, [-1.5, 1.0, 0.5])), 0.08)
        self.assertEqual(list(A.importance(m, ['a', 'b', 'bruit']))[:2] in (['a', 'b'], ['b', 'a']), True)

    def test_deltas_avec_arbres(self):
        m = {'pas': 1.0, 'arbres': [{'j': 0, 's': 0.0, 'g': {'v': -0.2}, 'd': {'v': 0.3}}], 'variables': ['pf_srv_ace']}
        coefs = {'aces': {'vit_ace': 1.0}, '_arbres_service': m}
        ds, da, db = F.deltas({'pf_srv_ace': 0.5, 'vit_ace': 0.1}, coefs)
        self.assertAlmostEqual(ds, 0.3)
        self.assertAlmostEqual(da, 0.1)
        self.assertAlmostEqual(F.deltas({'pf_srv_ace': -0.5}, coefs)[0], -0.2)
        self.assertEqual(F.deltas({}, {'_arbres_service': {}})[0], 0.0)   # vide (pronostics : groupe filtré) : rien

    def test_toutes_les_variables_service(self):
        V = F.variables_completes()
        for g, d in F.GROUPES.items():
            for f in d.get('service', []):
                self.assertIn(f, V)
        self.assertEqual(len(V), len(set(V)))


if __name__ == '__main__':
    unittest.main()
