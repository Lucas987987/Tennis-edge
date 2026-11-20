"""Simulateur point par point (21/10/2026) : calcul exact, règles du tennis,
ancrage au marché, lecture Sackmann / tennis-data, notes service-retour."""
import datetime as dt
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import donnees as D  # noqa: E402
import modele as M  # noqa: E402
import notes as N  # noqa: E402


class Modele(unittest.TestCase):
    def test_jeu_valeurs_connues(self):
        self.assertAlmostEqual(M.p_jeu(0.6), 0.7357, places=4)
        self.assertAlmostEqual(M.p_jeu(0.5), 0.5, places=12)

    def test_symetrie_et_sommes(self):
        for sg in (2, 3):
            r = M.match(0.63, 0.63, sg)
            self.assertAlmostEqual(r['victoire'], 0.5, places=9)
            self.assertAlmostEqual(sum(r['total_jeux'].values()), 1.0, places=9)
            self.assertAlmostEqual(sum(r['sets'].values()), 1.0, places=9)
            self.assertAlmostEqual(M.moyenne(r['ecart_jeux']), 0.0, places=9)
        self.assertAlmostEqual(M.p_tiebreak(0.7, 0.7, True), 0.5, places=9)

    def test_valeurs_controlees_par_monte_carlo(self):
        # 100 000 matchs tirés au hasard (21/10/2026) : 0,7759 / set 1 0,6941 / 24,32 jeux
        r = M.match(0.66, 0.60)
        self.assertAlmostEqual(r['victoire'], 0.775, delta=0.002)
        self.assertAlmostEqual(r['set1'], 0.6929, delta=0.002)
        self.assertAlmostEqual(M.moyenne(r['total_jeux']), 24.32, delta=0.02)
        self.assertEqual(set(r['sets']), {'2-0', '2-1', '1-2', '0-2'})
        self.assertEqual(min(r['total_jeux']), 12)
        self.assertEqual(max(r['total_jeux']), 39)          # 7-6 6-7 7-6
        r5 = M.match(0.66, 0.60, 3)
        self.assertAlmostEqual(r5['victoire'], 0.8282, delta=0.002)

    def test_tiebreak_final_a_10(self):
        # un set décisif à tie-break de 10 avantage davantage le meilleur
        a = M.match(0.66, 0.62, 3, tb_final=10)['victoire']
        b = M.match(0.66, 0.62, 3, tb_final=7)['victoire']
        self.assertGreater(a, b)

    def test_ancrage(self):
        a, b = M.ancrer(0.70, 0.58, 0.40)
        self.assertAlmostEqual(M.match(a, b)['victoire'], 0.40, places=5)
        # profil gardé : la somme des logits de service (deux gros serveurs ou non)
        self.assertAlmostEqual(M.logit(a) + M.logit(b), M.logit(0.70) + M.logit(0.58), places=9)
        x, y = M.depuis_marche(0.75)
        self.assertAlmostEqual(M.match(x, y)['victoire'], 0.75, places=5)


class Donnees(unittest.TestCase):
    def test_noms(self):
        self.assertIn(('del potro', 'j'), D.cles_sackmann('Juan Martin del Potro'))
        self.assertEqual(D.cle_td('Del Potro J.M.'), ('del potro', 'j'))
        self.assertEqual(D.cle_td('Auger-Aliassime F.'), ('auger aliassime', 'f'))
        self.assertIn(('auger aliassime', 'f'), D.cles_sackmann('Felix Auger-Aliassime'))
        self.assertIn(('zheng', 'q'), D.cles_sackmann('Qinwen Zheng'))

    def test_score(self):
        self.assertEqual(D.score_sets('6-4 3-6 7-6(5)'), ([(6, 4), (3, 6), (7, 6)], True))
        self.assertFalse(D.score_sets('6-4 2-1 RET')[1])
        self.assertFalse(D.score_sets('W/O')[1])

    def test_jointure(self):
        m = [{'date': dt.date(2024, 5, 20), 'circuit': 'ATP', 'nom_g': 'Alex de Minaur', 'nom_p': 'Casper Ruud'},
             {'date': dt.date(2024, 7, 1), 'circuit': 'ATP', 'nom_g': 'Alex de Minaur', 'nom_p': 'Casper Ruud'}]
        td = [{'date': dt.date(2024, 5, 24), 'vainqueur': 'De Minaur A.', 'perdant': 'Ruud C.'},
              {'date': dt.date(2024, 6, 15), 'vainqueur': 'De Minaur A.', 'perdant': 'Ruud C.'}]
        p = D.joindre(td, m)
        self.assertEqual(len(p), 1)
        self.assertIs(p[0][1], m[0])


class Notes(unittest.TestCase):
    def test_retrouve_la_verite_sans_regarder_le_futur(self):
        rnd = random.Random(3)
        vrai = {f"p{i}": (rnd.gauss(0, 0.3), rnd.gauss(0, 0.2)) for i in range(20)}
        matchs = []
        d = dt.date(2024, 1, 1)
        for sem in range(60):
            for _ in range(10):
                a, b = rnd.sample(sorted(vrai), 2)
                st = {}
                for s, (x, y) in (('w', (a, b)), ('l', (b, a))):
                    p = 1 / (1 + math.exp(-(0.5 + vrai[x][0] - vrai[y][1])))
                    n = 80
                    st[s] = (n, sum(rnd.random() < p for _ in range(n)))
                matchs.append({'date': d, 'fin': d + dt.timedelta(days=8), 'circuit': 'ATP', 'surface': 'Hard',
                               'gagnant': a, 'perdant': b, 'stats': st})
            d += dt.timedelta(days=7)
        nt = N.noter(matchs, d, demi_vie=10000, n0=50, tours=10)
        ks = sorted(vrai)
        c = sum((nt.S[k] - 0) * vrai[k][0] for k in ks) / math.sqrt(sum(nt.S[k] ** 2 for k in ks) * sum(vrai[k][0] ** 2 for k in ks))
        self.assertGreater(c, 0.9)
        self.assertAlmostEqual(nt.mu[('ATP', 'Hard')], 0.5, delta=0.08)
        # point-in-time : un tournoi non terminé au lundi n'est jamais lu
        tot = sum(m['stats']['w'][0] + m['stats']['l'][0] for m in matchs if m['fin'] < dt.date(2024, 3, 4))
        nt2 = N.noter(matchs, dt.date(2024, 3, 4), demi_vie=10 ** 9, n0=50, tours=1)
        self.assertAlmostEqual(sum(nt2.pts.values()), tot, delta=1e-3)


if __name__ == '__main__':
    unittest.main()


class FormeDuJour(unittest.TestCase):
    def test_sigma_zero_identique(self):
        a, b = M.match(0.66, 0.60), M.match_forme(0.66, 0.60, 2, 0.0)
        self.assertEqual(a['victoire'], b['victoire'])

    def test_plus_de_deux_sets_moins_de_jeux(self):
        r0 = M.prix_depuis_pinnacle(0.70, 0.64, 2, 0.0)
        r1 = M.prix_depuis_pinnacle(0.70, 0.64, 2, 0.15)
        self.assertAlmostEqual(r1['victoire'], 0.70, places=4)        # niveau gardé (celui de Pinnacle)
        deux = lambda r: r['sets']['2-0'] + r['sets']['0-2']
        self.assertGreater(deux(r1), deux(r0) + 0.05)                   # réglage 21/10 : 55 % -> 63 %
        self.assertLess(M.moyenne(r1['total_jeux']), M.moyenne(r0['total_jeux']))
        self.assertAlmostEqual(sum(r1['sets'].values()), 1.0, places=9)


class MarchesSets(unittest.TestCase):
    def test_cote_a_l_instant(self):
        import importlib.util
        sp = importlib.util.spec_from_file_location(
            'tennis_edge_t_ms', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur', 'marches_sets.py'))
        ms = importlib.util.module_from_spec(sp)
        argv = sys.argv
        sys.argv = ['x']
        try:
            sp.loader.exec_module(ms)
        finally:
            sys.argv = argv
        r = {'home_curve': [['2026-10-20T10:00:00', 1.9], ['2026-10-20T11:40:00', 1.8], ['2026-10-20T12:10:00', 3.5]],
             'away_curve': [['2026-10-20T10:00:00', 2.0], ['2026-10-20T11:40:00', 2.1], ['2026-10-20T12:10:00', 1.3]]}
        t = dt.datetime(2026, 10, 20, 11, 30)                           # 30 min avant un début à 12:00
        self.assertEqual(ms.paire_a(r, t), (1.9, 2.0))                  # jamais la cote d'après
        self.assertEqual(ms.paire_a(r, dt.datetime(2026, 10, 20, 12, 0)), (1.8, 2.1))   # pas la cote en direct
        self.assertIsNone(ms.paire_a(r, dt.datetime(2026, 10, 20, 15, 0), age_max=60))   # trop vieille
        self.assertAlmostEqual(ms.juste(2.0, 2.0), 0.5, places=9)
        self.assertTrue(ms.cinq_sets('Wimbledon Men Singles'))
        self.assertFalse(ms.cinq_sets('Wimbledon Women Singles'))


class ScoresComplets(unittest.TestCase):
    def test_ordre_reel_et_somme(self):
        r = M.scores_complets(0.66, 0.62, 2, 0.15, top=10 ** 6)
        tot = sum(p for _, p in r['scores'])
        self.assertAlmostEqual(tot, 1.0, places=9)
        gagne = sum(p for s, p in r['scores'] if sum(int(a) > int(b) for a, b in (x.split('-') for x in s.split())) == 2)
        self.assertAlmostEqual(gagne, M.match_forme(0.66, 0.62, 2, 0.15)['victoire'], places=9)
        # le vainqueur peut perdre le 1er set : ces suites existent et sont comptées
        d = dict(r['scores'])
        self.assertGreater(d['4-6 6-3 6-4'], 0)
        rem = sum(p for s, p in d.items() if s.split()[0].split('-')[0] < s.split()[0].split('-')[1] and len(s.split()) == 3
                  and int(s.split()[2].split('-')[0]) > int(s.split()[2].split('-')[1]))
        self.assertAlmostEqual(rem, r['remontee_A'], places=9)

    def test_effet_du_service_sur_l_ordre(self):
        # joueurs identiques : « 6-3 puis 6-4 » plus probable que « 6-4 puis 6-3 » (qui sert le dernier jeu)
        d = dict(M.scores_complets(0.63, 0.63, 2, 0.0, top=10 ** 6)['scores'])
        self.assertGreater(d['6-3 6-4'], d['6-4 6-3'])
        self.assertAlmostEqual(d['6-4 6-4'], d['4-6 4-6'], places=12)
