"""V6.6 : CLV Pinnacle sans marge, commission Betfair, drapeaux des books,
plafond d'âge des cotes, stabilité 16 ans, propositions jamais gelées
automatiquement et gels strictement prospectifs."""
import collections
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

LAB = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))
import books  # noqa: E402
import bookmakers_sets_v5 as v5  # noqa: E402
import clv_stats  # noqa: E402
import history_stability as hs  # noqa: E402
import selection_v66 as sel  # noqa: E402


class BooksAndClvTests(unittest.TestCase):
    def test_fair_close_removes_pinnacle_margin(self):
        self.assertAlmostEqual(books.fair_close(1.90, 1.90), 2.0)
        self.assertAlmostEqual(books.fair_close_proportional(1.5, 2.6), (1 / 1.5 + 1 / 2.6) / (1 / 1.5))
        self.assertIsNone(books.fair_close(None, 2.0))
        self.assertIsNone(books.fair_close(1.0, 2.0))

    def test_power_devig(self):
        # Marché équilibré : puissance = proportionnelle = 2,00 / 2,00 exactement.
        self.assertAlmostEqual(books.fair_close(1.90, 1.90), 2.0, places=9)
        self.assertAlmostEqual(books.fair_close_proportional(1.90, 1.90), 2.0, places=9)
        # 1,20 / 4,80 : k tel que (1/1,2)^k + (1/4,8)^k = 1, probabilités somme 1.
        k = books.power_exponent(1.20, 4.80)
        self.assertGreater(k, 1)
        fav, dog = books.fair_close(1.20, 4.80), books.fair_close(4.80, 1.20)
        self.assertAlmostEqual(1 / fav + 1 / dog, 1.0, places=9)
        self.assertAlmostEqual(1 / fav, (1 / 1.2) ** k, places=9)
        # La puissance donne plus de marge à l'outsider : cote juste plus haute que
        # la proportionnelle pour l'outsider, plus basse pour le favori.
        self.assertGreater(dog, books.fair_close_proportional(4.80, 1.20))
        self.assertLess(fav, books.fair_close_proportional(1.20, 4.80))
        self.assertAlmostEqual(fav, 1.2202, places=3)   # proportionnelle : 1,25
        self.assertAlmostEqual(dog, 5.5413, places=3)   # proportionnelle : 5,00
        # Entrées invalides : None ; marge négative toujours résolue.
        self.assertIsNone(books.fair_close(1.0, 2.0))
        self.assertAlmostEqual(1 / books.fair_close(2.1, 2.1), 0.5, places=9)

    def test_clv_pin_uses_margin_free_close_and_net_commission(self):
        self.assertAlmostEqual(books.clv_pin_pct("unibet.fr", 2.10, 1.90, 1.90), 5.0)
        # Betfair : cote effective 1 + 1.10 × 0.95 = 2.045 -> +2.25 %
        self.assertAlmostEqual(books.effective_odds("betfair-ex", 2.10), 2.045)
        self.assertAlmostEqual(books.clv_pin_pct("betfair-ex", 2.10, 1.90, 1.90), 2.25)
        self.assertAlmostEqual(books.pnl("betfair-ex", 2.10, True), 1.045)
        self.assertEqual(books.pnl("betfair-ex", 2.10, False), -1.0)
        self.assertAlmostEqual(books.pnl("unibet.fr", 2.10, True), 1.10)

    def test_book_flags(self):
        for name in ("winamax.fr", "unibet.fr", "pmu"):
            self.assertTrue(books.flags(name)["jouable_fr"], name)
        for name in ("pinnacle", "betfair-ex", "1xbet", "22bet", "unibet", "bet365"):
            f = books.flags(name)
            self.assertTrue(f["jouable"], name)
            self.assertFalse(f["jouable_fr"], name)
        self.assertFalse(books.flags("sbobet")["jouable"])
        self.assertEqual(books.flags("bet365.fr")["duplicate_of"], "bet365")
        self.assertTrue(books.flags("bet365.fr")["fr_incertain"])
        self.assertEqual(books.canonical("bet365.fr"), books.canonical("bet365"))
        self.assertTrue(books.flags("betfair-ex")["exchange"])

    def test_cluster_summary_and_holm(self):
        s = clv_stats.summary([1, 2, 3, None, 4, 5, 6], list("aabbccd"))
        self.assertEqual(s["n"], 6)
        self.assertAlmostEqual(s["mean_pct"], 3.5)
        self.assertLess(s["ci95"][0], 3.5)
        self.assertLess(s["p_one_sided"], 0.05)
        self.assertEqual(clv_stats.holm([0.01, None, 0.04]), [0.02, None, 0.04])


def _curve(points):
    return [[t, o, 500] for t, o in points]


class EngineV66Tests(unittest.TestCase):
    """Moteur V5 : plafond 30 min, CLV Pinnacle, commission ; mode legacy inchangé."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        (self.root / "parts").mkdir()
        self.uid = "atp_demo_a_vs_b"
        (self.root / "set_results.json").write_text(json.dumps({self.uid: {"match": "home"}}))
        rows = [
            self._record("acme", [("2026-10-01T10:45:00Z", 2.10)], [("2026-10-01T10:45:00Z", 1.75)]),
            self._record("stale", [("2026-10-01T10:15:00Z", 2.10)], [("2026-10-01T10:15:00Z", 1.75)]),
            self._record("betfair-ex", [("2026-10-01T10:45:00Z", 2.10)], [("2026-10-01T10:45:00Z", 1.75)]),
            self._record("pinnacle",
                         [("2026-10-01T10:40:00Z", 2.00), ("2026-10-01T11:59:00Z", 1.90)],
                         [("2026-10-01T10:40:00Z", 1.85), ("2026-10-01T11:59:00Z", 1.90)]),
        ]
        (self.root / "parts" / "hist_book_demo.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in rows))

    def tearDown(self):
        self.temp.cleanup()

    def _record(self, book, home, away):
        return {"uid": self.uid, "fixture_id": "fx-1", "book": book,
                "commence_time": "2026-10-01T12:00:00Z", "home": "A", "away": "B",
                "tournament": "ATP Demo", "home_curve": _curve(home), "away_curve": _curve(away)}

    def _rows(self, legacy):
        rows, _, _ = v5.load_observations(self.root, legacy=legacy)
        return {(r["book"], r["side"]): r for r in rows if r["horizon"] == "1h"}

    def test_quote_age_cap_30_minutes_but_legacy_unchanged(self):
        self.assertEqual(v5.MAX_QUOTE_AGE_MIN, 30)
        new, old = self._rows(False), self._rows(True)
        self.assertNotIn(("stale", "home"), new)       # 45 min > 30 min
        self.assertIn(("stale", "home"), old)          # règle V6.3 d'origine
        self.assertIn(("acme", "home"), new)

    def test_clv_pinnacle_margin_free_and_betfair_commission(self):
        rows = self._rows(False)
        acme = rows[("acme", "home")]
        self.assertAlmostEqual(acme["clv_pin_pct"], 5.0)
        # Secondaire (même book) : aucun point après la décision -> pas de clôture book.
        self.assertIsNone(acme["clv_book_pct"])
        self.assertAlmostEqual(acme["pnl"], 1.10)
        betfair = rows[("betfair-ex", "home")]
        self.assertAlmostEqual(betfair["clv_pin_pct"], 2.25)
        self.assertAlmostEqual(betfair["pnl"], 1.045)
        self.assertFalse(betfair["jouable_fr"])
        legacy = self._rows(True)[("betfair-ex", "home")]
        self.assertAlmostEqual(legacy["pnl"], 1.10)  # gels V6.3 : P&L d'origine
        # Pinnacle comparé à lui-même : écart sans objet en V6.6.
        self.assertIsNone(rows[("pinnacle", "home")]["pinnacle_gap_pct"])

    def test_missing_pinnacle_close_gives_null_clv_and_is_counted(self):
        rows = [dict(r, clv_pin_pct=None) for r in self._rows(False).values()]
        stats = v5._stats(rows, v5.load_autoresearch_stats())
        self.assertEqual(stats["clv_pin_n"], 0)
        self.assertEqual(stats["sans_cloture_pinnacle"], len(rows))
        self.assertIsNone(stats["clv_pin_mean_pct"])


def _write_history(path, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["date", "circuit", "vainqueur", "perdant", "psw", "psl", "tournoi", "surface"])
    writer.writerows(rows)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write(buffer.getvalue())


class HistoryStabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        (self.root / "historique").mkdir()
        rows = []
        for year in range(2015, 2022):
            for i in range(40):
                day = f"{year}-03-{1 + i % 28:02d}"
                # Favori 1.20 gagne 90 % sur terre battue ATP (meilleur que le prix).
                if i % 10:
                    rows.append([day, "ATP", f"F{i}", f"O{i}", "1.20", "4.50", "Monte Carlo Masters", "Clay"])
                else:
                    rows.append([day, "ATP", f"O{i}", f"F{i}", "4.50", "1.20", "Monte Carlo Masters", "Clay"])
                # Sur dur : 1.20 gagne 75 %.
                if i % 4:
                    rows.append([day, "ATP", f"G{i}", f"P{i}", "1.20", "4.50", "Other Open", "Hard"])
                else:
                    rows.append([day, "ATP", f"P{i}", f"G{i}", "4.50", "1.20", "Other Open", "Hard"])
        _write_history(self.root / hs.SOURCE, rows)

    def tearDown(self):
        self.temp.cleanup()

    def test_tiny_fixture_report(self):
        report = hs.build(self.root, permutations=200)
        self.assertEqual(report["matches"], 7 * 80)
        cell = next(c for c in report["cells"] if c["cell"] == "côté favori · cote 1,01–1,30 · circuit ATP · surface Clay")
        self.assertTrue(cell["eligible"])
        self.assertEqual(cell["years_tested"], 7)
        self.assertGreater(cell["roi_pct"], 0)
        self.assertLess(cell["p_permutation"], 0.05)
        self.assertTrue(cell["passes"])
        self.assertIsNotNone(cell["p_holm"])
        hard = next(c for c in report["cells"] if c["cell"] == "côté favori · cote 1,01–1,30 · circuit ATP · surface Hard")
        self.assertFalse(hard["passes"])
        self.assertIn(cell["cell"], [c["cell"] for c in report["passing"]])
        tag = hs.stability_tag(1.2, "ATP", "favori", "Clay", report=report)
        self.assertEqual(tag["tag"], "stable 16 ans")
        self.assertEqual(hs.stability_tag(1.2, "Challenger", "favori", report=report)["cell"],
                         "côté favori · cote 1,01–1,30")
        self.assertEqual(hs.stability_tag(None, "ATP", report=report)["tag"], "non disponible")

    def test_requires_five_years_and_200_permutations(self):
        with self.assertRaises(SystemExit):
            hs.main([str(self.root), "--permutations", "50"])
        report = hs.analyse([b for b in hs.load_bets(self.root / hs.SOURCE) if b["year"] < "2019"], 200)
        self.assertTrue(all(not c["eligible"] for c in report["cells"]))


def _segment(i, book="unibet.fr", clv=3.0, low=0.5, n=100, members=None, market="match"):
    members = members or [hashlib.sha256(f"fx-{i}-{k}".encode()).hexdigest() for k in range(n)]
    return {
        "market": market, "book": book, "horizon": "1h", "selection": "favori",
        "circuit": "ATP", "criteria": [{"dimension": "marge", "value": f"seg {i}"}],
        "predicates": [], "unique_matches": n, "n": n, "distinct_days": 30,
        "clv_pin_n": n, "clv_pin_mean_pct": clv, "clv_pin_ci95": [low, clv + 2],
        "p_holm_clv_pin": 0.5, "roi_pct": 4.0, "roi_ci95": [-10, 18], "mean_odds": 1.8,
        "feature_availability": {"verified": True}, "discovery_fixture_hashes": members,
        "start_date": "2026-06-01", "end_date": "2026-10-10",
    }


class SelectionV66Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        (self.root / "Tennis_Edge_Lab/live").mkdir(parents=True)
        (self.root / "Tennis_Edge_Lab/registry").mkdir(parents=True)
        self.registry = self.root / sel.REGISTRY

    def tearDown(self):
        self.temp.cleanup()

    def _propose(self, segments):
        doc = sel.propose(self.root, dt.date(2026, 10, 15), segments=segments, report={"cells": []})
        sel.write_proposals(self.root, doc)
        return json.loads((self.root / sel.PROPOSALS).read_text())

    def test_propose_never_freezes_and_respects_limits(self):
        fr_books = ("winamax.fr", "unibet.fr", "pmu")
        segments = [_segment(i, book=fr_books[i % 3], market=("match", "set1")[i // 3 % 2],
                             clv=10 - i * 0.1, low=5 - i * 0.1) for i in range(15)]
        segments.append(_segment(99, book="sbobet", clv=50))          # non jouable
        segments.append(_segment(98, clv=40, n=50))                     # n < 80
        segments.append(_segment(97, clv=-1))                           # CLV ≤ 0
        doc = self._propose(segments)
        self.assertFalse(self.registry.exists())
        self.assertFalse(doc["freeze_automatic"])
        self.assertEqual(len(doc["proposals"]), sel.MAX_PER_WEEK)
        self.assertNotIn("sbobet", {p["book"] for p in doc["proposals"]})
        self.assertTrue(all(p["n"] >= 80 and p["clv_pin_mean_pct"] > 0 for p in doc["proposals"]))
        self.assertTrue(all(p["jouable_fr"] for p in doc["proposals"]))
        families = collections.Counter((p["book"], p["market"]) for p in doc["proposals"])
        self.assertLessEqual(max(families.values()), sel.MAX_PER_BOOK_MARKET)
        lows = [p["clv_pin_ci95"][0] for p in doc["proposals"]]
        self.assertEqual(lows, sorted(lows, reverse=True))
        self.assertIn("stabilite_16_ans", doc["proposals"][0])
        self.assertTrue(doc["proposals"][0]["note_mecanisme"])
        # La même semaine : propositions inchangées (au plus 10 par semaine).
        again = sel.propose(self.root, dt.date(2026, 10, 17), segments=[_segment(50, clv=99)])
        self.assertTrue(again.get("unchanged_this_week"))

    def test_bet365_duplicate_and_near_identical_populations_not_double_counted(self):
        a = _segment(1, book="bet365")
        b = dict(_segment(1, book="bet365.fr"), discovery_fixture_hashes=a["discovery_fixture_hashes"])
        doc = self._propose([a, b])
        self.assertEqual(len(doc["proposals"]), 1)

    def test_freeze_only_chosen_ids_and_strictly_prospective(self):
        doc = self._propose([_segment(i) for i in range(3)])
        chosen = doc["proposals"][0]["id"]
        with self.assertRaises(ValueError):
            sel.freeze(self.root, ["deadbeefdeadbeef"])
        with self.assertRaises(ValueError):
            sel.freeze(self.root, ["pas-un-id"])
        with self.assertRaises(ValueError):
            sel.freeze(self.root, [])
        when = dt.datetime(2026, 10, 15, 18, 0, tzinfo=dt.timezone.utc)
        created = sel.freeze(self.root, [chosen], when)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["eligible_after_utc"], "2026-10-16")
        with self.assertRaises(ValueError):
            sel.freeze(self.root, [chosen], when)
        record = sel.read_registry(self.root)[0]
        index = record["criteria"][0]["value"].split()[-1]
        discovery_fixture = f"fx-{index}-0"
        base = {"market": "match", "book": "unibet.fr", "horizon": "1h", "side_type": "favori",
                "feature_available_by_decision": True, "pnl": 1.0, "clv_pin_pct": 2.0}

        class FakeEngine:
            @staticmethod
            def _criteria(row):
                return [("marge", row["seg"])]
        seg = record["criteria"][0]["value"]
        rows = [
            dict(base, fixture_id="fx-a", date="2026-10-15", decision_ts="2026-10-15T17:00:00+00:00", seg=seg),  # avant gel
            dict(base, fixture_id="fx-b", date="2026-10-15", decision_ts="2026-10-15T20:00:00+00:00", seg=seg),  # jour du gel
            dict(base, fixture_id=discovery_fixture, date="2026-10-17", decision_ts="2026-10-17T10:00:00+00:00", seg=seg),
            dict(base, fixture_id="fx-c", date="2026-10-16", decision_ts="2026-10-16T09:00:00+00:00", seg=seg),
            dict(base, fixture_id="fx-d", date="2026-10-16", decision_ts="2026-10-16T09:00:00+00:00", seg="autre"),
        ]
        selected = sel.prospective_rows(FakeEngine, record, rows)
        self.assertEqual([r["fixture_id"] for r in selected], ["fx-c"])

    def test_registry_chain_detects_tampering(self):
        doc = self._propose([_segment(i) for i in range(2)])
        sel.freeze(self.root, [doc["proposals"][0]["id"]])
        text = self.registry.read_text().replace('"jouable_fr":true', '"jouable_fr":false')
        self.registry.write_text(text)
        with self.assertRaises(ValueError):
            sel.read_registry(self.root)


class AutoresearchClvPinTests(unittest.TestCase):
    def test_safe_row_uses_margin_free_pinnacle_close(self):
        import autoresearch as ar
        ar._external_features = {}
        ar._pin_close = {"u1": {"pin_close_side": 1.9, "pin_close_other": 1.9, "pin_fair_close": 2.0}}
        row = {"date": "2026-10-01", "entry": "2.1", "pin_open": "2.0", "lead_min": "600",
               "mag_cote_pct": "4", "steame_gagne": "oui", "pnl": "1.1", "uid": "u1",
               "entry_book": "unibet", "tour": "ATP Demo", "clv_book_pct": "3.0",
               "clv_vs_pin_pct": "10.5"}
        parsed = ar.safe_row(row)
        self.assertAlmostEqual(parsed["clv_pin"], 5.0)
        self.assertEqual(parsed["clv_pin_brut"], 10.5)
        self.assertEqual(parsed["clv_book"], 3.0)
        parsed = ar.safe_row(dict(row, uid="u2"))
        self.assertIsNone(parsed["clv_pin"])
        stats = ar.stats_roi([parsed])
        self.assertEqual(stats["sans_cloture_pinnacle"], 1)
        ar._external_features = None
        ar._pin_close = None


class CommitGuardTests(unittest.TestCase):
    def test_timestamp_only_change_is_restored(self):
        import subprocess
        import commit_guard
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            run = lambda *a: subprocess.run(["git", *a], cwd=root, check=True, capture_output=True)
            run("init", "-q")
            (root / "a.json").write_text(json.dumps({"generated_at": "2026-10-01", "x": 1}))
            (root / "b.json").write_text(json.dumps({"generated_at": "2026-10-01", "x": 1}))
            run("add", "-A")
            run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
            (root / "a.json").write_text(json.dumps({"generated_at": "2026-10-02", "x": 1}))
            (root / "b.json").write_text(json.dumps({"generated_at": "2026-10-02", "x": 2}))
            commit_guard.main(["--root", str(root), "a.json", "b.json"])
            self.assertEqual(json.loads((root / "a.json").read_text())["generated_at"], "2026-10-01")
            self.assertEqual(json.loads((root / "b.json").read_text())["x"], 2)


if __name__ == "__main__":
    unittest.main()
