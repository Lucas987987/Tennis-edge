# -*- coding: utf-8 -*-
"""Paquet 289 — étude des duels de serveurs (simulateur/etude_pente_service.py), sur données factices :
β retrouvé, indice du duel sans fuite du vainqueur, règle de décision, rapport sans nom ni mot interdit, ajout au
journal sans toucher au reste."""
import datetime as dt
import json
import math
import os
import random
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..'))
import etude_pente_service as P  # noqa: E402

GABARIT = os.path.join(ICI, '..', 'journal_ajouts', 'paquet_289.json')


def factices(n_par_periode=6000, beta=-4.0, graine=7, circuits=P.CIRCUITS):
    """Lignes vues du vainqueur, où la vraie loi est p = σ(z (1 + β x))."""
    rnd = random.Random(graine)
    rows = []
    for c in circuits:
        for d in (dt.date(2020, 5, 1), dt.date(2024, 5, 1)):
            for _ in range(n_par_periode):
                z = rnd.gauss(0, 1.1)
                x = rnd.uniform(-0.08, 0.08)
                gagne_a = rnd.random() < P._sg(P.corriger(z, x, beta))
                rows.append({'c': c, 'd': d, 'x': x, 'zb': z if gagne_a else -z})
    return rows


class Apprentissage(unittest.TestCase):
    def test_beta_retrouve(self):
        rows = factices(n_par_periode=30000, circuits=('ATP',))
        Z, X = [r['zb'] for r in rows], [r['x'] for r in rows]
        self.assertAlmostEqual(P.apprendre_beta(Z, X), -4.0, delta=1.2)

    def test_sans_effet_beta_proche_de_zero(self):
        rows = factices(n_par_periode=20000, beta=0.0, circuits=('WTA',))
        b = P.apprendre_beta([r['zb'] for r in rows], [r['x'] for r in rows])
        self.assertLess(abs(b), 1.5)


class IndiceDuDuel(unittest.TestCase):
    def test_symetrique_et_sans_vainqueur(self):
        s = P.Service()
        d = dt.date(2021, 1, 10)
        s.jouer('a', 'b', d, 'ATP', {'w': (80, 60), 'l': (75, 45)})
        d2 = d + dt.timedelta(days=5)
        self.assertAlmostEqual(s.duel('a', 'b', d2, 'ATP'), s.duel('b', 'a', d2, 'ATP'), places=12)

    def test_serveurs_au_dessus_des_retourneurs(self):
        s = P.Service()
        d = dt.date(2021, 1, 10)
        for _ in range(10):
            s.jouer('gros1', 'gros2', d, 'ATP', {'w': (100, 80), 'l': (100, 78)})
            s.jouer('ret1', 'ret2', d, 'ATP', {'w': (100, 50), 'l': (100, 48)})
        d2 = d + dt.timedelta(days=3)
        self.assertGreater(s.duel('gros1', 'gros2', d2, 'ATP'), 0.03)
        self.assertLess(s.duel('ret1', 'ret2', d2, 'ATP'), -0.03)

    def test_oubli_apres_un_an_et_joueur_inconnu_moyen(self):
        s = P.Service()
        d = dt.date(2020, 1, 1)
        s.jouer('a', 'b', d, 'WTA', {'w': (100, 90), 'l': (100, 40)})
        self.assertNotAlmostEqual(s.joueur('a', d + dt.timedelta(days=10), 'WTA')[0], 0.63, places=3)
        self.assertAlmostEqual(s.joueur('a', d + dt.timedelta(days=400), 'WTA')[0], 0.63, places=6)
        self.assertAlmostEqual(s.duel('x', 'y', d, 'CH'), 0.0, places=9)

    def test_sans_feuille_rien_ne_bouge(self):
        s = P.Service()
        s.jouer('a', 'b', dt.date(2020, 1, 1), 'ATP', None)
        self.assertEqual(s._somme('a', dt.date(2020, 1, 2)), (0, 0, 0, 0))


class Regle(unittest.TestCase):
    def test_effet_reel_retenu_sur_chaque_circuit(self):
        res = P.etudier(factices(beta=-8.0))
        for c in P.CIRCUITS:
            self.assertTrue(res[c]['retenu'], res[c]['raisons'])
            self.assertLess(res[c]['beta_appris_2018_2022'], 0)

    def test_sans_effet_non_retenu(self):
        res = P.etudier(factices(beta=0.0, graine=3))
        for c in P.CIRCUITS:
            self.assertFalse(res[c]['retenu'])

    def test_trop_peu_de_matchs(self):
        res = P.etudier(factices(n_par_periode=400, beta=-8.0))
        for c in P.CIRCUITS:
            self.assertIn("moins de 1 000 matchs jugés", res[c]['raisons'])

    def test_sens_contraire_refuse(self):
        rows = [r for r in factices(beta=-8.0, circuits=('ATP',)) if r['d'].year < 2023]
        rows += [r for r in factices(beta=8.0, graine=11, circuits=('ATP',)) if r['d'].year >= 2023]
        v = P.juger_circuit(rows, 'ATP')
        self.assertFalse(v['retenu'])
        self.assertIn('pas le même sens sur les deux périodes', v['raisons'])

    def test_regle_ecrite_dans_l_en_tete_avant_le_code(self):
        with open(P.__file__, encoding='utf-8') as f:
            src = f.read()
        tete = src[:src.index('import collections')]
        for morceau in ('RÈGLE ÉCRITE AVANT TOUT RÉSULTAT', '2018–2022', '2023 → juin 2026', '1 000 matchs', '0,001',
                        'même sens', 'CIRCUIT PAR CIRCUIT'):
            self.assertIn(morceau, tete)
        self.assertEqual((P.MIN_JUGES, P.MARGE, P.COUPURE), (1000, 0.001, dt.date(2023, 1, 1)))

    def test_elo_de_production(self):
        with open(P.__file__, encoding='utf-8') as f:
            code = '\n'.join(l.split('#', 1)[0] for l in f.read().splitlines())
        self.assertIn('E.de_production(racine)', code)
        self.assertNotIn('Elo()', code)


class RapportEtJournal(unittest.TestCase):
    def setUp(self):
        with open(GABARIT, encoding='utf-8') as f:
            self.gabarit = json.load(f)
        self.res = P.etudier(factices(beta=-6.0))
        self.entree = P.entree_journal(self.res, self.gabarit)

    def test_rien_d_interdit_ni_de_nom(self):
        texte = json.dumps({'circuits': self.res, 'entree': self.entree, 'regle': P.REGLE}, ensure_ascii=False).lower()
        for mot in ('march', 'pinnacle', 'cote', 'bookmaker', 'value', 'mise', '"nom'):
            self.assertNotIn(mot, texte)
        with open(GABARIT, encoding='utf-8') as f:
            self.assertNotIn('march', f.read().lower())

    def test_entree_du_journal(self):
        e = self.entree
        self.assertEqual(e['paquet'], 289)
        self.assertEqual(e['statut'], 'etude')
        self.assertIn('RÉSULTAT', e['quoi'])
        for nom in ('ATP', 'WTA', 'Challenger'):
            self.assertIn(nom, e['quoi'])
        self.assertTrue(e['quoi'].endswith('Le % de victoire ne change pas.'))

    def test_ajout_au_journal_sans_toucher_au_reste(self):
        avant = {'regle': 'r', 'changements': [{'date': '2026-11-19', 'statut': 'production', 'paquet': 287,
                                                 'quoi': 'VIDÉO « test » é', 'garde_fou': 'g'}]}
        with tempfile.TemporaryDirectory() as d:
            ch = os.path.join(d, 'journal.json')
            with open(ch, 'w', encoding='utf-8') as f:
                json.dump(avant, f, ensure_ascii=False, indent=1)
            with open(ch, encoding='utf-8') as f:
                texte_avant = f.read()
            P.ajouter_au_journal(ch, self.entree)
            P.ajouter_au_journal(ch, self.entree)            # deux fois : une seule entrée 289
            with open(ch, encoding='utf-8') as f:
                texte = f.read()
            doc = json.loads(texte)
        self.assertEqual([x['paquet'] for x in doc['changements']], [287, 289])
        self.assertEqual(doc['changements'][0], avant['changements'][0])
        self.assertTrue(texte.startswith(texte_avant[:-len('\n  }\n ]\n}')]))
        self.assertFalse(texte.endswith('\n'))


if __name__ == '__main__':
    unittest.main()
