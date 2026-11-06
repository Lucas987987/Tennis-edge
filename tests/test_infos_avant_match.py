# 06/11/2026 (paquet 210) — séries, face-à-face, réussite par rapport aux chances d'avant match.
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
import infos_avant_match as I  # noqa: E402


def match(d, g, p, sets, ab=False):
    return {'date': d, 'circuit': 'ATP', 'surface': 'Hard', 'nom_g': g, 'nom_p': p, 'sets': sets, 'complet': not ab,
            'abandon': ab, 'tournoi': 'Test', 'niveau': 'A'}


class TestInfos(unittest.TestCase):
    def setUp(self):
        d0 = dt.date(2026, 10, 1)
        L = []
        for k in range(12):                              # Alpha bat Beta 12 fois, puis perd une fois
            L.append(match(d0 + dt.timedelta(days=k), 'Alpha One', 'Beta Two', [(6, 3), (6, 4)]))
        L.append(match(d0 + dt.timedelta(days=20), 'Beta Two', 'Alpha One', [(3, 6), (7, 5), (6, 2)]))
        L.append(match(d0 + dt.timedelta(days=21), 'Gamma Three', 'Beta Two', [], ab=True))   # forfait : ignoré
        self.H, self.F, self.k = I.rejouer(L)

    def test_series_et_sets_de_suite(self):
        a = I.fiche_joueur(self.H, self.k('Alpha One'), dt.date(2026, 11, 1))
        b = I.fiche_joueur(self.H, self.k('Beta Two'), dt.date(2026, 11, 1))
        self.assertEqual(a['serie'], {'type': 'defaites', 'n': 1, 'sets': 'perdus', 'sets_n': 2})
        self.assertEqual(b['serie'], {'type': 'victoires', 'n': 1, 'sets': 'gagnes', 'sets_n': 2})

    def test_reussite_et_face_a_face(self):
        a = I.fiche_joueur(self.H, self.k('Alpha One'), dt.date(2026, 11, 1))
        self.assertEqual((a['reussite']['matchs'], a['reussite']['victoires']), (13, 12))
        self.assertGreater(a['reussite']['ecart'], 0)
        f = I.face_a_face(self.F, self.k('Beta Two'), self.k('Alpha One'))
        self.assertEqual((f['rencontres'], f['home'], f['away']), (13, 1, 12))
        self.assertEqual(f['derniers'][0], {'date': '2026-10-21', 'tournoi': 'Test', 'vainqueur': 'home', 'score': '3-6 7-5 6-2'})
        self.assertEqual(len(f['derniers']), 5)


if __name__ == '__main__':
    unittest.main()
