"""V7.3 « Base des matchs » : lectures rejouées dans le temps (parité avec « Matchs en direct »,
aucune donnée du futur), cohérence CLV → gains, fiabilité de la clôture, registre mensuel."""
import datetime as dt
import gzip
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

LAB = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))


def _load(name):
    spec = importlib.util.spec_from_file_location("t73_" + name, LAB / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


lp = _load("lectures_profils")
dp = lp.dp
UTC = dt.timezone.utc


def fixture_rows():
    """Lignes du jeu de parité V7.2, datées pour que chacune soit « connue » de la suivante."""
    fx = dp.fixture()
    t0 = dt.datetime(2026, 6, 1, tzinfo=UTC)
    rows = []
    for i, r in enumerate(fx["rows"]):
        r = dict(r)
        r["_start"] = t0 + dt.timedelta(hours=i)
        rows.append(r)
    return fx, rows


class Parite(unittest.TestCase):
    def test_meme_lecture_que_matchs_en_direct(self):
        fx, rows = fixture_rows()
        for p in fx["profiles"]:
            same_h = [r for r in rows if r["horizon"] == p["horizon"]]
            H = lp._Horizon(same_h)
            got = lp.lecture(H, len(same_h), p)
            idx, relaxed, crit, ok = dp.similar(rows, p)
            s = dp.stats(rows, idx, dp.baseline(rows, crit))
            self.assertEqual(got["n"], len(idx))
            self.assertEqual(got["relaches"], len(relaxed))
            self.assertEqual(got["ok"], ok)
            self.assertAlmostEqual(got["base"], s["base"], places=9)
            if s["exces"]["mean"] is not None:
                self.assertAlmostEqual(got["exces"], s["exces"]["mean"], places=9)
                self.assertAlmostEqual(got["exces_ci"][0], s["exces"]["ci"][0], places=9)
            self.assertEqual(got["verdict"], dp.verdict(s, lp.ALPHA))


def row(start, horizon="6h", cote=2.0, clv=0.0, gagne=1, date=None, **kw):
    lead = dict(dp.HORIZONS)[horizon]
    r = {"horizon": horizon, "circuit": "ATP", "surface": "Hard", "cote_pin": cote, "move_pin_pct": 1.0,
         "ecart_jouable_pct": -1.0, "alerte_avant": "aucune", "clv_pinnacle": clv, "gagne": gagne,
         "pnl_jouable": (cote - 1) if gagne else -1.0, "pnl_pinnacle": (cote - 1) if gagne else -1.0,
         "date": date or start.date().isoformat(), "_uid": f"u{start.isoformat()}", "joueur": "A",
         "decision_ts": (start - dt.timedelta(minutes=lead)).isoformat(timespec="minutes"),
         "cloture_pin": cote}
    r.update(kw)
    return r


class PointDansLeTemps(unittest.TestCase):
    def test_le_futur_ne_change_jamais_une_lecture(self):
        t0 = dt.datetime(2026, 7, 1, 12, tzinfo=UTC)
        passe = [row(t0 + dt.timedelta(hours=6 * i), clv=-1.0 + (i % 3)) for i in range(60)]
        cible = row(t0 + dt.timedelta(days=20))
        avant = lp.compute(passe + [cible])[-1]
        futur = [row(t0 + dt.timedelta(days=21, hours=i), clv=50.0) for i in range(80)]
        apres = lp.compute(passe + [cible] + futur)[len(passe)]
        self.assertEqual(avant, apres)

    def test_un_match_trop_recent_n_est_pas_connu(self):
        t0 = dt.datetime(2026, 7, 1, 12, tzinfo=UTC)
        cible = row(t0 + dt.timedelta(days=10))
        decision = lp._ts(cible["decision_ts"])
        # commencé 3 h avant la décision : résultat pas encore sûr -> exclu
        recent = row(decision - dt.timedelta(hours=3))
        out = lp.compute([recent, cible])
        self.assertEqual(out[1]["n"], 0)


class Coherence(unittest.TestCase):
    def test_coherent_quand_les_gains_suivent_la_clv(self):
        items = [(2.0, 0.0, 1.0 if i % 2 else -1.0) for i in range(200)]
        c = lp.coherence(items)
        self.assertAlmostEqual(c["roi_attendu"], 0.0)
        self.assertAlmostEqual(c["roi_reel"], 0.0)
        self.assertEqual(c["etat"], "cohérent")

    def test_le_cas_du_tipster(self):
        # CLV +2 % mais 40 % de victoires à cote 2,0 : le bankroll fond.
        items = [(2.0, 2.0, 1.0 if i % 5 < 2 else -1.0) for i in range(1000)]
        c = lp.coherence(items)
        self.assertLess(c["z"], -2)
        self.assertEqual(c["etat"], "la CLV ne se transforme pas en gains")

    def test_peu_de_paris(self):
        self.assertEqual(lp.coherence([(2.0, 1.0, 1.0)] * 10)["etat"], "trop peu de paris")
        self.assertEqual(lp.coherence([])["n"], 0)


class Fiabilite(unittest.TestCase):
    def test_un_cote_par_match_le_favori(self):
        t0 = dt.datetime(2026, 7, 1, 12, tzinfo=UTC)
        rows = []
        for i in range(40):
            s = t0 + dt.timedelta(hours=i)
            fav = row(s, cote=1.5, clv=0.0, gagne=1, joueur="F")
            out = row(s, cote=2.8, clv=0.0, gagne=0, joueur="O")
            out["_uid"] = fav["_uid"]
            rows += [fav, out]
        f = lp.fiabilite(rows)
        self.assertEqual(f["cotes_jugees"], 40)
        g = f["par_circuit"][0]
        self.assertAlmostEqual(g["proba_juste"], 1 / 1.5)
        self.assertEqual(g["victoires"], 1.0)


class Registre(unittest.TestCase):
    def test_registre_mensuel_et_reecriture_seulement_si_change(self):
        rm = _load("registre_matchs")
        start = dt.datetime(2026, 9, 3, 15, tzinfo=UTC)

        def pt(h, o):
            return (start - dt.timedelta(hours=h), o, None)

        def anchors(points):
            return {"open": points[0], "close": points[-1],
                    "horizons": {"24h": points[0], "6h": points[1], "1h": points[2], "10m": points[3]}}
        pin = {"start": start, "home": "Alpha Un", "away": "Beta Deux", "tournament": "ATP Metz",
               "curves": {"home": anchors([pt(30, 1.8), pt(6, 1.75), pt(1, 1.7), pt(.2, 1.68)]),
                          "away": anchors([pt(30, 2.1), pt(6, 2.15), pt(1, 2.2), pt(.2, 2.25)])}}
        other = {**pin, "curves": {"home": anchors([pt(30, 1.85), pt(6, 1.8), pt(1, 1.75), pt(.2, 1.72)]),
                                   "away": anchors([pt(30, 2.0), pt(6, 2.05), pt(1, 2.1), pt(.2, 2.12)])}}

        class Surf:
            def lookup(self, t):
                return ("Hard", "test")
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            sink = {"records": {("m1", "pinnacle"): pin, ("m1", "unibet"): other},
                    "series": {"m1": {"home": [(start - dt.timedelta(hours=h), o) for h, o in ((30, 1.8), (6, 1.75), (1, 1.7))],
                                      "away": []}},
                    "rows": [row(start, cote=1.75, joueur="Alpha Un", _uid="m1")],
                    "results": {"m1": {"match": "home"}}, "surfaces": Surf(), "pair_results": None, "root": root}
            rm.run(sink)
            idx = json.loads((root / rm.OUT_DIR / "index.json").read_text())
            self.assertEqual([m["mois"] for m in idx["mois"]], ["2026-09"])
            path = root / rm.OUT_DIR / "registre_2026-09.json.gz"
            doc = json.loads(gzip.decompress(path.read_bytes()))
            m = doc["matchs"][0]
            self.assertEqual(m["joueurs"], ["Alpha Un", "Beta Deux"])
            self.assertEqual(m["vainqueur"], 0)
            self.assertEqual(doc["books"][m["cotes"][0][0]]["nom"], "pinnacle")
            self.assertEqual(m["cotes"][0][1][0], [1800, 1.8])          # ouverture : 30 h avant
            self.assertEqual(len(m["pinnacle"][0]), 3)
            self.assertEqual(m["horizons"][0][0], 0)                      # côté du joueur
            self.assertIn("lecture_verdict", doc["colonnes_horizons"])
            before = path.read_bytes()
            ch, _ = rm.write_month(root, "2026-09", doc["matchs"], [b["nom"] for b in doc["books"]], "autre date")
            self.assertFalse(ch)
            self.assertEqual(path.read_bytes(), before)
            ev = json.loads((root / rm.OUT_EVAL).read_text())
            self.assertIn("coherence_matchs", ev)

    def test_match_connu_seulement_par_ses_alertes(self):
        rm = _load("registre_matchs")
        als = [{"type": "H13", "joueur": "Lorenzo Rottoli", "at": "2026-09-07T01:15:41", "book": "betsson",
                "cote": 2.6, "ampleur_pts": 2.57, "envoyee": True, "gagne": 0, "pnl": -1.0, "clv_pin": -5.5,
                "tournoi": "ATP Challenger Genoa", "circuit": "Challenger", "surface": None, "delai_min": 474}]
        m = rm.alert_only("2026-09-07_valerio_aboian_lorenzo_rottoli", als)
        self.assertEqual(m["joueurs"], ["Valerio Aboian", "Lorenzo Rottoli"])
        self.assertEqual(m["vainqueur"], 0)
        self.assertTrue(m["sans_courbe"])
        self.assertLessEqual(abs(m["alertes"][0][2] - 474), 1)


if __name__ == "__main__":
    unittest.main()
