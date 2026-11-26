# -*- coding: utf-8 -*-
"""Tests de simulateur/etude_styles_approfondie.py (paquet 457), sur données factices : aucune archive nécessaire."""
import datetime as dt
import json
import math
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ICI))
import etude_styles_approfondie as SA  # noqa: E402

BORNES = (dt.date(2018, 1, 1), dt.date(2021, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 6, 1))
JOURS = (dt.date(2019, 3, 1), dt.date(2020, 3, 1), dt.date(2021, 3, 1), dt.date(2022, 3, 1),
         dt.date(2023, 3, 1), dt.date(2024, 3, 1), dt.date(2025, 3, 1))


def _sg(z):
    return 1 / (1 + math.exp(-z))


def lignes(effet, n=700, graine=7, circuit='ATP'):
    """Matchs factices : la réalité suit logit Elo + effet · (a0·b5 − a5·b0) (aces contre retour de 1re)."""
    rnd = random.Random(graine)
    rows = []
    for jour in JOURS:
        for i in range(n):
            a = [rnd.gauss(0, 0.02) for _ in range(SA.K)]
            b = [rnd.gauss(0, 0.02) for _ in range(SA.K)]
            z = rnd.gauss(0, 1.0)
            x = (a[0] * b[5] - a[5] * b[0]) / 0.02 ** 2
            if rnd.random() < _sg(z + effet * x):
                rows.append((circuit, jour, 'Hard' if i % 2 else 'Clay', z, a, b))
            else:
                rows.append((circuit, jour, 'Hard' if i % 2 else 'Clay', -z, b, a))
        rows.append((circuit, jour, 'Hard', 0.4, None, None))             # joueur non décrit : jamais concerné
    return rows


class TestStylesApprofondie(unittest.TestCase):
    def test_un_vrai_effet_est_retrouve_et_retenu(self):
        j = SA.juger_circuit(lignes(0.5), BORNES)
        self.assertEqual(j['concernes_juges'], 3 * 700)
        self.assertEqual(j['matchs_juges'], 3 * 701)
        self.assertGreater(j['gain_juge']['gain'], SA.MARGE)
        self.assertTrue(j['meme_sens_sur_les_deux_periodes'])
        self.assertTrue(j['retenu'], j['raisons'])
        self.assertEqual(j['rencontres_aux_poids_les_plus_forts'][0]['mesures'], 'aces × retour de 1re gagné')
        self.assertGreater(j['rencontres_aux_poids_les_plus_forts'][0]['poids'], 0)

    def test_sans_effet_rien_n_est_retenu(self):
        j = SA.juger_circuit(lignes(0.0, graine=11), BORNES)
        self.assertFalse(j['retenu'])
        self.assertLess(j['gain_juge']['gain'], SA.MARGE)
        self.assertTrue(j['raisons'])

    def test_moins_de_1000_matchs_juges_jamais_retenu(self):
        j = SA.juger_circuit(lignes(0.5, n=200), BORNES)
        self.assertLess(j['concernes_juges'], SA.MIN_JUGES)
        self.assertFalse(j['retenu'])
        self.assertIn('moins de 1000 matchs concernés jugés', j['raisons'])

    def test_trop_peu_de_matchs(self):
        j = SA.juger_circuit(lignes(0.5, n=5), BORNES)
        self.assertFalse(j['retenu'])

    def test_rencontres_antisymetriques(self):
        rnd = random.Random(3)
        a = [rnd.gauss(0, 1) for _ in range(SA.K)]
        b = [rnd.gauss(0, 1) for _ in range(SA.K)]
        ech = [1.0 + k for k in range(SA.K)]
        ab, ba = SA.rencontres(a, b, ech), SA.rencontres(b, a, ech)
        self.assertEqual(len(ab), 28)
        for u, v in zip(ab, ba):
            self.assertAlmostEqual(u, -v)
        self.assertTrue(all(abs(v) < 1e-12 for v in SA.rencontres(a, a, ech)))

    def test_ajuster_poids_nuls_sans_information_et_penalite(self):
        R = [r for r in lignes(0.5, n=300) if r[4] is not None]
        X, Z = SA.tableau(R, SA.echelles(R))
        doux, fort = SA.ajuster(X, Z, 10.0), SA.ajuster(X, Z, 1e6)
        self.assertGreater(sum(b * b for b in doux), sum(b * b for b in fort))
        self.assertLess(max(abs(b) for b in fort), 1e-2)
        self.assertGreater(SA.gain(X, Z, doux)['gain'], 0)
        self.assertEqual(SA.gain([], [], doux), {'matchs': 0})

    @staticmethod
    def _match(jour, g, p, ace_g, circuit='ATP'):
        # détail = (svpt, in1, w1, w2, ace, df, bpf, bps, sg)
        return {'date': jour, 'circuit': circuit, 'surface': 'Hard', 'gagnant': g, 'perdant': p, 'minutes': 90,
                'detail': {'w': (80, 50, 38, 16, ace_g, 2, 4, 3, 12), 'l': (80, 50, 33, 14, 4, 3, 8, 5, 12)}}

    def test_profils_sans_fuite(self):
        P = SA.Profils()
        d0 = dt.date(2017, 1, 2)
        for i in range(40):                                               # établit la moyenne du circuit
            P.ajouter(self._match(d0 + dt.timedelta(days=7 * (i // 4)), f"x{i}", f"y{i}", 4))
        jour = dt.date(2018, 1, 1)
        self.assertEqual(P.profil('serveur', jour), (None, 0.0))
        P.ajouter(self._match(jour, 'serveur', 'autre', 20))
        # le même jour (même tournoi) : le match n'est pas encore dans le profil
        self.assertEqual(P.profil('serveur', jour), (None, 0.0))
        f, n = P.profil('serveur', jour + dt.timedelta(days=7))
        self.assertGreater(f[0], 0)                                       # plus d'aces que la moyenne
        self.assertGreater(P.profil('autre', jour + dt.timedelta(days=7))[0][5], -1)
        self.assertAlmostEqual(n, 80 * 0.5 ** (7 / 365.0), places=6)
        # un an plus tard : le poids a diminué de moitié, la mesure est plus rapprochée de 0
        f2, n2 = P.profil('serveur', jour + dt.timedelta(days=372))
        self.assertLess(n2, n / 1.9)
        self.assertLess(f2[0], f[0])

    def test_essais_du_match(self):
        e = SA.essais_du_match((80, 50, 38, 16, 9, 2), (70, 40, 28, 15, 3, 1), 100)
        self.assertEqual(e[0], (80, 9))
        self.assertEqual(e[3], (30, 16))
        self.assertEqual(e[5], (40, 12))
        self.assertEqual(e[6], (30, 15))
        self.assertEqual(e[7], (150, 6000.0))
        self.assertEqual(SA.essais_du_match((80, 50, 38, 16, 9, 2), (70, 40, 28, 15, 3, 1), None)[7], (0, 0.0))

    def test_etude_journal_et_rapport_sans_mot_interdit(self):
        rows = lignes(0.5, n=400, circuit='ATP') + lignes(0.0, n=400, graine=13, circuit='WTA')
        ch = lignes(0.0, n=10, graine=17, circuit='CH')
        e = SA.etudier(rows + ch)
        self.assertEqual(set(e['circuits']), {'ATP', 'WTA', 'CH'})
        self.assertFalse(e['circuits']['CH']['retenu'])
        self.assertIn('challenger_archive_2018_2022_puis_2023_pour_memoire', e)
        self.assertNotIn('retenu', e['challenger_archive_2018_2022_puis_2023_pour_memoire'].get('gain_juge', {}))
        with open(SA.GABARIT_JOURNAL, encoding='utf-8') as f:
            gabarit = json.load(f)
        entree = SA.entree_journal({'etude': e}, gabarit)
        self.assertEqual(entree['paquet'], 457)
        self.assertEqual(entree['statut'], 'etude')
        texte = json.dumps({'etude': e, 'entree': entree}, ensure_ascii=False).lower()
        self.assertNotIn('marché', texte)
        self.assertNotIn('cote ', texte.replace('aucune cote ', ''))
        self.assertIn('RÉSULTAT', entree['quoi'])


if __name__ == '__main__':
    unittest.main()
