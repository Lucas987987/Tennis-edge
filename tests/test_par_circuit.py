# -*- coding: utf-8 -*-
"""13/11/2026 (paquet 255) — ce qui restait commun aux circuits, jugé circuit par circuit."""
import json
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(ICI, '..', 'simulateur')
sys.path.insert(0, SIM)
sys.path.insert(0, ICI)
import etude_par_circuit as PC  # noqa: E402
import facteurs as F  # noqa: E402
import test_facteurs_cumules as T  # noqa: E402


class Elo(unittest.TestCase):
    def test_reglage_de_pronostic(self):
        r = (None, 'ATP', 200.0, 100.0, 50, 5, 1.0)
        self.assertGreater(PC.z_elo(r, 0.0, 0.0), PC.z_elo(r, 0.6, 0.0))           # surface moins favorable
        self.assertGreater(PC.z_elo(r, 0.3, 0.0), PC.z_elo(r, 0.3, 15.0))          # prudence : plus près de 50 %
        self.assertAlmostEqual(PC.z_elo((None, 'ATP', 200.0, None, 50, 5, 1.0), 0.6, 0.0), 200 / 400 * 2.302585, places=4)


class Rapport(unittest.TestCase):
    def test_rapport(self):
        r = json.load(open(os.path.join(SIM, 'rapport_par_circuit.json'), encoding='utf-8'))
        self.assertEqual(r['statut'], 'etude')
        self.assertFalse(r['A_elo_au_moment_du_pronostic']['CH']['retenu'])         # non concluant par règle
        for c in ('ATP', 'WTA'):
            b = r['B_poids_du_melange_archive'][c]
            self.assertEqual(b['retenu'], b['gain_jugement'] >= 0.001 and b['gain_apprentissage'] > 0
                             and b['matchs']['2025 → janvier 2026'] >= 1000)
        t = json.dumps(r, ensure_ascii=False).lower()
        for mot in ('marché', 'pinnacle', 'cote', 'value'):
            self.assertNotIn(mot, t)


class FantomeComplet(unittest.TestCase):
    def test_par_circuit(self):
        rnd = random.Random(7)
        L = [T.ligne(rnd, i) for i in range(700)]
        for i, x in enumerate(L):
            x['circuit'] = 'ATP' if i % 2 else 'WTA'
        appr, juge = L[:560], L[560:]
        m = F.apprendre_complet(appr, T.FEATS)
        out = F.complet_par_circuit(appr + appr[:200], juge * 5, [], m)
        self.assertIsNone(out['CH']['paires'])
        P = out['ATP']['paires']
        self.assertEqual(len(P['vainqueur']), out['ATP']['matchs'][1])
        self.assertTrue(P['points'])

    def test_branchement(self):
        s = open(os.path.join(SIM, 'facteurs.py'), encoding='utf-8').read()
        self.assertIn("f'facteur:modele_complet:{circ}'", s)
        self.assertIn("'fantome': True", s)


if __name__ == '__main__':
    unittest.main()
