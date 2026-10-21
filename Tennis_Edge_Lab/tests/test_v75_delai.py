"""V7.5 délai alerte -> pari : prix du book alerté après l'envoi, CLV au prix disponible."""
import datetime as dt
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

LAB = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))
spec = importlib.util.spec_from_file_location("t75_delai", LAB / "delai_alertes.py")
da = importlib.util.module_from_spec(spec)
spec.loader.exec_module(da)
UTC = dt.timezone.utc
START = dt.datetime(2026, 10, 20, 15, tzinfo=UTC)
T0 = START - dt.timedelta(hours=2)


def cp(h, o):
    return (START - dt.timedelta(hours=h), o, None)


class Delai(unittest.TestCase):
    def setUp(self):
        self.records = {("m1", "pinnacle"): {
            "start": START, "home": "Alpha Un", "away": "Beta Deux", "tournament": "ATP X",
            "curves": {"home": {"open": cp(30, 2.1), "close": cp(0.1, 2.0), "horizons": {}},
                       "away": {"open": cp(30, 1.8), "close": cp(0.1, 1.9), "horizons": {}}}}}
        # bet365 : 2,20 jusqu'à T0+4 min, puis 2,05 ; unibet stable à 2,10
        self.series = {"m1": {"bet365": {"home": [(T0 - dt.timedelta(minutes=30), 2.2), (T0 + dt.timedelta(minutes=4), 2.05)],
                                         "away": []},
                              "unibet": {"home": [(T0 - dt.timedelta(hours=1), 2.1)], "away": []}}}
        self.alertes = [{"code": "H17", "uid": "m1", "joueur": "Alpha Un", "book": "bet365", "cote": 2.2, "t": T0}]

    def test_prix_tenu_puis_corrige(self):
        lignes, sans = da.mesurer(self.alertes, self.records, self.series)
        self.assertEqual(sans, 0)
        par = {l["delai"]: l for l in lignes}
        self.assertTrue(par[2]["tient"])
        self.assertFalse(par[5]["tient"])
        fair = da.books.fair_close(2.0, 1.9)
        self.assertAlmostEqual(par[0]["clv"], 100 * (2.2 / fair - 1))
        self.assertAlmostEqual(par[5]["clv"], 100 * (2.05 / fair - 1))
        self.assertAlmostEqual(par[5]["clv_meilleur"], 100 * (2.1 / fair - 1))   # unibet mieux que bet365 corrigé

    def test_resume_et_alertes_lues(self):
        lignes, _ = da.mesurer(self.alertes, self.records, self.series)
        R = {(r["hypothese"], r["delai_min"]): r for r in da.resume(lignes)}
        self.assertEqual(R[("toutes", 5)]["prix_tenu"], 0.0)
        with tempfile.TemporaryDirectory() as tmp:
            pathlib.Path(tmp, "h17_signal_log.jsonl").write_text("\n".join(json.dumps(x) for x in [
                {"uid": "m1", "joueur": "Alpha Un", "book": "bet365", "cote": 2.2, "signale_le": "2026-10-20T13:00:00", "envoye": True},
                {"uid": "m2", "joueur": "C", "book": "bet365", "cote": 2.2, "signale_le": "2026-10-20T13:00:00", "envoye": False},
                {"uid": "m3", "joueur": "D", "book": "bet365", "cote": 2.2, "signale_le": "2026-10-20T13:00:00", "envoye": True, "doublon": "h13"}]))
            al = da.lire_alertes(tmp)
        self.assertEqual([a["uid"] for a in al], ["m1"])                    # envoyées, hors doublons


if __name__ == "__main__":
    unittest.main()
