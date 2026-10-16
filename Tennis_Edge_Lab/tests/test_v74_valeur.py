"""V7.4 H19 « valeur contre Pinnacle juste » : gel intact, un pari par joueur, règle exacte,
persistance, Holm, jugement seulement après le gel."""
import datetime as dt
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

LAB = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))
spec = importlib.util.spec_from_file_location("t74_valeur", LAB / "valeur.py")
va = importlib.util.module_from_spec(spec)
spec.loader.exec_module(va)
UTC = dt.timezone.utc


def anchors(start, pts):
    """pts : {'open':(h,o), '24h':..., 'close':(h,o)} — h = heures avant le début."""
    p = lambda v: None if v is None else (start - dt.timedelta(hours=v[0]), v[1], None)
    return {"open": p(pts.get("open")), "close": p(pts.get("close")),
            "horizons": {h: p(pts.get(h)) for h in ("24h", "6h", "1h", "10m")}}


def match(uid, start, pin_home, pin_away, books_home, close_home=None, tournament="ATP Metz"):
    rec = {("%s" % uid, "pinnacle"): {"start": start, "home": "A", "away": "B", "tournament": tournament,
                                      "curves": {"home": anchors(start, pin_home), "away": anchors(start, pin_away)}}}
    for book, pts in books_home.items():
        rec[(uid, book)] = {"start": start, "home": "A", "away": "B", "tournament": tournament,
                            "curves": {"home": anchors(start, pts), "away": anchors(start, {})}}
    return rec


class Gel(unittest.TestCase):
    def test_gel_commite_intact(self):
        self.assertEqual(va.check_gel(LAB.parent)["etat"], "intact")

    def test_regle_figee(self):
        self.assertEqual((va.H19["ecart_min_pct"], va.H19["ecart_max_pct"], va.H19["age_max_min"], va.H19["cible_n"]),
                         (2.0, 8.0, 30, 300))
        self.assertEqual(va.H19["gele_le"], "2026-10-16")

    def test_gel_modifie_detecte(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / va.GEL_FILE
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps({"regle": {**va.H19, "ecart_min_pct": 1.0}, "sha256": va.empreinte()}))
            self.assertEqual(va.check_gel(tmp)["etat"], "MODIFIÉ")


class Regle(unittest.TestCase):
    def setUp(self):
        s = dt.datetime(2026, 10, 20, 15, tzinfo=UTC)
        pin_h = {"6h": (6, 2.0), "1h": (1, 2.0), "10m": (0.2, 1.95), "close": (0.05, 1.95)}
        pin_a = {"6h": (6, 1.9), "1h": (1, 1.9), "10m": (0.2, 1.95), "close": (0.05, 1.95)}
        fair6 = va.books.fair_close(2.0, 1.9)
        # bet365 à +3 % de la juste à 6 h ET à 1 h (un seul pari attendu : 6 h), prix disparu à la clôture
        b365 = {"6h": (6.1, round(fair6 * 1.03, 3)), "1h": (1.1, round(fair6 * 1.03, 3)), "close": (0.1, 1.9)}
        # betfair à +3 % brut mais commission 5 % : net sous le seuil
        bf = {"6h": (6.1, round(fair6 * 1.03, 3))}
        # book trop vieux (40 min) à +5 %
        old = {"6h": (6.7, round(fair6 * 1.05, 3))}
        self.records = match("m1", s, pin_h, pin_a, {"bet365": b365, "betfair-ex": bf, "unibet": old})
        self.fair6 = fair6

    def test_un_pari_par_joueur_premier_horizon(self):
        opps = va.opportunites(self.records, {"m1": {"match": "home"}})
        paris = va.premier(opps, va.regle_h19)
        self.assertEqual(len(paris), 1)
        p = paris[0]
        self.assertEqual((p["horizon"], p["book"]), ("6h", "bet365"))
        self.assertAlmostEqual(p["ecart"], 3.0, delta=0.1)
        self.assertFalse(p["persiste"])
        self.assertAlmostEqual(p["pnl"], p["cote"] - 1)
        self.assertAlmostEqual(p["clv"], 100 * (p["cote"] / va.books.fair_close(1.95, 1.95) - 1))

    def test_age_et_commission_respectes(self):
        opps = va.opportunites(self.records, {})
        six = [o for o in opps if o["horizon"] == "6h" and o["joueur"] == "A"][0]
        self.assertNotIn("unibet", [c["book"] for c in six["cands"]])            # 40 min : exclu
        bf = [c for c in six["cands"] if c["book"] == "betfair-ex"][0]
        self.assertLess(bf["ecart_pct"], 2.0)                                       # commission déduite

    def test_holm_monotone(self):
        cases = [{"n": 40, "clv": {"p": p}} for p in (0.001, 0.02, 0.03, 0.5)]
        self.assertEqual(va.holm(cases), 4)
        adj = [c["p_holm"] for c in sorted(cases, key=lambda c: c["clv"]["p"])]
        self.assertEqual(adj, sorted(adj))
        self.assertAlmostEqual(adj[0], 0.004)

    def test_jugee_seulement_apres_le_gel(self):
        s_avant = dt.datetime(2026, 10, 10, 15, tzinfo=UTC)
        rec = dict(self.records)
        for (uid, b), r in list(self.records.items()):
            rec[("m0", b)] = {**r, "start": s_avant,
                              "curves": {side: {k: (None if v is None else (
                                  {kk: (None if vv is None else (vv[0] - dt.timedelta(days=10), vv[1], None))
                                   for kk, vv in v.items()} if k == "horizons" else (v[0] - dt.timedelta(days=10), v[1], None)))
                                  for k, v in c.items()} for side, c in r["curves"].items()}}
        with tempfile.TemporaryDirectory() as tmp:
            doc = va.build({"records": rec, "results": {}, "root": tmp})
        self.assertEqual(doc["h19"]["prospectif"]["n"], 1)
        self.assertEqual(doc["h19"]["retrospectif"]["n"], 1)
        self.assertTrue(doc["h19"]["prospectif"]["verdict"].startswith("EN COURS"))


if __name__ == "__main__":
    unittest.main()
