"""V6.7 Explorateur : jeux de données, champs après coup exclus des filtres,
résultat/CLV/P&L, carte des surfaces, cube historique, gels prospectifs."""
import csv
import datetime as dt
import gzip
import io
import json
import pathlib
import sys
import tempfile
import unittest

LAB = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))
import books  # noqa: E402
import explorer_build as xb  # noqa: E402
import explorer_gel as xg  # noqa: E402
import tennis_meta as meta  # noqa: E402


def jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def history_csv(path, rows):
    buffer = io.StringIO()
    w = csv.writer(buffer)
    w.writerow(["date", "circuit", "vainqueur", "perdant", "psw", "psl", "tournoi", "surface"])
    w.writerows(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write(buffer.getvalue())


class MetaTests(unittest.TestCase):
    def test_circuit_and_bands(self):
        self.assertEqual(meta.circuit_of("US Open Men Singles"), "Grand Chelem")
        self.assertEqual(meta.circuit_of("ATP Challenger Palermo"), "Challenger")
        self.assertEqual(meta.circuit_of("WTA Beijing"), "WTA")
        self.assertEqual(meta.circuit_of("ATP Shanghai"), "ATP")
        self.assertEqual(meta.circuit_of("Berlin"), "Autre")
        self.assertEqual(meta.odds_band(1.25), "1,01–1,30")
        self.assertEqual(meta.odds_band(6), "≥ 5,00")
        self.assertEqual(meta.band(45, meta.LEAD_BANDS), "30–90 min")

    def test_surface_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "h.csv.gz"
            history_csv(path, [["2024-01-02", "ATP", "A", "B", "1.5", "2.5", "Brisbane International", "Hard"]])
            surfaces = meta.SurfaceMap(path)
            self.assertEqual(surfaces.lookup("ATP Shanghai"), ("Hard", "table manuelle"))
            self.assertEqual(surfaces.lookup("ATP Challenger Palermo"), ("Clay", "table manuelle"))
            self.assertEqual(surfaces.lookup("ATP Challenger Biella")[0], "inconnue")
            self.assertEqual(surfaces.lookup("ATP Brisbane"), ("Hard", "tennis-data"))
            self.assertEqual(surfaces.lookup("US Open Women Singles")[0], "Hard")
            self.assertEqual(surfaces.lookup("?")[0], "inconnue")


class AlertsDatasetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.root = pathlib.Path(self.tmp.name)
        uid = "2026-10-01_ann_alpha_bea_beta"
        start = "2026-10-01T12:00:00"
        jsonl(root / "h17_signal_log.jsonl", [
            {"uid": uid, "signale_le": "2026-10-01T08:00:00", "joueur": "Ann Alpha", "adversaire": "Bea Beta",
             "tournoi": "WTA Beijing", "cote": 2.10, "book": "unibet", "ampleur_pts": 3.4,
             "commence": start, "envoye": True},
            {"uid": uid, "signale_le": "2026-10-01T08:05:00", "joueur": "Ann Alpha", "adversaire": "Bea Beta",
             "tournoi": "WTA Beijing", "cote": 2.10, "book": "unibet", "commence": start,
             "envoye": True, "doublon": "oui"},
            {"uid": uid, "signale_le": "2026-10-01T08:06:00", "joueur": "Bea Beta", "adversaire": "Ann Alpha",
             "tournoi": "WTA Beijing", "cote": 1.9, "book": "unibet", "commence": start, "envoye": False},
        ])
        jsonl(root / "canal_public_log.jsonl", [
            {"t": "2026-10-01T09:00:00", "uid": uid, "joueur": "Ann Alpha", "commence": start,
             "tournoi": "WTA Beijing", "ampleur_pts": 4.0, "cote_ref_apres": 1.9,
             "retards_tous": [["4casters", 2.50, 9.0], ["bet365", 2.05, 3.0], ["betfair-ex", 2.04, 2.0]]},
            {"t": "2026-10-01T10:00:00", "uid": uid, "joueur": "Ann Alpha", "commence": start,
             "retards_tous": [["bet365", 2.20, 3.0]]},
        ])
        jsonl(root / "odds_alerts_log.jsonl", [
            {"logged_at": "2026-10-01T07:00:00", "uid": uid, "home": "Ann Alpha", "away": "Bea Beta",
             "tournament": "WTA Beijing", "commence_time": "2026-10-01T12:00:00Z", "mins_before": 300,
             "o_home_first": 2.3, "o_home_last": 2.1, "o_away_first": 1.6, "o_away_last": 1.7,
             "mv_home_pct": -8.7, "mv_away_pct": 6.2},
        ])
        jsonl(root / "clv_history.jsonl", [{
            "uid": "wta_beijing_ann_alpha_vs_bea_beta", "commence_time": "2026-10-01T12:00:00Z",
            "home": "Ann Alpha", "away": "Bea Beta", "tournament": "WTA Beijing",
            "home_curve": [["2026-09-30T12:00:00", 2.2], ["2026-10-01T07:30:00", 2.0], ["2026-10-01T11:59:00", 1.9],
                           ["2026-10-01T13:00:00", 1.2]],
            "away_curve": [["2026-09-30T12:00:00", 1.7], ["2026-10-01T07:30:00", 1.85], ["2026-10-01T11:59:00", 1.9],
                           ["2026-10-01T13:00:00", 4.0]],
        }])
        (root / "set_results.json").write_text(json.dumps({"wta_beijing_ann_alpha_vs_bea_beta": {"match": "home"}}))
        self.doc = xb.build_alerts(root)
        cols = self.doc["columns"]
        self.rows = [dict(zip(cols, r)) for r in self.doc["rows"]]

    def tearDown(self):
        self.tmp.cleanup()

    def by_type(self, kind):
        return [r for r in self.rows if r["type"] == kind]

    def test_selection_of_alerts(self):
        self.assertEqual(len(self.by_type("H17")), 1)          # doublon et non envoyé exclus
        self.assertEqual(len(self.by_type("PUBLIC")), 1)       # première alerte par uid + joueur
        self.assertEqual(len(self.by_type("MOUVEMENT")), 1)
        public = self.by_type("PUBLIC")[0]
        self.assertEqual(public["book"], "bet365")             # flux 4casters exclu
        self.assertEqual(public["cote"], 2.05)
        mouvement = self.by_type("MOUVEMENT")[0]
        self.assertEqual(mouvement["book"], xb.REF_BOOK)
        self.assertEqual(mouvement["jouable"], "non")
        self.assertEqual(mouvement["joueur"], "Ann Alpha")     # côté renforcé (cote en baisse)

    def test_result_clv_pnl_with_power_devig_and_pre_start_close(self):
        h = self.by_type("H17")[0]
        self.assertEqual(h["gagne"], 1)
        # Clôture = dernier point AVANT le début (1,90 / 1,90), jamais 1,20 / 4,00.
        self.assertEqual((h["pin_close"], h["pin_close_adv"]), (1.9, 1.9))
        self.assertAlmostEqual(h["clv_pin"], books.clv_pin_pct("unibet", 2.10, 1.9, 1.9), places=3)
        self.assertAlmostEqual(h["clv_pin"], 5.0, places=3)
        self.assertAlmostEqual(h["pnl"], 1.10, places=4)
        self.assertEqual(h["cote_pinnacle"], "outsider")        # Pinnacle à 08:00 : 2,0 contre 1,85
        self.assertAlmostEqual(h["pin_move_entree_cloture"], -5.0, places=2)

    def test_cross_alert_features(self):
        h, public = self.by_type("H17")[0], self.by_type("PUBLIC")[0]
        self.assertEqual(h["suivie_public"], "oui")
        self.assertEqual(h["minutes_vers_public"], 60.0)
        self.assertEqual(public["precede_par_H"], "oui")
        self.assertEqual(public["minutes_depuis_H"], 60.0)
        self.assertEqual(self.by_type("MOUVEMENT")[0]["precede_par_H"], "non")
        self.assertEqual(h["nb_alertes_match"], "3+")

    def test_look_ahead_fields_are_never_filters(self):
        roles = {f["name"]: f["role"] for f in self.doc["fields"]}
        self.assertEqual(roles["pin_move_entree_cloture"], "post_entree")
        for name in ("pin_move_entree_cloture", "pin_close", "pin_close_adv", "gagne", "pnl", "clv_pin",
                     "minutes_vers_public", "suivie_public"):
            self.assertNotIn(name, xb.FILTER_FIELDS)
        self.assertEqual(roles["suivie_public"], "filtre_apres_alerte")


class HistoCubeTests(unittest.TestCase):
    def test_cube_sums_match_direct_computation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            rows = [["2020-01-0%d" % (1 + i % 5), "ATP", f"A{i}", f"B{i}", "1.40" if i % 3 else "3.10",
                     "3.10" if i % 3 else "1.40", "French Open", "Clay"] for i in range(30)]
            history_csv(root / "historique/tennis_data.csv.gz", rows)
            cube = xb.build_histo(root)
            n = sum(c[6] for c in cube["cells"])
            self.assertEqual(n, 60)
            direct = sum((float(r[4]) - 1) - 1 for r in rows)  # vainqueur gagne, perdant perd
            self.assertAlmostEqual(sum(c[8] for c in cube["cells"]), direct, places=6)
            self.assertTrue(all(c[3] == "Grand Chelem" for c in cube["cells"]))


class FreezeSpecTests(unittest.TestCase):
    def test_validation(self):
        ok = xg.validate_spec(json.dumps({"jeu": "alertes", "criteres": {"type": ["H17"], "circuit": "ATP"}}))
        self.assertEqual(ok["criteres"], {"circuit": ["ATP"], "type": ["H17"]})
        bad = [
            {"jeu": "histo", "criteres": {"circuit": ["ATP"]}},
            {"jeu": "alertes", "criteres": {}},
            {"jeu": "alertes", "criteres": {"suivie_public": ["oui"]}},
            {"jeu": "alertes", "criteres": {"mois": ["2026-10"]}},
            {"jeu": "alertes", "criteres": {"pin_move_entree_cloture": ["x"]}},
            {"jeu": "alertes", "criteres": {"inconnu": ["x"]}},
            {"jeu": "alertes", "criteres": {"type": []}},
        ]
        for spec in bad:
            with self.assertRaises(ValueError, msg=spec):
                xg.validate_spec(json.dumps(spec))
        with self.assertRaises(ValueError):
            xg.validate_spec("pas du json")

    def test_freeze_is_strictly_prospective_and_chained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            when = dt.datetime(2026, 10, 15, 18, 0, tzinfo=dt.timezone.utc)
            spec = json.dumps({"jeu": "alertes", "criteres": {"type": ["PUBLIC"], "circuit": ["ATP"]}})
            record = xg.freeze(root, spec, when)
            self.assertEqual(record["eligible_after_utc"], "2026-10-16")
            with self.assertRaises(ValueError):
                xg.freeze(root, spec, when)
            base = {"type": "PUBLIC", "circuit": "ATP", "clv_pin": 2.0, "pnl": 1.0}
            rows = [
                dict(base, _at="2026-10-15T17:00:00+00:00", date="2026-10-15"),   # avant le gel
                dict(base, _at="2026-10-15T20:00:00+00:00", date="2026-10-15"),   # jour du gel
                dict(base, _at="2026-10-16T09:00:00+00:00", date="2026-10-16"),   # compté
                dict(base, _at="2026-10-16T09:00:00+00:00", date="2026-10-16", circuit="WTA"),
            ]
            self.assertEqual(len(xg.prospective(record, rows)), 1)
            report = xg.evaluate(root, rows)
            self.assertEqual(report["candidates"][0]["n"], 1)
            self.assertEqual(report["candidates"][0]["state"], "en attente (n < 30)")
            path = root / xg.REGISTRY
            path.write_text(path.read_text().replace('"PUBLIC"', '"H17"'))
            with self.assertRaises(ValueError):
                xg.read_registry(root)


if __name__ == "__main__":
    unittest.main()
