"""V6.9 : jeu « Tous les matchs », filtres multi-critères (parité Python/JS), gels v2."""
import datetime as dt
import gzip
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

LAB = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))
import books  # noqa: E402
import explorer_gel as xg  # noqa: E402
import explorer_matchs as xm  # noqa: E402

START = dt.datetime(2026, 10, 1, 12, 0, tzinfo=dt.timezone.utc)


def at(minutes_before):
    return (START - dt.timedelta(minutes=minutes_before)).strftime("%Y-%m-%dT%H:%M:%S")


def record(book, home, away):
    return {"uid": "2026-10-01_ann_alpha_bea_beta", "fixture_id": "fx1", "book": book,
            "commence_time": "2026-10-01T12:00:00Z", "home": "Ann Alpha", "away": "Bea Beta",
            "tournament": "WTA Beijing", "home_curve": home, "away_curve": away}


class MatchsDatasetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.root = pathlib.Path(self.tmp.name)
        (root / "parts").mkdir()
        rows = [
            # Pinnacle : ouverture 2,20/1,70, à 1 h 2,00/1,85 (deux côtés), clôture 1,90/1,90, puis un point APRÈS le début.
            record("pinnacle",
                   [[at(1500), 2.2], [at(70), 2.0], [at(1), 1.9], [at(-30), 1.2]],
                   [[at(1500), 1.7], [at(70), 1.85], [at(1), 1.9], [at(-30), 4.0]]),
            record("unibet.fr", [[at(65), 2.15]], [[at(65), 1.75]]),     # FR, 5 min avant la décision 1 h
            record("betfair-ex", [[at(62), 2.30]], [[at(62), 1.80]]),    # bourse : commission
            record("1xbet", [[at(110), 2.60]], [[at(110), 1.60]]),       # 50 min : trop ancien (> 30 min)
        ]
        with gzip.open(root / "parts/hist_book_2026-W40.jsonl.gz", "wt", encoding="utf-8") as stream:
            stream.write("".join(json.dumps(r) + "\n" for r in rows))
        (root / "set_results.json").write_text(json.dumps({"2026-10-01_ann_alpha_bea_beta": {"match": "home"}}))
        self.doc = xm.build(root, environ={})
        names = [c["name"] for c in self.doc["columns"]]
        self.rows = [{n: (self.doc["dicts"][n][self.doc["data"][n][i]] if n in self.doc["dicts"] else self.doc["data"][n][i])
                      for n in names} for i in range(self.doc["n"])]

    def tearDown(self):
        self.tmp.cleanup()

    def row(self, horizon, player):
        return next(r for r in self.rows if r["horizon"] == horizon and r["joueur"] == player)

    def test_horizon_selection_requires_pinnacle_both_sides(self):
        # 6 h : aucun point Pinnacle dans la fenêtre de 3 h ; 10 min : le dernier point (T−1 min) est après la décision.
        self.assertEqual({r["horizon"] for r in self.rows}, {"24h", "1h"})
        self.assertEqual(len(self.rows), 4)

    def test_entries_devig_commission_and_freshness(self):
        r = self.row("1h", "Ann Alpha")
        self.assertEqual(r["cote_pin"], 2.0)
        self.assertEqual(r["book_jouable"], "betfair-ex")             # 1 + 1,30 × 0,95 = 2,235 > 2,15 ; 1xbet trop ancien
        self.assertAlmostEqual(r["cote_jouable"], books.effective_odds("betfair-ex", 2.30), places=3)
        self.assertEqual(r["book_fr"], "unibet.fr")
        self.assertEqual(r["cote_fr"], 2.15)
        self.assertEqual(r["nb_books"], 4)
        self.assertAlmostEqual(r["clv_pinnacle"], books.clv_pin_pct("pinnacle", 2.0, 1.9, 1.9), places=2)
        self.assertAlmostEqual(r["clv_fr"], 7.5, places=2)              # 2,15 / 2,00 − 1
        self.assertAlmostEqual(r["clv_jouable"], books.clv_pin_pct("betfair-ex", 2.30, 1.9, 1.9), places=2)
        self.assertAlmostEqual(r["pnl_jouable"], 1.235, places=3)
        self.assertEqual(r["gagne"], 1)
        self.assertEqual(r["cloture_pin"], 1.9)                         # dernier point AVANT le début
        self.assertAlmostEqual(r["move_pin_pct"], 100 * (2.0 / 2.2 - 1), places=2)
        fair_h = books.fair_close(2.0, 1.85)
        self.assertAlmostEqual(r["ecart_fr_pct"], 100 * (2.15 / fair_h - 1), places=2)

    def test_look_ahead_fields_are_never_filters(self):
        for name in ("cloture_pin", "move_cloture_pct", "gagne", "clv_pinnacle", "pnl_jouable", "decision_ts", "date"):
            self.assertNotIn(name, xm.FILTER_FIELDS)
        roles = {c["name"]: c["role"] for c in self.doc["columns"]}
        self.assertEqual(roles["cloture_pin"], "post_entree")
        self.assertEqual(roles["move_cloture_pct"], "post_entree")

    def test_compact_encoding(self):
        self.assertIn("circuit", self.doc["dicts"])
        self.assertTrue(all(isinstance(v, int) for v in self.doc["data"]["circuit"]))


class MaterializeTests(unittest.TestCase):
    def test_r2_materialization_only_when_requested(self):
        fake = mock.Mock()
        fake.materialize_hist.return_value = {"hist_book_2026-W30.jsonl.gz": "ok"}
        with mock.patch.object(xm, "_load", return_value=fake) as loader:
            self.assertEqual(xm.materialize({}), {})
            loader.assert_not_called()
            self.assertEqual(xm.materialize({"R2_HIST_MATERIALIZE": "1"}), {"hist_book_2026-W30.jsonl.gz": "ok"})
            fake.materialize_hist.assert_called_once()
            self.assertEqual(fake.materialize_hist.call_args.args[0], "book")
        with mock.patch.object(xm, "_load", side_effect=RuntimeError("pas de R2")):
            self.assertEqual(xm.materialize({"R2_HIST_MATERIALIZE": "1"}), {})   # ne lève jamais


class ParityTests(unittest.TestCase):
    def test_python_filter_matches_shared_fixture(self):
        fixture = json.loads((LAB / "tests/fixtures/explorer_parity.json").read_text(encoding="utf-8"))
        for spec in fixture["specs"]:
            got = [i for i, r in enumerate(fixture["rows"]) if xg.row_matches(r, spec["criteres"], spec["plages"])]
            self.assertEqual(got, spec["expected"], spec)


class FreezeV2Tests(unittest.TestCase):
    def test_spec_round_trip_and_validation(self):
        text = json.dumps({"jeu": "matchs", "criteres": {"circuit": ["ATP", "WTA"]},
                           "plages": {"cote_pin": [1.8, 2.4], "move_pin_pct": [None, -3]}, "entree": "fr",
                           "date": "2026-10-16", "stats": {"n": 12}})
        spec = xg.validate_spec(text)
        self.assertEqual(spec["plages"], {"cote_pin": [1.8, 2.4], "move_pin_pct": [None, -3.0]})
        self.assertEqual(spec["entree"], "fr")
        self.assertEqual(xg.validate_spec(json.dumps({"jeu": "alertes", "criteres": {}, "plages": {"cote": [1.8, 2.4]}}))["jeu"], "alertes")
        bad = [
            {"jeu": "matchs", "criteres": {}, "plages": {"cloture_pin": [1, 2]}},          # après coup
            {"jeu": "matchs", "criteres": {}, "plages": {"cote_pin": [3, 2]}},             # plage vide
            {"jeu": "matchs", "criteres": {}, "plages": {"cote_pin": [None, None]}},
            {"jeu": "matchs", "criteres": {"circuit": ["ATP"]}, "entree": "bet365"},
            {"jeu": "alertes", "criteres": {"type": ["H17"]}, "entree": "fr"},
            {"jeu": "matchs", "criteres": {"mois": ["2026-10"]}},
            {"jeu": "alertes", "criteres": {}, "plages": {"pin_move_entree_cloture": [0, 1]}},
        ]
        for spec_bad in bad:
            with self.assertRaises(ValueError, msg=spec_bad):
                xg.validate_spec(json.dumps(spec_bad))

    def test_matchs_freeze_is_prospective_and_uses_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            when = dt.datetime(2026, 10, 15, 18, 0, tzinfo=dt.timezone.utc)
            text = json.dumps({"jeu": "matchs", "criteres": {"circuit": ["ATP"]},
                               "plages": {"cote_pin": [1.8, 2.4]}, "entree": "fr"})
            record = xg.freeze(root, text, when)
            self.assertEqual(record["jeu"], "matchs")
            self.assertEqual(record["entree"], "fr")
            base = {"circuit": "ATP", "cote_pin": 2.0, "clv_fr": 3.0, "pnl_fr": 1.0, "clv_jouable": -9.0, "pnl_jouable": -1}
            rows = [
                dict(base, decision_ts="2026-10-15T17:00+00:00", date="2026-10-15"),
                dict(base, decision_ts="2026-10-15T20:00+00:00", date="2026-10-15"),
                dict(base, decision_ts="2026-10-16T09:00+00:00", date="2026-10-16"),
                dict(base, decision_ts="2026-10-16T09:00+00:00", date="2026-10-16", cote_pin=2.6),
                dict(base, decision_ts="2026-10-16T09:00+00:00", date="2026-10-16", cote_pin=None),
            ]
            self.assertEqual(len(xg.prospective(record, rows)), 1)
            report = xg.evaluate(root, {"alertes": [], "matchs": rows})
            c = report["candidates"][0]
            self.assertEqual((c["n"], c["clv_pin_mean_pct"], c["roi_pct"]), (1, 3.0, 100.0))
            self.assertEqual(c["entree"], "fr")

    def test_un_pari_par_joueur(self):
        """21/10/2026 : option « un pari par joueur et par match » (premier horizon), même règle que l'interface."""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            when = dt.datetime(2026, 10, 15, 18, 0, tzinfo=dt.timezone.utc)
            sans = xg.validate_spec(json.dumps({"jeu": "matchs", "criteres": {"circuit": ["WTA"]}, "entree": "jouable"}))
            avec = xg.validate_spec(json.dumps({"jeu": "matchs", "criteres": {"circuit": ["WTA"]}, "entree": "jouable",
                                                "un_par_joueur": True}))
            self.assertNotIn("un_par_joueur", sans)
            self.assertNotEqual(xg.spec_id(sans), xg.spec_id(avec))
            with self.assertRaises(ValueError):
                xg.validate_spec(json.dumps({"jeu": "alertes", "criteres": {"type": ["H17"]}, "un_par_joueur": True}))
            record = xg.freeze(root, json.dumps({"jeu": "matchs", "criteres": {"circuit": ["WTA"]},
                                                 "entree": "jouable", "un_par_joueur": True}), when)
            self.assertTrue(record["un_par_joueur"])
            base = {"circuit": "WTA", "date": "2026-10-16", "joueur": "A", "clv_jouable": 1.0, "pnl_jouable": 1.0}
            rows = [dict(base, horizon="10m", decision_ts="2026-10-16T14:50+00:00"),
                    dict(base, horizon="6h", decision_ts="2026-10-16T09:00+00:00"),
                    dict(base, horizon="1h", decision_ts="2026-10-16T14:00+00:00"),
                    dict(base, joueur="B", horizon="1h", decision_ts="2026-10-16T14:00+00:00")]
            sel = xg.prospective(record, rows)
            self.assertEqual([(r["joueur"], r["horizon"]) for r in sel], [("A", "6h"), ("B", "1h")])
            c = xg.evaluate(root, {"alertes": [], "matchs": rows})["candidates"][0]
            self.assertEqual((c["n"], c["un_par_joueur"]), (2, True))


if __name__ == "__main__":
    unittest.main()
