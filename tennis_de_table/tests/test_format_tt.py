"""Paquet 502 : format des matchs (3 ou 4 manches gagnantes) — familles, repli, règle de l'étude, branchement prudent
dans les pronostics (seulement si l'étude est retenue ; la Pologne toujours en 3)."""
import datetime as dt
import json
import os
import random
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..'))
import format_tt as FT  # noqa: E402
import etude_format_tt as EF  # noqa: E402
import pronostics_tt as PT  # noqa: E402


def monde(seed=1, tours=True, derive=False):
    """Champions : 4 manches gagnantes à partir des quarts ; Feeder : toujours 3 ; Olympiques : toujours 4."""
    rng = random.Random(seed)
    X = []
    for k in range(9000):
        jour = (dt.date(2023, 1, 1) + dt.timedelta(days=k // 6)).isoformat()      # jugement à partir de k ≈ 6 000
        fam = rng.choice(('WTT Champions Macao, MS', 'Feeder Havirov, MS', 'Feeder Havirov, MD', 'Olympic Games, WS'))
        tour = rng.choice(('Round of 32', 'Round of 16', 'Quarterfinal', 'Semifinal', 'Final'))
        if 'Champions' in fam:
            longs = ('Final',) if derive and jour >= '2025-10-01' else ('Quarterfinal', 'Semifinal', 'Final')
            n = 4 if tour in longs else 3
        else:
            n = 4 if 'Olympic' in fam else 3
        X.append((jour, fam, tour if tours else None, n))
    return sorted(X)


class T(unittest.TestCase):
    def test_familles_et_epreuves(self):
        self.assertEqual(FT.famille('WTT Champions Frankfurt, Singles'), 'champions')
        self.assertEqual(FT.famille('WTT Star Contender Chennai 2025, MS, Qualifying'), 'star_contender_qualif')
        self.assertEqual(FT.famille('Europe Smash Sweden, WS'), 'smash')
        self.assertEqual(FT.famille('Feeder Dusseldorf II, MS'), 'feeder')
        self.assertEqual(FT.famille('TT Elite Series'), 'autre')
        for t in ('Feeder Havirov, MD', 'European Championship (XD)', 'Feeder Dusseldorf, Doubles', 'China Smash, WD'):
            self.assertEqual(FT.epreuve(t), 'double', t)
        for t in ('Feeder Havirov, MS', 'WTT Champions Macao, Women Singles', 'European Championship (MS) '):
            self.assertEqual(FT.epreuve(t), 'simple', t)

    def test_repli_sur_les_cases_larges(self):
        T = FT.apprendre([('WTT Champions X, MS', 'Final', 4)] * 12 + [('WTT Champions X, MS', 'Round of 16', 3)] * 12)
        self.assertEqual(FT.predire(T, 'WTT Champions Y, MS', 'Final'), 4)
        self.assertEqual(FT.predire(T, 'WTT Champions Y, MS', 'Round of 16'), 3)
        self.assertAlmostEqual(FT.proba_4(T, 'WTT Champions Y, MS', 'Group 3'), 0.5)    # case vide → famille
        self.assertEqual(FT.proba_4(T, 'Feeder Z, MD', None, a_priori=0.07), 0.07)        # rien → a priori

    def test_etude_retenue_avec_le_tour(self):
        rep = EF.etudier(monde(), lambda x: None)
        self.assertTrue(rep['retenu'])
        self.assertGreater(rep['jugement_candidat']['format_juste_pct'], 99)
        self.assertEqual(FT.predire(rep['table_production'], 'WTT Champions Doha, MS', 'Semifinal'), 4)
        self.assertEqual(FT.predire(rep['table_production'], 'WTT Champions Doha, MS', 'Round of 32'), 3)
        self.assertEqual(FT.predire(rep['table_production'], 'Feeder Varazdin, MS', 'Final'), 3)

    def test_etude_sans_tour_moins_bonne_que_le_temoin_non_retenue(self):
        # sans le tour, et avec des tours finaux qui raccourcissent au jugement : Champions prédit « 4 » partout, format
        # juste plus bas que le témoin → non retenu, même si la log loss baisse
        fam_seules = [x for x in monde(tours=False, derive=True) if 'Olympic' not in x[1]]
        rep = EF.etudier(fam_seules, lambda x: None)
        self.assertFalse(rep['retenu'])
        self.assertIsNone(rep['table_production'])
        self.assertEqual(EF.etudier(monde()[:500], lambda x: None)['verdict'], 'donnees_insuffisantes')

    def test_branchement_seulement_si_retenu(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'r.json')
        rep = EF.etudier(monde(), lambda x: None)
        for retenu in (True, False):
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(dict(rep, retenu=retenu), f)
            FT._TABLE.clear()
            self.assertEqual(FT.table_retenue(p) is not None, retenu)
        FT._TABLE.clear()
        FT._TABLE[FT.RAPPORT] = rep['table_production']
        try:
            self.assertEqual(PT.format_du_match({'ligue': 'International', 'tournoi': 'WTT Champions X, MS', 'tour': 'Final'}),
                             (4, 'habituel'))
            self.assertEqual(PT.format_du_match({'ligue': 'Poland', 'tournoi': 'TT Elite Series'}), (3, 'ligue'))
            self.assertEqual(PT.format_du_match({'ligue': 'International', 'format': 4}), (4, 'source'))
            FT._TABLE[FT.RAPPORT] = None
            self.assertEqual(PT.format_du_match({'ligue': 'International', 'tournoi': 'WTT Champions X, MS', 'tour': 'Final'}),
                             (3, 'suppose'))
        finally:
            FT._TABLE.clear()


if __name__ == '__main__':
    unittest.main()
