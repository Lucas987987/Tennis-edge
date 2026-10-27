import collections
import datetime as dt
import gzip
import json
import pathlib
import sys
import tempfile
import unittest

LAB = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))
import bookmakers_sets_v5 as v5
import courbes_cotes as cc
import explorer_build as xb
import explorer_matchs as xm

T0 = dt.datetime(2026, 10, 1, 10, tzinfo=dt.timezone.utc)
T1 = dt.datetime(2026, 10, 1, 11, tzinfo=dt.timezone.utc)
START = dt.datetime(2026, 10, 1, 12, tzinfo=dt.timezone.utc)


class DedoublonnageTests(unittest.TestCase):
    def test_strictement_identique_supprime_sans_melanger_les_instants(self):
        points = [(T0, 2.0, 100), (T0, 2.0, 200), (T1, 2.0, 100),
                  (T0, 2.1, 100), (T0, 1.9, 100)]
        counters = collections.Counter()
        out = cc.dedupliquer(points, counters)
        self.assertEqual(out, [(T0, 2.0, 100), (T1, 2.0, 100), (T0, 2.1, 100), (T0, 1.9, 100)])
        self.assertEqual(counters['duplicate_quote_points_removed'], 1)
        self.assertEqual(points[0], (T0, 2.0, 100))  # entrée non mutée

    def test_curve_points_dedoublonne_apres_tri_stable(self):
        counters = collections.Counter()
        curve = [[T1.isoformat(), 2.0], [T0.isoformat(), 1.9], [T0.isoformat(), 1.9],
                 [T0.isoformat(), 2.2], [START.isoformat(), 1.5]]
        out = v5._curve_points(curve, START, counters)
        self.assertEqual([(p[0], p[1]) for p in out], [(T0, 1.9), (T0, 2.2), (T1, 2.0)])
        self.assertEqual(counters['duplicate_quote_points_removed'], 1)
        self.assertEqual(counters['post_start_quotes_excluded'], 1)

    def test_pinnacle_index_et_compteur_explorateur(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'clv_history.jsonl'
            row = {'uid': 'u', 'commence_time': START.isoformat(), 'home': 'Ann Alpha', 'away': 'Bea Beta',
                   'home_curve': [[T0.isoformat(), 2.0], [T0.isoformat(), 2.0], [T1.isoformat(), 2.0]],
                   'away_curve': [[T0.isoformat(), 1.8], [T1.isoformat(), 1.9]]}
            path.write_text(json.dumps(row)+'\n', encoding='utf-8')
            index = xb.PinnacleIndex(path)
            item, side = index.find('Ann Alpha', START, 'Bea Beta')
            self.assertEqual(len(item['curves']['home']), 2)
            feats = xb.pinnacle_features(item, side, T1)
            self.assertEqual(feats['pin_points_n'], 2)

    def test_series_fusionnees_ne_repetent_pas_les_partitions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root/'parts').mkdir()
            row = {'uid': '2026-10-01_ann_alpha_bea_beta', 'book': 'pinnacle',
                   'commence_time': START.isoformat(), 'home': 'Ann Alpha', 'away': 'Bea Beta',
                   'tournament': 'WTA Test',
                   'home_curve': [[T0.isoformat(), 2.0], [T1.isoformat(), 1.9]],
                   'away_curve': [[T0.isoformat(), 1.8], [T1.isoformat(), 1.9]]}
            (root/'parts/hist_book_test.jsonl').write_text((json.dumps(row)+'\n')*2, encoding='utf-8')
            counters, series = collections.Counter(), {}
            xm.collect(root, counters, series=series)
            home = series[row['uid']]['home']
            self.assertEqual(home, [(T0, 2.0), (T1, 1.9)])
            self.assertGreaterEqual(counters['duplicate_quote_points_removed'], 2)


if __name__ == '__main__':
    unittest.main()
