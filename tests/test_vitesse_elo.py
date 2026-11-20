# -*- coding: utf-8 -*-
"""11/11/2026 (paquet 229) — vitesse de l'Elo en WTA et départ des petits niveaux : l'étude, et la vitesse par joueur."""
import datetime as dt
import json
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import elo as E  # noqa: E402
import etude_vitesse_elo as EV  # noqa: E402


def match(g, p, jour, circuit='WTA', niveau='P', femme=True, abandon=False):
    return {'nom_g': g, 'nom_p': p, 'circuit': circuit, 'surface': 'Hard', 'date': jour, 'bo': 3,
            'gagnant': ('wta:' if femme else 'atp:') + g, 'sets': [(6, 3), (6, 4)], 'complet': True,
            'abandon': abandon, 'niveau': niveau}


class VitesseParJoueur(unittest.TestCase):
    def test_sans_reglage_rien_ne_change(self):
        a, b = E.Elo(poids_surface=0.3, welo='norme', incertitude=5.0), E.Elo(poids_surface=0.3, welo='norme', incertitude=5.0)
        b.regler_vitesse('x', 1.0)
        for g, p in (('x', 'y'), ('y', 'z'), ('x', 'z'), ('z', 'x')):
            a.maj(g, p, 'Hard', False, 0.6)
            b.maj(g, p, 'Hard', False, 0.6)
        self.assertEqual(a.g, b.g)
        self.assertEqual(a.s, b.s)
        self.assertEqual(b.vit, {})

    def test_un_joueur_regle_bouge_plus_vite_lui_seul(self):
        a, b = E.Elo(), E.Elo()
        b.regler_vitesse('x', 2.0)
        a.maj('x', 'y', 'Hard')
        b.maj('x', 'y', 'Hard')
        self.assertAlmostEqual(b.g['x'] - 1500, 2 * (a.g['x'] - 1500))
        self.assertAlmostEqual(b.g['y'], a.g['y'])                      # l'adversaire garde sa vitesse
        self.assertAlmostEqual(b.s[('x', 'Hard')] - 1500, 2 * (a.s[('x', 'Hard')] - 1500))
        b.regler_vitesse('x', 1.0)
        self.assertNotIn('x', b.vit)

    def test_les_options_de_l_elo_ne_changent_pas(self):
        self.assertEqual(sorted(E.Elo().options()), ['incertitude', 'poids_surface', 'welo'])


class Etude(unittest.TestCase):
    def test_une_joueuse_se_reconnait_a_son_identifiant(self):
        self.assertTrue(EV.femme({'gagnant': 'wta:123'}))
        self.assertFalse(EV.femme({'gagnant': 'atp:123'}))
        self.assertFalse(EV.femme({}))

    def test_rejeu_competitions_par_equipes_hors_jugement_et_vitesse_des_seules_joueuses(self):
        j = dt.date(2019, 3, 4)
        M = [match('Ana A', 'Bea B', j), match('Ana A', 'Cleo C', j, niveau='D'), match('Bea B', 'Cleo C', j, abandon=True),
             match('Dan D', 'Eli E', j, circuit='ATP', niveau='A', femme=False), match('Ana A', 'Bea B', j)]
        base = EV.rejouer(M, E.cle, RACINE)
        vite = EV.rejouer(M, E.cle, RACINE, vitesse_f=1.4)
        self.assertEqual([r[0] for r in base], ['WTA', 'ATP', 'WTA'])       # ni le niveau « D » ni l'abandon ne sont jugés
        self.assertEqual(base[1][3], vite[1][3])                            # le match des hommes ne bouge pas
        self.assertGreater(vite[2][3], base[2][3])                          # la gagnante monte plus vite
        self.assertIsNone(base[0][4])
        self.assertIsNotNone(EV.rejouer(M, E.cle, RACINE, rapide=True)[2][4])

    def test_le_depart_ne_touche_que_les_petits_niveaux(self):
        j = dt.date(2019, 3, 4)
        M = [match('Dan D', 'Eli E', j, circuit='CH', niveau='C', femme=False), match('Fab F', 'Gus G', j, circuit='ATP', niveau='A', femme=False),
             match('Dan D', 'Fab F', j, circuit='ATP', niveau='A', femme=False)]
        bas, haut = EV.rejouer(M, E.cle, RACINE, depart=1200.0), EV.rejouer(M, E.cle, RACINE, depart=1350.0)
        self.assertEqual(bas[1][3], haut[1][3])                             # deux joueurs du grand circuit : inchangé
        self.assertGreater(haut[2][3], bas[2][3])                           # le joueur venu d'en bas part plus haut

    def test_beta_de_l_elo_rapide(self):
        rnd, P = random.Random(3), []
        for _ in range(20000):
            z, zr = rnd.gauss(0, 1), None
            zr = z + rnd.gauss(0, 0.5)
            vrai = z + 0.4 * (zr - z)
            gagne = rnd.random() < EV._sg(vrai)
            P.append((z, zr) if gagne else (-z, -zr))
        self.assertAlmostEqual(EV.beta_rapide(P), 0.4, delta=0.08)

    def test_compare_et_regle(self):
        base = [0.5] * 600 + [-0.5] * 400
        mieux = [0.7] * 600 + [-0.3] * 400
        c = EV.compare(base, mieux)
        self.assertGreater(c['gain'], 0)
        self.assertLess(c['brier'], c['brier_base'])
        self.assertEqual(EV.compare([], []), {'matchs': 0})
        ok = {'matchs': 5000, 'gain': 0.002, 'erreurs_types': 3.0}
        self.assertEqual(EV.passe({'gain': 0.002}, ok), (True, []))
        self.assertFalse(EV.passe({'gain': 0.002}, dict(ok, gain=0.0009))[0])
        self.assertFalse(EV.passe({'gain': 0.002}, dict(ok, erreurs_types=1.0))[0])
        self.assertFalse(EV.passe({'gain': 0.002}, dict(ok, matchs=800))[0])
        self.assertFalse(EV.passe({'gain': -0.001}, ok)[0])

    def test_l_etude_prend_l_elo_de_production(self):
        with open(os.path.join(RACINE, 'simulateur', 'etude_vitesse_elo.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn('E.de_production(racine)', src)
        self.assertNotRegex(src, r'\bElo\(\s*\)')
        self.assertIn('AVANT DE REGARDER', src)


class Rapport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RACINE, 'simulateur', 'rapport_vitesse_elo.json'), encoding='utf-8') as f:
            cls.R = json.load(f)

    def test_rapport_public_avec_brier(self):
        txt = json.dumps(self.R, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'clôture', 'cote'):
            self.assertNotIn(mot, txt)
        self.assertIn('brier', self.R['vitesse_wta']['2023 → juin 2026'])

    def test_rien_n_est_en_production_qui_n_ait_passe(self):
        """Les deux étapes sont rejetées : la production garde sa vitesse et son départ à 1200."""
        self.assertFalse(self.R['vitesse_wta']['retenue'])
        self.assertFalse(self.R['depart_petits_niveaux']['retenu'])
        with open(os.path.join(RACINE, 'simulateur', 'backtest_pronostic.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn('DEPART_BAS = 1200.0', src)
        self.assertNotIn('regler_vitesse', src)

    def test_la_forme_a_ete_choisie_sur_la_periode_d_apprentissage(self):
        c = self.R['vitesse_wta']['candidats_2018_2022']
        meilleur = max(c, key=lambda n: c[n]['2018–2022']['gain'])
        self.assertEqual(self.R['vitesse_wta']['forme_choisie'], meilleur)


if __name__ == '__main__':
    unittest.main()
