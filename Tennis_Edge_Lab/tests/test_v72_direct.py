"""V7.2 « Matchs en direct » : référence Python de la similarité, instantané direct_matchs.json."""
import datetime as dt
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

LAB = pathlib.Path(__file__).resolve().parents[1]
ROOT = LAB.parent
sys.path.insert(0, str(LAB))
import direct_profils as dp  # noqa: E402


def _arrondi(x):
    """Les flottants à 9 décimales : l'ordre des additions peut varier d'une
    machine à l'autre (0.5725 contre 0.5724999999999999)."""
    if isinstance(x, float):
        return round(x, 9)
    if isinstance(x, list):
        return [_arrondi(v) for v in x]
    if isinstance(x, dict):
        return {k: _arrondi(v) for k, v in x.items()}
    return x


class Similarite(unittest.TestCase):
    def test_fixture_is_current(self):
        stored = json.loads((LAB / "tests/fixtures/direct_parity.json").read_text(encoding="utf-8"))
        self.assertEqual(_arrondi(json.loads(json.dumps(dp.fixture()))), _arrondi(stored))

    def test_power_fair_matches_books(self):
        spec = importlib.util.spec_from_file_location("tennis_edge_t72_books", LAB / "books.py")
        books = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(books)
        for a, b in ((1.5, 2.6), (1.232, 4.69), (2.05, 1.83), (1.01, 21.0)):
            self.assertAlmostEqual(dp.power_fair(a, b), books.fair_close(a, b), places=9)

    def test_no_post_decision_field(self):
        post = {"gagne", "clv_pinnacle", "clv_jouable", "clv_fr", "pnl_pinnacle", "pnl_jouable", "pnl_fr",
                "cloture_pin", "move_cloture_pct", "proba_juste"}
        self.assertFalse(post & set(dp.SIMILARITY_FIELDS))
        spec = importlib.util.spec_from_file_location("tennis_edge_t72_em", LAB / "explorer_matchs.py")
        em = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(em)
        roles = {f[0]: f[3] for f in em.FIELDS}
        for f in dp.SIMILARITY_FIELDS:
            self.assertEqual(roles[f], "filtre", f)
        self.assertEqual(roles["proba_juste"], "descriptif")

    def test_relaxation_stops_at_30(self):
        rows = [{"horizon": "6h", "circuit": "ATP", "surface": "Hard", "cote_pin": 2.0, "move_pin_pct": -3,
                 "ecart_jouable_pct": -1, "alerte_avant": "aucune", "clv_pinnacle": 1.0, "date": "2026-10-01"}] * 30
        p = {"horizon": "6h", "circuit": "ATP", "surface": "Hard", "cote_pin": 2.0, "move_dir": "raccourcie",
             "move_band": "−5 à −2 %", "ecart_band": "−2 à 0 %", "alerte": "non"}
        idx, relaxed, _, ok = dp.similar(rows, p)
        self.assertEqual((len(idx), relaxed, ok), (30, [], True))
        idx, relaxed, _, ok = dp.similar(rows[:29], p)
        self.assertEqual((ok, relaxed), (False, list(dp.RELAX)))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    return module


@unittest.skipUnless((ROOT / "scripts/direct_matchs.py").is_file() and (ROOT / "scripts/oddspapi_v5.py").is_file(),
                     "scripts absents")
class Instantane(unittest.TestCase):
    def test_build_window_open_and_alerts(self):
        dm = _load("tennis_edge_t72_dm", ROOT / "scripts/direct_matchs.py")
        now = dt.datetime(2026, 10, 16, 12, tzinfo=dt.timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)

            def curve(uid, book, start, h, a):
                return {"uid": uid, "book": book, "commence_time": start, "home": "Ann B", "away": "Bob C",
                        "tournament": "ATP Shanghai", "home_curve": h, "away_curve": a}
            rows = [curve("2026-10-16_ann_b_bob_c", "pinnacle", "2026-10-16T18:00:00Z",
                          [["2026-10-15T08:00:00", 2.0], ["2026-10-16T11:00:00", 1.8], ["2026-10-16T18:30:00", 1.5]],
                          [["2026-10-15T08:00:00", 1.9], ["2026-10-16T11:00:00", 2.1]]),
                    curve("2026-10-16_ann_b_bob_c", "unibet", "2026-10-16T18:00:00Z",
                          [["2026-10-16T11:30:00", 1.85]], [["2026-10-16T11:30:00", 2.0]]),
                    curve("2026-10-19_ann_b_bob_c", "pinnacle", "2026-10-19T18:00:00Z",       # hors fenêtre
                          [["2026-10-15T08:00:00", 2.0]], [["2026-10-15T08:00:00", 1.9]])]
            (d / "book_curves_live.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            (d / "h16_signal_log.jsonl").write_text(json.dumps({"uid": "2026-10-16_ann_b_bob_c", "joueur": "Ann B",
                                                                "signale_le": "2026-10-16T09:00:00", "cote": 1.9,
                                                                "book": "unibet", "envoye": True, "doublon": ""}) + "\n",
                                                    encoding="utf-8")
            doc = dm.build(d, "book_curves_live.jsonl", now=now)
            self.assertEqual(len(doc["matchs"]), 1)
            doc2 = dm.build(d, "book_curves_live.jsonl", now=dt.datetime(2026, 10, 16, 19, tzinfo=dt.timezone.utc))
            self.assertEqual(doc2["matchs"][0]["pin"]["courant"]["h"], 1.8)   # en cours : cote d'avant 18:00
            m = doc["matchs"][0]
            self.assertEqual(m["pin"]["ouverture"], {"h": 2.0, "a": 1.9, "t": "2026-10-15T08:00:00Z"})
            self.assertEqual(m["pin"]["courant"]["h"], 1.8)           # le point de 13:00 est dans le futur
            self.assertEqual(m["cotes"]["unibet"], [1.85, 2.0, "2026-10-16T11:30:00Z"])
            self.assertEqual((m["circuit"], m["alertes"][0]["type"]), ("ATP", "H16"))
            self.assertTrue(doc["books"]["unibet"]["jouable"])
            self.assertFalse(doc["books"]["pinnacle"]["jouable"])
            self.assertTrue(dm.ecrire_si_change(d / "o.json", doc))
            self.assertFalse(dm.ecrire_si_change(d / "o.json", dict(doc, genere_le="x")))


if __name__ == "__main__":
    unittest.main()
