"""Bilan des joueurs en tie-break (05/11/2026) : tie-breaks reconnus, α retrouvé, mesures sans le jour même."""
import datetime as dt
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import etude_tiebreaks_joueurs as TJ  # noqa: E402


class TiebreaksJoueurs(unittest.TestCase):
    def test_tiebreaks(self):
        self.assertEqual(TJ.tiebreaks([(7, 6), (4, 6), (6, 7)]), [1, 0])
        self.assertEqual(TJ.tiebreaks([(6, 4), (7, 5)]), [])

    def test_alpha(self):
        rnd = random.Random(3)
        R = []
        for _ in range(20000):
            q = rnd.uniform(0.2, 0.8)
            R.append((q, int(rnd.random() < TJ._sg(0.5 * TJ._lg(q)))))
        self.assertAlmostEqual(TJ.apprendre_alpha(R), 0.5, delta=0.08)

    def test_jour_meme_exclu(self):
        d0, d1 = dt.date(2019, 1, 1), dt.date(2019, 6, 1)
        ev = [(d0, 'ATP', 'a', 'b', 0.5, 1, True), (d1, 'ATP', 'a', 'b', 0.5, 1, True), (d1, 'ATP', 'a', 'b', 0.5, 0, True)]
        rows, H, _ = TJ.lignes(ev)
        self.assertEqual([r['na'] for r in rows], [0, 1, 1])


if __name__ == '__main__':
    unittest.main()
