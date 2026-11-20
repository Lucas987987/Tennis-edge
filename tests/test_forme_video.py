"""Forme montrée en vidéo (04/11/2026) : 3 sets / tie-break si la probabilité du match dépasse la moyenne du circuit."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import match_simule as MS  # noqa: E402
import pronostics_du_jour as PD  # noqa: E402

F = {k: None for k in MS.CLES_FEUILLE}


def ligne(sets):
    return (' '.join(f'{a}-{b}' for a, b in sets), dict(F), dict(F), [[0, 0], [0, 0]], sets)


class Regle(unittest.TestCase):
    def setUp(self):
        # favori (joueur 0) : 50 × 6-3 6-4, 30 × 6-3 3-6 7-6, 20 défaites 3-6 4-6
        self.brut = [ligne([(6, 3), (6, 4)])] * 50 + [ligne([(6, 3), (3, 6), (7, 6)])] * 30 + [ligne([(3, 6), (4, 6)])] * 20

    def test_au_dessus_de_la_moyenne_trois_sets_avec_tie_break(self):
        mt = MS.match_type(self.brut, None, 0, (0.25, 0.25))          # P(3 sets) = P(tb) = 30 %
        self.assertEqual(len(mt['sets']), 3)
        self.assertTrue(MS.a_un_tiebreak(mt['sets']))
        self.assertEqual(mt['vainqueur'], 0)

    def test_sous_la_moyenne_deux_sets(self):
        mt = MS.match_type(self.brut, None, 0, (0.366, 0.384))
        self.assertEqual(len(mt['sets']), 2)
        self.assertFalse(MS.a_un_tiebreak(mt['sets']))

    def test_sans_moyennes_ancienne_regle(self):
        self.assertEqual(len(MS.match_type(self.brut, None, 0)['sets']), 2)

    def test_seuils_jamais_sous_la_moyenne_et_part_reelle(self):
        import datetime as dt, gzip, json, tempfile
        with tempfile.TemporaryDirectory() as d:
            dos = os.path.join(d, 'simulateur', 'journal_pronostics', 'apres_match')
            os.makedirs(dos)
            B = {str(i): {'circuit': 'ATP', 'ecarts': {'lignes': {'set_decisif': [0.30 + i / 1000, False],
                                                                  'tie_break': [0.30 + i / 1000, False]}}} for i in range(200)}
            with gzip.open(os.path.join(dos, '2026-11-01.json.gz'), 'wt', encoding='utf-8') as f:
                json.dump(B, f)
            s = PD.seuils_forme(d, aujourdhui=dt.date(2026, 11, 4))
            part = sum(1 for i in range(200) if 0.30 + i / 1000 >= s['ATP'][0]) / 200
            self.assertAlmostEqual(part, MS.MOYENNES_FORME['ATP'][0], delta=0.01)
            self.assertGreaterEqual(s['ATP'][0], MS.MOYENNES_FORME['ATP'][0])
            self.assertEqual(s['WTA'], MS.MOYENNES_FORME['WTA'])            # pas assez de matchs : la moyenne

    def test_moyennes_par_circuit(self):
        self.assertEqual(set(MS.MOYENNES_FORME), {'ATP', 'WTA', 'CH'})


if __name__ == '__main__':
    unittest.main()
