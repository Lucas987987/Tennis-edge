"""Paquet 503 : fatigue et forme du jour au tennis de table — traits sans regarder devant, apprentissage des
coefficients, règle de jugement (monde avec effet → retenu, monde sans → non retenu), rapport et journal sans nom."""
import contextlib
import datetime as dt
import io
import json
import math
import os
import random
import shutil
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..'))
sys.path.insert(0, ICI)
import elo_tt as ET  # noqa: E402
import etude_fatigue_tt as FA  # noqa: E402
from test_elo_tt import ecrire_monde  # noqa: E402

E2 = [400, 0.6, 0.5, 20]


def monde(effet, jours=300, par_jour=24, joueurs=16, seed=5, ligue='Poland'):
    """Matchs factices (tuples de ET.matchs) : chaque jour, des joueurs enchaînent les matchs toutes les 20 ou 40
    minutes. effet = (b1, b2, b3) réellement à l'œuvre dans le monde (0, 0, 0 : aucun effet du jour)."""
    rng = random.Random(seed)
    force = {i: rng.gauss(0, 0.5) for i in range(1, joueurs + 1)}
    M, debut = [], dt.date(2025, 3, 1)
    for k in range(jours):
        d = debut + dt.timedelta(days=k)
        t = int(dt.datetime(d.year, d.month, d.day, 8, tzinfo=dt.timezone.utc).timestamp())
        du_jour = []
        for j in range(par_jour):
            t += 60 * rng.choice((20, 40))
            h, a = rng.sample(range(1, joueurs + 1), 2)
            du_jour.append([t, d.isoformat(), ligue, h, a, 0, 0.5, 3, (0, 3)])
            x = FA.traits(du_jour)[-1]
            z = force[h] - force[a] + effet[0] * x[0] + effet[1] * x[1] + effet[2] * x[2]
            y = 1 if rng.random() < 1 / (1 + math.exp(-z)) else 0
            du_jour[-1][5:] = [y, 0.5 + (0.06 if y else -0.06), 3, (3, 1) if y else (1, 3)]
        M.extend(tuple(m) for m in du_jour)
    M.sort(key=lambda m: (m[0], m[3], m[4]))
    return M


class Traits(unittest.TestCase):
    J = '2025-10-02'

    def test_valeurs(self):
        M = [(1000, self.J, 'X', 1, 2, 1, 0.6, 3, (3, 0)),            # 1 bat 2
             (1000 + 1800, self.J, 'X', 1, 3, 0, 0.4, 3, (1, 3)),     # 30 min après : 1 a joué 1 match (gagné), 3 aucun
             (1000 + 5400, self.J, 'X', 3, 2, 1, 0.6, 3, (3, 2)),     # 3 : 1 match gagné il y a 60 min ; 2 : perdu il y a 90
             (1000 + 86400, '2025-10-03', 'X', 1, 2, 1, 0.6, 3, (3, 0))]   # lendemain : tout repart de zéro
        X = FA.traits(M)
        self.assertEqual(X[0], (0, 0, 0.0, 0, 0))
        self.assertEqual(X[1], (1, 1, (30 - 180) / 60, 1, 0))
        self.assertEqual(X[2], (0, 2, (60 - 90) / 60, 1, 1))
        self.assertEqual(X[3], (0, 0, 0.0, 0, 0))

    def test_repos_plafonne(self):
        M = [(0, self.J, 'X', 1, 2, 1, 0.6, 3, (3, 0)), (5 * 3600, self.J, 'X', 1, 3, 1, 0.6, 3, (3, 0))]
        self.assertEqual(FA.traits(M)[1], (1, 1, 0.0, 1, 0))          # 300 min plafonnées à 180 : comme sans match

    def test_meme_debut_ne_se_voit_pas(self):
        M = [(1000, self.J, 'X', 1, 2, 1, 0.6, 3, (3, 0)), (1000, self.J, 'X', 1, 3, 1, 0.6, 3, (3, 0)),
             (1000, self.J, 'X', 2, 3, 0, 0.4, 3, (0, 3)), (4600, self.J, 'X', 1, 4, 1, 0.6, 3, (3, 0))]
        X = FA.traits(M)
        for x in X[:3]:
            self.assertEqual(x, (0, 0, 0.0, 0, 0))
        self.assertEqual(X[3][3], 2)                                   # ensuite, les deux matchs de 1 sont comptés

    def test_ne_regarde_pas_devant(self):
        M = monde((0, 0, 0), jours=6)
        X = FA.traits(M)
        for n in (1, 17, 60, len(M) - 1):
            self.assertEqual(FA.traits(M[:n]), X[:n])                  # le préfixe ne dépend pas de la suite
        k = 40
        N = list(M)
        for i in range(k, len(N)):                                     # on renverse tous les résultats à partir de k
            m = N[i]
            N[i] = m[:5] + (1 - m[5], 1 - m[6], m[7], (m[8][1], m[8][0]))
        Z = FA.traits(N)
        fin = max(i for i, m in enumerate(M) if m[0] <= M[k][0])       # k et les matchs au même début
        self.assertEqual(Z[:fin + 1], X[:fin + 1])                     # le résultat d'un match ne change pas ses traits
        self.assertNotEqual(Z, X)


class Apprentissage(unittest.TestCase):
    def test_retrouve_les_coefficients(self):
        rng = random.Random(1)
        vrai, L = (-0.3, 0.4, 0.2), []
        for _ in range(6000):
            z, x = rng.gauss(0, 1), (rng.randint(-3, 3), rng.randint(-2, 2), rng.uniform(-3, 3))
            p = 1 / (1 + math.exp(-(z + sum(b * v for b, v in zip(vrai, x)))))
            L.append((z, x, 1 if rng.random() < p else 0))
        b = FA.apprendre(L)
        for u, v in zip(b, vrai):
            self.assertAlmostEqual(u, v, delta=0.08)
        seul = FA.apprendre(L, (1,))
        self.assertEqual((seul[0], seul[2]), (0.0, 0.0))
        self.assertGreater(seul[1], 0.2)
        self.assertGreater(FA.comparer(L, b)['gain'], 0.02)
        self.assertEqual(FA.comparer(L, [0, 0, 0])['gain'], 0)

    def test_cas_limites(self):
        self.assertEqual(FA.apprendre([(0.0, (1, 1, 1.0), 1)] * 50), [0.0, 0.0, 0.0])          # trop peu de matchs
        L = [(0.1, (i % 3 - 1, 0, 0.0), i % 2) for i in range(400)]                           # traits toujours nuls
        self.assertEqual(FA.apprendre(L), [0.0, 0.0, 0.0])
        self.assertEqual(FA.comparer([], [0, 0, 0]), {'matchs': 0})
        self.assertTrue(FA.meme_signe([-1, 2, 3], [-0.1, 5, 1]))
        self.assertFalse(FA.meme_signe([-1, 2, 3], [0.1, 5, 1]))
        self.assertTrue(FA.meme_signe([0.001, 2, 3], [-0.001, 5, 1]))      # coefficient quasi nul : son signe ne compte pas
        self.assertFalse(FA.meme_signe([0.001, 0.001, 0], [0.001, 0.001, 0]))  # aucun coefficient net : pas de sens à vérifier
        self.assertFalse(FA.meme_signe([0.1, 2, 3], [0.1, 5, 1], ecarts=(1, 1, 1)) is False)


class Etude(unittest.TestCase):
    def test_monde_avec_effet_retenu(self):
        lignes = []
        rep = FA.etudier(monde((-0.35, 0.5, 0.3)), E2, {}, lignes.append)
        po = rep['par_ligue']['Poland']
        self.assertTrue(po['produit'])
        self.assertGreaterEqual(po['jugement']['matchs'], FA.MIN_JUGES)
        self.assertTrue(po['retenu'], po)
        self.assertEqual(rep['verdict'], 'retenu')
        self.assertEqual(rep['retenu_dans'], ['Poland'])
        self.assertLess(po['coefficients_appris']['b1_matchs_deja_joues'], 0)
        self.assertGreater(po['coefficients_appris']['b2_resultat_precedent'], 0)
        self.assertEqual(len(po['chaque_trait_seul']), 3)
        T = po['favori_selon_matchs_deja_joues']
        self.assertEqual(sum(t['matchs'] for t in T.values()), po['jugement']['matchs'])
        self.assertTrue(set(T) <= set(FA.TRANCHES_DEJA))
        self.assertTrue(any('RETENU' in x for x in lignes))

    def test_monde_sans_effet_non_retenu(self):
        rep = FA.etudier(monde((0, 0, 0)), E2, {'Poland': 1.1}, lambda x: None)
        self.assertFalse(rep['par_ligue']['Poland']['retenu'])
        self.assertEqual(rep['verdict'], 'non_retenu')

    def test_ligue_hors_produit_jamais_retenue(self):
        rep = FA.etudier(monde((-0.35, 0.5, 0.3), ligue='Czech Republic'), E2, {}, lambda x: None)
        cz = rep['par_ligue']['Czech Republic']
        self.assertGreater(cz['jugement']['gain'], FA.MARGE)             # l'effet est bien là, décrit…
        self.assertFalse(cz['retenu'])                                   # … mais la ligue n'est pas du produit
        self.assertEqual(rep['verdict'], 'non_retenu')

    def test_pas_assez(self):
        rep = FA.etudier(monde((0, 0, 0), jours=20), E2, {}, lambda x: None)
        self.assertEqual(rep['verdict'], 'donnees_insuffisantes')


class Rapport(unittest.TestCase):
    """De bout en bout sur un historique factice écrit sur disque : ni nom ni identifiant dans le rapport et le journal."""

    def test_sans_nom(self):
        d = tempfile.mkdtemp()
        sortie = FA.SORTIE
        try:
            ecrire_monde(d, jours=300, debut=dt.date(2025, 3, 1))
            M = ET.matchs(d)
            lignes = []
            rep = FA.etudier(M, E2, {'Poland': 1.1}, lignes.append)
            self.assertIn('Poland', rep['par_ligue'])
            self.assertFalse(rep['par_ligue']['Czech Republic']['retenu'])
            texte = json.dumps(rep, ensure_ascii=False) + '\n'.join(lignes)
            self.assertNotIn('Joueur', texte)
            for cle in ('id_h', 'id_a', '"h"', '"a"', 'joueur'):
                self.assertNotIn(cle, texte)
            FA.SORTIE = os.path.join(d, 'rapport.json')                   # main() n'écrit pas dans le dépôt pendant le test
            tampon = io.StringIO()
            with contextlib.redirect_stdout(tampon):
                self.assertEqual(FA.main(['', d]), 0)
            self.assertNotIn('Joueur', tampon.getvalue())
            with open(FA.SORTIE, encoding='utf-8') as f:
                ecrit = f.read()
            self.assertEqual(json.loads(ecrit)['paquet'], 503)
            self.assertNotIn('Joueur', ecrit)
        finally:
            FA.SORTIE = sortie
            shutil.rmtree(d)


if __name__ == '__main__':
    unittest.main()
