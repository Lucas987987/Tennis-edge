"""Paquet 503 : face-à-face du tennis de table — rencontres passées de la même paire sans regard vers l'avenir, b du
maximum de vraisemblance, règle de jugement (monde avec un vrai effet de paire → retenu ; monde sans → non retenu),
rapport et journal sans nom ni identifiant."""
import datetime as dt
import json
import math
import os
import random
import re
import shutil
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..'))
sys.path.insert(0, ICI)
import elo_tt as ET  # noqa: E402
import etude_face_a_face_tt as FF  # noqa: E402
from test_elo_tt import ecrire_monde  # noqa: E402

E2 = [400, 0.6, 0.5, 20]


def monde(effet, jours=424, seed=11):
    """Matchs factices (tuples de ET.matchs) du 01/01/2025 au 28/02/2026 : Pologne, 12 joueurs qui se retrouvent sans
    cesse, avec un effet propre à chaque paire d'ampleur « effet » ; International, 40 joueurs, sans effet de paire."""
    rng = random.Random(seed)
    force = {i: rng.gauss(0, 0.5) for i in range(700001, 700053)}
    pol, inter = list(range(700001, 700013)), list(range(700013, 700053))
    paire = {(i, j): rng.choice((-1, 1)) * effet for i in pol for j in pol if i < j}
    M, debut = [], dt.date(2025, 1, 1)
    for k in range(jours):
        d = debut + dt.timedelta(days=k)
        t0 = int(dt.datetime(d.year, d.month, d.day, 8, tzinfo=dt.timezone.utc).timestamp())
        for j in range(36):
            lg, J = ('Poland', pol) if j % 3 else ('International', inter)
            h, a = rng.sample(J, 2)
            z = force[h] - force[a] + (paire.get((h, a), 0.0) if h < a else -paire.get((a, h), 0.0))
            p = 1 / (1 + math.exp(-z))
            y = 1 if rng.random() < p else 0
            v = min(max(p + rng.gauss(0, 0.1), 0.02), 0.98)       # part de points cohérente avec le niveau : la marge
            part = 0.5 + math.log(v / (1 - v)) / 20               # de l'Elo E2 (échelle 20) vise p, témoin étalonné
            M.append((t0 + 300 * j, d.isoformat(), lg, h, a, y, part, 3, (3, 1) if y else (1, 3)))
    M.sort(key=lambda x: (x[0], x[3], x[4]))
    return M


class Mesure(unittest.TestCase):
    def test_rencontres_passees_orientees(self):
        M = [(10, '2025-01-01', 'X', 1, 2, 1, 0.5, 3, (3, 0)), (20, '2025-01-01', 'X', 2, 1, 1, 0.5, 3, (3, 0)),
             (30, '2025-01-01', 'X', 1, 2, 0, 0.5, 3, (0, 3)), (30, '2025-01-01', 'X', 2, 1, 0, 0.5, 3, (0, 3)),
             (40, '2025-01-01', 'X', 1, 3, 1, 0.5, 3, (3, 0)), (50, '2025-01-01', 'X', 2, 1, 1, 0.5, 3, (3, 0))]
        F = FF.rencontres_passees(M, [0.6, 0.5, 0.5, 0.5, 0.5, 0.5])
        self.assertEqual(F[0], (0.0, 0))
        self.assertAlmostEqual(F[1][0], -0.4)                 # vu du joueur 2 : le joueur 1 avait gagné (résidu +0,4)
        self.assertEqual(F[1][1], 1)
        self.assertAlmostEqual(F[2][0], 0.4 - 0.5)            # vu du joueur 1 : +0,4 puis −0,5
        self.assertEqual((F[2][1], F[3][1]), (2, 2))          # même t : les deux matchs ne se voient pas
        self.assertAlmostEqual(F[3][0], -F[2][0])
        self.assertEqual(F[4], (0.0, 0))                      # autre paire : rien
        self.assertEqual(F[5][1], 4)
        self.assertAlmostEqual(F[5][0], -(0.4 - 0.5 - 0.5 + 0.5))

    def test_aucun_regard_vers_l_avenir(self):
        M = monde(0.8, jours=40)
        P = FF.temoin(M, E2, {'Poland': 1.2})
        F = FF.rencontres_passees(M, P)
        c = len(M) // 2
        while M[c][0] == M[c - 1][0]:
            c += 1
        self.assertEqual(FF.rencontres_passees(M[:c], P[:c]), F[:c])                 # la suite n'a rien changé
        M2 = M[:c] + [m[:5] + (1 - m[5],) + m[6:] for m in M[c:]]                   # on inverse tous les résultats d'après
        P2 = FF.temoin(M2, E2, {'Poland': 1.2})
        self.assertEqual(P2[:c + 1], P[:c + 1])
        self.assertEqual(FF.rencontres_passees(M2, P2)[:c + 1], F[:c + 1])
        self.assertNotEqual(FF.rencontres_passees(M2, P2)[c + 1:], F[c + 1:])

    def test_b_du_maximum_de_vraisemblance(self):
        rng = random.Random(5)
        L = []
        for _ in range(6000):
            z, n = rng.gauss(0, 0.7), rng.randint(0, 30)
            s = rng.gauss(0, 0.3) * n
            L.append((z, s, n, 1 if rng.random() < 1 / (1 + math.exp(-(z + 2.0 * s / (n + 10)))) else 0))
        b = FF.apprendre_b(L, 10)
        self.assertAlmostEqual(b, 2.0, delta=0.5)
        for autre in (b - 0.2, b + 0.2):
            self.assertLess(FF.log_loss(L, 10, b), FF.log_loss(L, 10, autre))
        self.assertEqual(FF.apprendre_b([(0.1, 0.0, 0, 1)] * 50, 5), 0.0)
        self.assertAlmostEqual(FF.comparer(L, 10, 0.0)['gain'], 0.0)
        self.assertEqual(FF.comparer([], 10, 1.0), {'matchs': 0})
        self.assertEqual(FF.apprendre([])['b'], 0.0)


class Regle(unittest.TestCase):
    def test_effet_de_paire_retenu(self):
        lg = []
        rep = FF.etudier(monde(0.9), E2, {}, lg.append)
        po, it = rep['par_ligue']['Poland'], rep['par_ligue']['International']
        self.assertTrue(po['retenu'], po)
        self.assertTrue(all(po['criteres'].values()))
        self.assertGreater(po['appris_sur_apprentissage']['b'], 0)
        self.assertIn(po['appris_sur_apprentissage']['k'], FF.GRILLE_K)
        self.assertGreater(po['jugement']['gain'], 0.01)
        self.assertAlmostEqual(po['jugement']['log_loss_temoin'] - po['jugement']['log_loss_candidat'], po['jugement']['gain'], places=4)
        d = po['descriptif']
        self.assertGreaterEqual(d['part_au_moins_1_rencontres_pct'], d['part_au_moins_5_rencontres_pct'])
        self.assertGreaterEqual(d['part_au_moins_5_rencontres_pct'], d['part_au_moins_20_rencontres_pct'])
        self.assertGreater(d['part_au_moins_20_rencontres_pct'], 50)
        self.assertGreater(d['au_moins_5_rencontres']['matchs'], 1000)
        self.assertFalse(it['retenu'], it)                    # même monde, ligue sans effet de paire
        self.assertEqual(rep['ligues_retenues'], ['Poland'])
        self.assertEqual(rep['verdict'], 'retenu')
        self.assertEqual(rep['paquet'], 503)
        self.assertIn('RETENU', '\n'.join(lg))
        self.assertIsNone(re.search(r'\b7000\d\d\b', json.dumps(rep) + '\n'.join(lg)))   # aucun identifiant de joueur

    def test_sans_effet_non_retenu(self):
        rep = FF.etudier(monde(0.0), E2, {'International': 1.249}, lambda x: None)
        self.assertFalse(rep['par_ligue']['Poland']['retenu'])
        self.assertFalse(rep['par_ligue']['International']['retenu'])
        self.assertEqual(rep['verdict'], 'non_retenu')
        self.assertEqual(rep['ligues_retenues'], [])

    def test_autre_ligue_decrite_jamais_retenue(self):
        M = [m[:2] + ('Czech Republic' if m[2] == 'Poland' else m[2],) + m[3:] for m in monde(0.9)]
        rep = FF.etudier(M, E2, {}, lambda x: None)
        cz = rep['par_ligue']['Czech Republic']
        self.assertTrue(all(cz['criteres'].values()))
        self.assertFalse(cz['produit'])
        self.assertFalse(cz['retenu'])
        self.assertEqual(rep['verdict'], 'non_retenu')

    def test_moins_de_1000_juges_non_retenu(self):
        M = monde(0.9)
        la = [x for x in FF.lignes(M, *self._pf(M), range(len(M)), 'Poland')]
        v = FF.juger(la[2000:6000], la[6000:6900], True)
        self.assertFalse(v['criteres']['au_moins_1000_juges'])
        self.assertFalse(v['retenu'])

    @staticmethod
    def _pf(M):
        P = FF.temoin(M, E2, {})
        return P, FF.rencontres_passees(M, P)

    def test_pas_assez(self):
        self.assertEqual(FF.etudier(monde(0.5, jours=30), E2, {}, lambda x: None)['verdict'], 'donnees_insuffisantes')


class Fichiers(unittest.TestCase):
    def test_main_sur_un_historique_factice_sans_nom(self):
        d = tempfile.mkdtemp()
        sortie, FF.SORTIE = FF.SORTIE, os.path.join(d, 'rapport.json')
        try:
            ecrire_monde(d, jours=330, debut=dt.date(2025, 3, 1))
            lg = []
            rep = FF.etudier(ET.matchs(d), E2, {'Poland': 1.1}, lg.append)
            self.assertIn('Poland', rep['par_ligue'])
            self.assertIn('retenu', rep['par_ligue']['Poland'])
            self.assertFalse(rep['par_ligue']['Czech Republic']['retenu'])
            self.assertNotIn('Joueur', json.dumps(rep) + '\n'.join(lg))
            sys.stdout, vrai = open(os.devnull, 'w'), sys.stdout
            try:
                self.assertEqual(FF.main(['x', d]), 0)
            finally:
                sys.stdout.close()
                sys.stdout = vrai
            with open(FF.SORTIE, encoding='utf-8') as f:
                txt = f.read()
            self.assertEqual(json.loads(txt)['etude'], 'face_a_face')
            self.assertNotIn('Joueur', txt)
        finally:
            FF.SORTIE = sortie
            shutil.rmtree(d)

    def test_regle_ecrite_dans_l_en_tete(self):
        self.assertIn('AVANT TOUT ESSAI', FF.__doc__)
        self.assertEqual((FF.MIN_JUGES, FF.MARGE, FF.ERREURS_TYPES, FF.GRILLE_K), (1000, 0.001, 2.0, (5, 10, 20, 40)))
        self.assertEqual(FF.LIGUES_PRODUIT, ('International', 'Poland'))


if __name__ == '__main__':
    unittest.main()
