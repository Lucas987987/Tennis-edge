# -*- coding: utf-8 -*-
"""Tests de simulateur/etude_peu_documentes.py (paquet 462), sur données factices : aucune archive nécessaire."""
import json
import math
import os
import random
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ICI))
import etude_peu_documentes as PD  # noqa: E402

CFG = {'elo': 0.78, 'simulation': 0.24, 'pente_doc': 1.11, 'fmd': {'pente': 0.775, 'de': 500, 'a': 1500}}
CFGS = {c: dict(CFG) for c in PD.CIRCUITS}
NU = {'elo': 0.78, 'simulation': 0.24, 'pente_doc': None, 'fmd': None}
DOCS = {'moins_de_500': (120, 4000), '500_a_1500': (900, 5000), '1500_a_3000': (2000, 6000), '3000_et_plus': (5000, 9000)}


def _sg(z):
    return 1 / (1 + math.exp(-z))


def lignes(bruit_peu_documente, n=1300, graine=7, circuits=PD.CIRCUITS, cfg=CFG):
    """Lignes factices au format du rejeu. La réalité suit le mélange en place calculé avec la VRAIE simulation ; dans
    les deux tranches sous 1 500 points, la simulation observée est la vraie plus un bruit (0 : rien à corriger)."""
    rnd = random.Random(graine)
    rows = []
    for c in circuits:
        for jour in ('2025-03-10', '2025-11-17'):
            for nom, (peu, beaucoup) in DOCS.items():
                for _ in range(n):
                    x = rnd.gauss(0, 1.1)
                    ze, zs_vraie = x + rnd.gauss(0, 0.3), 0.9 * x + rnd.gauss(0, 0.5)
                    zs = zs_vraie + (rnd.gauss(0, bruit_peu_documente) if nom in PD.CONCERNEES else 0.0)
                    d_home, d_away = (peu, beaucoup) if rnd.random() < 0.5 else (beaucoup, peu)
                    vraie = PD.z_melange([c, jour, ze, zs_vraie, d_home, d_away], cfg)
                    if rnd.random() < _sg(vraie):
                        rows.append([c, jour, ze, zs, d_home, d_away])
                    else:
                        rows.append([c, jour, -ze, -zs, d_away, d_home])
    return rows


class TestMesures(unittest.TestCase):
    def test_tranches(self):
        t = lambda a, b: PD.tranche_de(['CH', '2025-01-01', 0.0, 0.0, a, b])  # noqa: E731
        self.assertEqual(t(0, 9000), 'moins_de_500')
        self.assertEqual(t(9000, 499), 'moins_de_500')
        self.assertEqual(t(500, 9000), '500_a_1500')
        self.assertEqual(t(1500, 1500), '1500_a_3000')
        self.assertEqual(t(3000, 9000), '3000_et_plus')

    def test_melange_sans_signal(self):
        r = ['CH', '2025-01-01', 1.0, 0.5, 5000, 6000]
        self.assertAlmostEqual(PD.z_melange(r, CFG), 0.78 + 0.12)
        self.assertAlmostEqual(PD.z_melange(r, CFG, b=0.0), 0.78)
        self.assertAlmostEqual(PD.z_melange(r, CFG, k=2.0), 1.8)
        self.assertAlmostEqual(PD.z_melange(r, CFG, a=1.0, b=1.0), 1.5)

    def test_signal_documentation_faible(self):
        r = ['CH', '2025-01-01', 1.0, 0.5, 5000, 100]            # favori de l'Elo (vainqueur) le PLUS documenté
        self.assertAlmostEqual(PD.z_melange(r, CFG), 1.11 * 0.9)
        self.assertAlmostEqual(PD.z_melange(r, NU), 0.9)

    def test_signal_favori_moins_documente(self):
        r = ['CH', '2025-01-01', 1.0, 0.5, 900, 6000]            # favori de l'Elo = vainqueur, 900 points
        self.assertAlmostEqual(PD.z_melange(r, CFG), 0.9 + 0.78 * (0.775 - 1) * 1.0)
        r2 = ['CH', '2025-01-01', -1.0, -0.5, 6000, 900]         # même match, le favori a perdu
        self.assertAlmostEqual(PD.z_melange(r2, CFG), -PD.z_melange(r, CFG))
        r3 = ['CH', '2025-01-01', 1.0, 0.5, 6000, 900]           # favori le plus documenté : rien
        self.assertAlmostEqual(PD.z_melange(r3, CFG), 0.9)
        r4 = ['CH', '2025-01-01', 1.0, 0.5, 300, 6000]           # sous 500 : seulement « documentation faible »
        self.assertAlmostEqual(PD.z_melange(r4, CFG), 1.11 * 0.9)

    def test_moyenne(self):
        self.assertEqual(PD.moyenne([]), {'matchs': 0})
        m = PD.moyenne([0.1, 0.3])
        self.assertEqual(m['matchs'], 2)
        self.assertAlmostEqual(m['gain'], 0.2)
        self.assertAlmostEqual(m['erreur_type'], 0.1)

    def test_nombres_a_la_francaise(self):
        self.assertEqual(PD.fr(9e-05), '0,00009')
        self.assertEqual(PD.fr(-0.00019), '-0,00019')
        self.assertEqual(PD.fr(0.0), '0')
        self.assertEqual(PD.fr(0.2378), '0,2378')
        self.assertEqual(PD.fr(1127), '1127')
        self.assertEqual(PD.fr(None), 'None')

    def test_gain_nul_sans_changement(self):
        R = lignes(0.0, n=50, circuits=('CH',))
        self.assertEqual(PD.gain(R, CFG, b=CFG['simulation'])['gain'], 0.0)
        self.assertEqual(PD.gain(R, CFG, k=1.0)['gain'], 0.0)

    def test_deux_poids_retrouves(self):
        R = [r for r in lignes(0.0, n=4000, graine=11, circuits=('CH',), cfg=NU) if PD.tranche_de(r) == '3000_et_plus']
        a, b = PD.apprendre_deux_poids(R, NU)
        self.assertAlmostEqual(a, NU['elo'], delta=0.12)
        self.assertAlmostEqual(b, NU['simulation'], delta=0.12)


class TestRegle(unittest.TestCase):
    def test_simulation_bruitee_retenue(self):
        jug = PD.juger(lignes(3.0), CFGS)
        for c in PD.CIRCUITS:
            for nom in PD.CONCERNEES:
                t = jug[c]['tranches'][nom]
                self.assertEqual(t['verdict'], 'retenu', (c, nom, t.get('raisons')))
                self.assertLess(t['poids_appris'], CFG['simulation'])
                self.assertEqual(t['sens'], 'moins de simulation')
                self.assertGreaterEqual(t['gain_jugement']['gain'], PD.MARGE)
                self.assertGreaterEqual(t['gain_jugement']['matchs'], PD.MIN_JUGES)
                self.assertTrue(t['passe_deux_erreurs_types'])
            self.assertEqual(jug[c]['tranches_retenues'], list(PD.CONCERNEES))
            self.assertEqual(jug[c]['tranches']['3000_et_plus']['verdict'], 'témoin')
            self.assertEqual(jug[c]['ensemble_des_matchs_concernes_jugement']['matchs'], 2 * 1300)

    def test_rien_a_corriger_non_retenu(self):
        # Sans effet, la règle seule peut retenir une tranche par hasard (ici 1 sur 6, à 1,2 erreur type) : c'est
        # pourquoi « passe_deux_erreurs_types » est publié à côté du verdict. Jamais les deux à la fois.
        jug = PD.juger(lignes(0.0), CFGS)
        T = [jug[c]['tranches'][nom] for c in PD.CIRCUITS for nom in PD.CONCERNEES]
        self.assertLessEqual(sum(t['verdict'] == 'retenu' for t in T), 1)
        for t in T:
            self.assertIn(t['verdict'], ('retenu', 'non retenu'))
            self.assertFalse(t['passe_deux_erreurs_types'])
            self.assertEqual(bool(t['raisons']), t['verdict'] == 'non retenu')

    def test_moins_de_1000_juges_aucune_decision(self):
        jug = PD.juger(lignes(3.0, n=400, circuits=('CH',)), CFGS)
        for nom in PD.CONCERNEES:
            t = jug['CH']['tranches'][nom]
            self.assertEqual(t['verdict'], 'aucune décision')
            self.assertIn('gain_jugement', t)                      # chiffres publiés quand même
        self.assertEqual(jug['ATP']['matchs'], 0)
        self.assertEqual(jug['ATP']['tranches']['moins_de_500']['verdict'], 'aucune décision')

    def test_trop_peu_pour_apprendre(self):
        jug = PD.juger(lignes(3.0, n=100, circuits=('CH',)), CFGS)
        t = jug['CH']['tranches']['500_a_1500']
        self.assertEqual(t['verdict'], 'aucune décision')
        self.assertNotIn('poids_appris', t)
        self.assertEqual(t['jugement']['matchs'], 100)

    def test_meme_resultat_deux_fois(self):
        a = PD.juger(lignes(1.5, n=350, circuits=('CH',)), CFGS)
        b = PD.juger(lignes(1.5, n=350, circuits=('CH',)), CFGS)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


class TestSorties(unittest.TestCase):
    def setUp(self):
        self.jug = PD.juger(lignes(3.0, n=1100, circuits=('CH',)), CFGS)
        with open(PD.GABARIT_JOURNAL, encoding='utf-8') as f:
            self.gabarit = json.load(f)

    def test_entree_journal(self):
        e = PD.entree_journal({'jugement': self.jug}, self.gabarit)
        self.assertEqual((e['paquet'], e['statut']), (462, 'etude'))
        self.assertIn('RÉSULTAT', e['quoi'])
        self.assertIn('Challenger', e['quoi'])
        self.assertTrue(e['quoi'].endswith('Le % de victoire ne change pas.'))
        for texte in (e['quoi'], e['garde_fou'], PD.REGLE, PD.LIMITES, json.dumps(self.jug, ensure_ascii=False)):
            self.assertNotIn('marché', texte.lower())
            self.assertNotIn('cote', texte.lower().replace('côté', ''))

    def test_gabarit_meme_forme_que_les_autres(self):
        self.assertEqual(sorted(self.gabarit), ['date', 'garde_fou', 'paquet', 'quoi_debut', 'statut'])

    def test_affichage_public_sans_erreur(self):
        sortie = []
        PD.afficher(self.jug, journal=sortie.append)
        self.assertTrue(any('Challenger' in l for l in sortie))
        self.assertTrue(any('ensemble des matchs concernés' in l for l in sortie))

    def test_journal_depuis_rapport(self):
        e = PD.entree_journal({'jugement': self.jug}, self.gabarit)
        with tempfile.TemporaryDirectory() as d:
            journal, rapport = os.path.join(d, 'journal.json'), os.path.join(d, 'rapport.json')
            with open(journal, 'w', encoding='utf-8') as f:
                json.dump({'regle': 'r', 'changements': [{'paquet': 461, 'quoi': 'avant'}]}, f)
            with open(rapport, 'w', encoding='utf-8') as f:
                json.dump({'entree_journal': e}, f, ensure_ascii=False)
            ancien, PD.JOURNAL = PD.JOURNAL, journal
            try:
                self.assertEqual(PD.main(['x', '--journal-depuis-rapport', rapport]), 0)
                self.assertEqual(PD.main(['x', '--journal-depuis-rapport', rapport]), 0)      # deux fois : une seule entrée
            finally:
                PD.JOURNAL = ancien
            with open(journal, encoding='utf-8') as f:
                L = json.load(f)['changements']
            self.assertEqual([x['paquet'] for x in L], [461, 462])

    def test_en_place_lit_les_fichiers_du_depot(self):
        cfgs = PD.en_place(os.path.dirname(os.path.dirname(ICI)))
        for c in PD.CIRCUITS:
            self.assertGreater(cfgs[c]['elo'], 0)
            self.assertGreater(cfgs[c]['simulation'], 0)

    def test_en_place_sans_fichier(self):
        with tempfile.TemporaryDirectory() as d:
            cfgs = PD.en_place(d)
        self.assertEqual(cfgs['CH']['simulation'], PD.POIDS_REPLI['simulation'])
        self.assertIsNone(cfgs['CH']['pente_doc'])
        self.assertIsNone(cfgs['CH']['fmd'])


if __name__ == '__main__':
    unittest.main()
