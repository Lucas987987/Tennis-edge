# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 251) — effets propres à chaque joueur (étude) et duel des coups dans le tiroir (descriptif)."""
import json
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
SIM = os.path.join(RACINE, 'simulateur')
sys.path.insert(0, SIM)
import coups_joueurs as CJ  # noqa: E402
import etude_profils_individuels as PI  # noqa: E402
import vitrine as V  # noqa: E402


class Effets(unittest.TestCase):
    def test_effet_propre(self):
        R = PI.Residus()
        for _ in range(30):
            R.ajouter('a', 'tous', -0.3)
            R.ajouter('a', 'grand_serveur', -0.3)
        for _ in range(30):
            R.ajouter('a', 'tous', 0.1)
        self.assertLess(R.effet('a', 'grand_serveur'), 0)          # pire contre ce style que contre tous
        self.assertIsNone(R.effet('a', 'indetermine'))
        self.assertEqual(R.effet('b', 'contreur'), 0.0)            # inconnu : rien

    def test_rapport(self):
        r = json.load(open(os.path.join(SIM, 'rapport_profils_individuels.json'), encoding='utf-8'))
        self.assertEqual(r['statut'], 'etude')
        self.assertEqual(r['retenus'], [])
        for c in ('ATP', 'WTA'):
            self.assertGreaterEqual(r['circuits'][c]['matchs_concernes']['2023 → juin 2026'], 1000)


class DuelTiroir(unittest.TestCase):
    def comptes(self, **k):
        c = {x: 100 for x in CJ.CATEGORIES + CJ.DUEL + ('points_gagnes', 'points_joues', 'montees', 'montees_gagnees')}
        c.update(points_joues=1000, montees=100, montees_gagnees=70, adv_montees=80, adv_montees_gagnees=50)
        c.update(k)
        return c

    def ligne(self):
        return {'home': 'Alpha Un', 'away': 'Beta Deux',
                'feuille_prevue': [{'aces': 4, 'doubles_fautes': 2}, {'aces': 6, 'doubles_fautes': 2}],
                'feuille_plus': [{'points_gagnes': [78, 55, 100]}, {'points_gagnes': [70, 50, 92]}]}

    def test_taux(self):
        t = V.taux_duel(self.comptes())
        self.assertAlmostEqual(t['filet_freq'], 0.1)
        self.assertAlmostEqual(t['filet_reussite'], 0.7)
        self.assertAlmostEqual(t['filet_concede'], 0.625)
        self.assertIsNone(V.taux_duel({'montees': 3})['filet_freq'])

    def test_duel_seulement_si_les_deux_sont_releves(self):
        doc = {'joueurs': {'alpha': {'matchs': 12, 'circuit': 'm', 'comptes': self.comptes()},
                           'beta': {'matchs': 12, 'circuit': 'm', 'comptes': self.comptes(montees=50)}}}
        cle = lambda n: n.split()[0].lower()  # noqa: E731
        pm = V.points_marques(self.ligne(), doc, cle)
        self.assertIn('duel', pm)
        self.assertIn('circuit', pm['duel'])
        del doc['joueurs']['beta']
        self.assertNotIn('duel', V.points_marques(self.ligne(), doc, cle))

    def test_page(self):
        s = open(os.path.join(RACINE, 'algo', 'index.html'), encoding='utf-8').read()
        self.assertIn("'Duel des coups'", s)
        self.assertIn("ni pour l'ensemble des joueurs, ni joueur par joueur", s)


if __name__ == '__main__':
    unittest.main()
