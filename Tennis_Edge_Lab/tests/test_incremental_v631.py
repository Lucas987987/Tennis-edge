"""Regression checks for the V6.3.1 cache (no external network)."""
import collections
import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'incremental_v631.py'


def engine_stub():
    engine = types.ModuleType('bookmakers_sets_v5')
    engine.HORIZONS = {'6h': (360, 180)}
    engine.MIN_ODDS, engine.MAX_ODDS = 1.01, 1000.0
    engine.parse_time = lambda s: dt.datetime.fromisoformat(s.replace('Z', '+00:00')) if s else None
    engine.partition_paths = lambda root: [
        (market, p) for market, pattern in (('match', 'hist_book_*'), ('set1', 'hist_set1_*'))
        for p in sorted((root / 'parts').glob(pattern)) if p.suffix == '.jsonl'
    ]
    engine.load_oddspapi_reader = lambda: lambda p: open(p, encoding='utf8')

    def identity(row, start):
        values = [row.get(k) for k in ('uid', 'fixture_id', 'home', 'away', 'book')]
        if not all(isinstance(v, str) and v.strip() for v in values):
            return None
        uid, fixture, home, away, book = values
        return (uid.strip(), fixture.strip(), start, home.strip().casefold(),
                away.strip().casefold(), book.strip().lower())
    engine._identity = identity

    def points(curve, start, counts):
        if not isinstance(curve, list):
            counts['invalid_curves'] += 1
            return []
        out = []
        for row in curve:
            parsed = engine.parse_time(row[0])
            if parsed >= start:
                counts['post_start_quotes_excluded'] += 1
            else:
                out.append((parsed, row[1], None))
        return out
    engine._curve_points = points
    engine._anchors = lambda pts, start: {
        'open': pts[0] if pts else None,
        'close': pts[-1] if pts else None,
        'horizons': {'6h': pts[-1] if pts else None},
    }
    engine._merge_anchor = lambda left, right: {
        'open': min(filter(None, (left['open'], right['open'])), default=None),
        'close': max(filter(None, (left['close'], right['close'])), default=None),
        'horizons': {'6h': max(filter(None, (left['horizons']['6h'],
                                           right['horizons']['6h'])), default=None)},
    }
    return engine


class IncrementalCacheTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / 'scratch-cache'
        self.parts = self.root / 'parts'
        self.parts.mkdir()
        for rel in ('Tennis_Edge_Lab/bookmakers_sets_v5.py',
                    'Tennis_Edge_Lab/source_features.py',
                    'scripts/oddspapi_v5.py'):
            path = self.root / rel
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_text('v1', encoding='utf8')
        stubs = {
            'bookmakers_sets_v5': engine_stub(),
            'candidate_registry_v62': types.ModuleType('candidate_registry_v62'),
            'candidate_selection_v63': types.ModuleType('candidate_selection_v63'),
            'candidate_watch_v61': types.ModuleType('candidate_watch_v61'),
        }
        stubs['candidate_registry_v62'].MARKETS = ('match', 'set1', 'set2')
        stubs['candidate_registry_v62'].REPORT = 'Tennis_Edge_Lab/live/candidate_watch_v62_prospective.json'
        with mock.patch.dict(sys.modules, stubs):
            spec = importlib.util.spec_from_file_location('incremental_v631_synthetic', SCRIPT)
            self.mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.mod)

    def make_row(self, uid='u1', fixture='f1', home='A', away='B', price=2.0):
        return {
            'uid': uid, 'fixture_id': fixture, 'home': home, 'away': away,
            'book': 'Pinnacle', 'commence_time': '2026-10-20T12:00:00+00:00',
            'home_curve': [['2026-10-20T05:00:00+00:00', price]],
            'away_curve': [['2026-10-20T05:00:00+00:00', 1.9]],
        }

    def write(self, path, *items):
        (self.parts / path).write_text(''.join(json.dumps(x) + '\n' for x in items), encoding='utf8')

    def test_cache_reuses_unchanged_sources_and_rebuilds_only_changed_partition(self):
        self.write('hist_book_1.jsonl', self.make_row())
        self.write('hist_set1_1.jsonl', self.make_row())
        one, _, m1 = self.mod.collect_cached(self.root, self.cache)
        self.assertEqual(m1, {'rebuilt': 2})
        two, _, m2 = self.mod.collect_cached(self.root, self.cache)
        self.assertEqual(m2, {'reused': 2})
        self.assertEqual(one, two)
        self.write('hist_book_1.jsonl', self.make_row(price=2.7))
        three, _, m3 = self.mod.collect_cached(self.root, self.cache)
        self.assertEqual(m3, {'rebuilt': 1, 'reused': 1})
        self.assertEqual(three['match', 'u1', 'pinnacle']['curves']['home']['open'][1], 2.7)
        # Cache reflects exact file bytes, not the filesystem mtime.
        _, _, m4 = self.mod.collect_cached(self.root, self.cache)
        self.assertEqual(m4, {'reused': 2})

    def test_global_conflict_detection_not_silently_lost_from_cached_shards(self):
        self.write('hist_book_1.jsonl', self.make_row())
        self.write('hist_book_2.jsonl', self.make_row(home='Different'))
        _, source, _ = self.mod.collect_cached(self.root, self.cache)
        self.assertEqual(source['conflicted_uids'], ['u1'])
        self.assertEqual(source['counters']['match_identity_conflicts'], 1)
        self.assertEqual(source['counters']['partition_records'], 2)
        _, repeated_source, reuse = self.mod.collect_cached(self.root, self.cache)
        self.assertEqual(source, repeated_source)
        self.assertEqual(reuse['reused'], 2)

    def test_parser_change_and_corrupted_cache_fail_closed_to_rebuild(self):
        self.write('hist_book_1.jsonl', self.make_row())
        _, _, first = self.mod.collect_cached(self.root, self.cache)
        self.assertEqual(first['rebuilt'], 1)
        # Simulate a corrupted cache: no output trusted from a broken ZIP/GZIP.
        for file in self.cache.iterdir():
            file.write_bytes(b'invalid data')
        _, _, rebuilt = self.mod.collect_cached(self.root, self.cache)
        self.assertEqual(rebuilt['rebuilt'], 1)
        (self.root/'Tennis_Edge_Lab/bookmakers_sets_v5.py').write_text('v2')
        _, _, rebuilt_parser = self.mod.collect_cached(self.root, self.cache)
        self.assertEqual(rebuilt_parser['rebuilt'], 1)


if __name__ == '__main__':
    unittest.main()
