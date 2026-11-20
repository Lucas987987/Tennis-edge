"""Verdicts EN DIRECT (16/10/2026) : journal complet des h*_signal.py, canal H14, suivi_direct.

Les scripts de signal tournent pour de vrai (DRY_RUN=1, aucun réseau) sur des
courbes synthétiques, dans un répertoire temporaire.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CHAMPS = {"uid", "hypothese", "joueur", "adversaire", "side", "tournoi", "circuit", "detecte_le", "signale_le",
          "commence", "book", "cote", "cote_signal", "book_signal", "pin_open", "pin_decision", "pin_signal",
          "mag_cote_pct", "ampleur_pts", "lead_min", "ecart_pct", "envoye", "statut_envoi", "doublon",
          "doublon_ref", "regle", "regle_hash", "gele_le", "schema"}
ORDRE = ["h13", "h15", "h16", "h17", "h18", "h16b", "h14"]   # ordre de courbes_alertes.yml


def iso(t):
    return t.replace(microsecond=0).isoformat()


def courbe(uid, home, away, t0, t1, start, pin, soft, tour="ATP Test"):
    """pin = ((h0, a0), (h1, a1)) ; soft = (h1, a1) au moment du mouvement."""
    rows = [{"uid": uid, "book": "pinnacle", "commence_time": iso(start), "home": home, "away": away,
             "tournament": tour, "home_curve": [[iso(t0), pin[0][0]], [iso(t1), pin[1][0]]],
             "away_curve": [[iso(t0), pin[0][1]], [iso(t1), pin[1][1]]]},
            {"uid": uid, "book": "unibet", "commence_time": iso(start), "home": home, "away": away,
             "tournament": tour, "home_curve": [[iso(t0), soft[0]]], "away_curve": [[iso(t0), soft[1]]]}]
    return rows


class JournalComplet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        t0, t1, start = now - dt.timedelta(hours=3), now - dt.timedelta(hours=2), now + dt.timedelta(hours=12)
        lines = []
        # Favori : H16, H16-B, H17, H18 et H14 (Pinnacle 1,60 -> 1,45 : -9,4 % ; 14 h avant).
        lines += courbe("2099-01-01_fav_a_dog_b", "Fav A", "Dog B", t0, t1, start,
                        ((1.60, 2.40), (1.45, 2.75)), (1.62, 2.30))
        # Bande 2,00-3,00 et 2,40-3,10 : H13 puis H15 (doublon de H13) ; H14 aussi (-12 %).
        lines += courbe("2099-01-01_mid_c_mid_d", "Mid C", "Mid D", t0, t1, start,
                        ((2.50, 1.60), (2.20, 1.75)), (2.45, 1.55), tour="WTA Test")
        (d / "book_curves_live.jsonl").write_text("".join(json.dumps(r) + "\n" for r in lines), encoding="utf-8")
        env = dict(os.environ, DRY_RUN="1", CURVES="book_curves_live.jsonl", PYTHONDONTWRITEBYTECODE="1")
        env.pop("TELEGRAM_TOKEN", None)
        cls.out = {}
        for h in ORDRE:
            r = subprocess.run([sys.executable, str(SCRIPTS / f"{h}_signal.py")], cwd=d, env=env,
                               capture_output=True, text=True, timeout=120)
            cls.out[h] = r
        cls.logs = {h: [json.loads(l) for l in (d / f"{h}_signal_log.jsonl").read_text(encoding="utf-8").splitlines()]
                    if (d / f"{h}_signal_log.jsonl").is_file() else [] for h in ORDRE}
        # Second passage : l'anti-doublon ne doit RIEN rejournaliser.
        for h in ORDRE:
            subprocess.run([sys.executable, str(SCRIPTS / f"{h}_signal.py")], cwd=d, env=env,
                           capture_output=True, text=True, timeout=120)
        cls.logs2 = {h: (d / f"{h}_signal_log.jsonl").read_text(encoding="utf-8").count("\n")
                     if (d / f"{h}_signal_log.jsonl").is_file() else 0 for h in ORDRE}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_scripts_run_cleanly(self):
        for h, r in self.out.items():
            self.assertEqual(r.returncode, 0, f"{h}: {r.stderr[-800:]}")

    def test_every_detection_logged_with_decision_fields(self):
        attendu = {"h13": {"Mid C"}, "h15": {"Mid C"}, "h16": {"Fav A"}, "h16b": {"Fav A"}, "h17": {"Fav A"},
                   "h18": {"Fav A"}, "h14": {"Fav A", "Mid C"}}
        for h, joueurs in attendu.items():
            self.assertEqual({r["joueur"] for r in self.logs[h]}, joueurs, h)
            for r in self.logs[h]:
                self.assertEqual(CHAMPS - set(r), set(), f"{h}: champs manquants")
                self.assertEqual(r["schema"], 2)
                self.assertEqual(r["hypothese"], h.upper())
                self.assertEqual(r["side"], "home")
                self.assertFalse(r["envoye"])                  # DRY_RUN : jamais « envoyé »
                self.assertEqual(len(r["regle_hash"]), 12)

    def test_values_at_decision(self):
        fav = self.logs["h18"][0]
        self.assertEqual((fav["pin_open"], fav["pin_decision"], fav["cote"], fav["book"]), (1.6, 1.45, 1.62, "unibet"))
        self.assertAlmostEqual(fav["mag_cote_pct"], 9.38, places=2)
        self.assertAlmostEqual(fav["ecart_pct"], 1.25, places=2)
        self.assertEqual(fav["circuit"], "ATP")
        self.assertEqual(fav["statut_envoi"], "non tenté (DRY_RUN)")

    def test_doublons_logged_with_reference(self):
        h15 = self.logs["h15"][0]
        self.assertEqual((h15["doublon"], h15["statut_envoi"]), ("h13", "doublon"))
        self.assertEqual(h15["doublon_ref"]["canal"], "h13")
        self.assertEqual(h15["doublon_ref"]["cote"], 2.45)

    def test_h14_live_channel(self):
        h14 = {r["joueur"]: r for r in self.logs["h14"]}
        self.assertGreater(h14["Fav A"]["mag_cote_pct"], 5)
        self.assertTrue(480 <= h14["Fav A"]["lead_min"] <= 1440)
        self.assertEqual(h14["Fav A"]["gele_le"], "2026-10-02")
        # en DRY_RUN rien n'est envoyé : pas de doublon, statut « non tenté »
        self.assertEqual(h14["Mid C"]["doublon"], "")

    def test_no_double_logging_on_rerun(self):
        for h in ORDRE:
            self.assertEqual(self.logs2[h], len(self.logs[h]), h)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    return module


class SuiviDirect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sd = _load("tennis_edge_t_suivi_direct", SCRIPTS / "suivi_direct.py")
        cls.vr = cls.sd.load_validation_report(ROOT)

    def test_statistics_block(self):
        paris = [{"cote": 2.0, "book": "unibet", "gagne": 1, "pnl": 1.0, "clv_pin": 2.0, "jour": "2026-10-01", "lead_min": 120},
                 {"cote": 2.0, "book": "unibet", "gagne": 0, "pnl": -1.0, "clv_pin": -1.0, "jour": "2026-10-02", "lead_min": 60},
                 {"cote": 3.0, "book": "betfair-ex", "gagne": 1, "pnl": 1.9, "clv_pin": 4.0, "jour": "2026-10-03", "lead_min": 60}]
        b = self.sd.bloc(paris)
        self.assertEqual((b["n"], b["gains"]), (3, 2))
        seuil = 100 * (0.5 + 0.5 + 1 / 2.9) / 3                     # cote nette de commission (Betfair 5 %)
        self.assertAlmostEqual(b["seuil"], round(seuil, 1))
        self.assertAlmostEqual(b["roi"], round(100 * 1.9 / 3, 1))
        self.assertEqual(b["clv_pin_moyen"], round(5 / 3, 1))
        self.assertEqual(b["clv_moyen"], b["clv_pin_moyen"])
        self.assertEqual(b["periode"], "2026-10-01 -> 2026-10-03")

    def test_side_from_uid_only_when_unambiguous(self):
        f = self.sd.side_depuis_uid
        self.assertEqual(f("2026-10-01_jan_choinski_dan_evans", "Dan Evans"), "away")
        self.assertEqual(f("2026-10-01_jan_choinski_dan_evans", "Jan Choinski"), "home")
        self.assertIsNone(f("2026-10-01_jan_choinski_dan_evans", "Someone Else"))

    def test_journal_never_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            line = {"uid": "2026-10-10_a_a_b_b", "joueur": "A A", "adversaire": "B B", "side": "home",
                    "detecte_le": "2026-10-10T08:00:00", "signale_le": "2026-10-10T08:00:01",
                    "commence": "2026-10-10T12:00:00", "cote": 2.5, "book": "unibet", "envoye": True, "doublon": ""}
            text = json.dumps(line) + "\n"
            (d / "h13_signal_log.jsonl").write_text(text, encoding="utf-8")

            class Fake:
                def pour(self, r):
                    return {"gagne": 1, "pnl": 1.5, "pin_close": 2.3, "pin_close_adv": 1.7, "clv_pin": 1.0,
                            "source_resultat": "test", "denoue": True}
            doc, table = self.sd.verdicts(d, vr=self.vr, ajouts=Fake())
            self.assertEqual((d / "h13_signal_log.jsonl").read_text(encoding="utf-8"), text)
            h13 = next(h for h in doc["hypotheses"] if h["code"] == "H13")
            self.assertEqual((h13["out_of_sample"]["n_detectees"], h13["out_of_sample"]["n"]), (1, 1))
            self.assertEqual(set(table["H13|2026-10-10_a_a_b_b|home"]),
                             {"gagne", "pnl", "pin_close", "pin_close_adv", "clv_pin", "source_resultat"})
            # Écriture seulement si le contenu change (genere_le ignoré).
            self.assertTrue(self.sd.ecrire_si_change(d / "v.json", doc))
            doc2 = dict(doc, genere_le="2099-01-01T00:00:00Z")
            self.assertFalse(self.sd.ecrire_si_change(d / "v.json", doc2))


class GardeVerrouillage(unittest.TestCase):
    """Garde du 16/10/2026 : > 10 % de détections commencées sans résultat => ni verrou ni verdict."""

    @classmethod
    def setUpClass(cls):
        cls.sd = _load("tennis_edge_t_suivi_direct_g", SCRIPTS / "suivi_direct.py")

    def lignes(self, n_passees, n_futures):
        now = dt.datetime(2026, 10, 16, 12, tzinfo=dt.timezone.utc)
        rows = [{"commence": "2026-10-10T12:00:00"} for _ in range(n_passees)]
        rows += [{"commence": "2026-10-17T12:00:00Z"} for _ in range(n_futures)]
        return rows, now

    def test_threshold_and_future_matches(self):
        rows, now = self.lignes(100, 50)
        g = self.sd.garde(rows, 90, now)          # 10 % sans résultat : limite incluse
        self.assertEqual((g["n_commencees"], g["n_sans_resultat"], g["verrouillable"]), (100, 10, True))
        g = self.sd.garde(rows, 89, now)          # 11 % : en attente
        self.assertFalse(g["verrouillable"])
        self.assertEqual(g["statut"], "en attente de résultats (11,0 % sans résultat)")

    def test_pair_window(self):
        class Ex:
            @staticmethod
            def name_key(x):
                return x.lower().replace(" ", "")
        a = self.sd.Ajouts.__new__(self.sd.Ajouts)
        a.ex = Ex()
        pair = ("annb", "bobc")
        a.by_pair = {pair: [("2026-10-08", "annb"), ("2026-10-12", "bobc"), ("2026-10-20", "annb")]}
        start = dt.datetime(2026, 10, 10, 12, tzinfo=dt.timezone.utc)
        won, src = a.par_paire("Ann B", "Bob C", start)
        self.assertEqual((won, src), (False, "paire exacte (+2 j)"))      # premier >= jour du match
        a.by_pair = {pair: [("2026-10-09", "annb")]}
        self.assertEqual(a.par_paire("Ann B", "Bob C", start), (True, "paire exacte (-1 j)"))
        a.by_pair = {pair: [("2026-10-08", "annb"), ("2026-10-18", "annb")]}
        self.assertEqual(a.par_paire("Ann B", "Bob C", start), (None, None))  # hors [J-1 ; J+7]
        self.assertEqual(a.par_paire("Ann B", None, start), (None, None))     # jamais un seul nom

    def test_validation_report_never_locks_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            doc = {"genere_le": "2026-10-16T12:00:00Z", "hypotheses": [
                {"code": "H16", "out_of_sample": {"n": 150, "gains": 120, "taux": 80.0, "seuil": 70.0, "ecart": 10.0, "roi": 5.0, "n_detectees": 180,
                                                  "verrouillable": False,
                                                  "statut": "en attente de résultats (15,0 % sans résultat)"}},
                {"code": "H13", "out_of_sample": {"n": 150, "gains": 70, "taux": 46.7, "seuil": 42.0, "ecart": 4.7, "roi": 3.0, "n_detectees": 160,
                                                  "verrouillable": True, "statut": "verrouillable"}}]}
            (d / "verdicts_direct.json").write_text(json.dumps(doc), encoding="utf-8")
            code = (
                "import sys, json; sys.path.insert(0, %r)\n"
                "import validation_report as vr\n"
                "noms = {'H16': 'favori net (pin<1,80) (direct)', 'H13': 'ROI bande cote 2-3 (direct)'}\n"
                "ws = [(n, g, w) for n, g, w in vr.HYPOTHESES if n in noms.values()]\n"
                "vr.HYPOTHESES[:] = ws\n"
                "res = [(n, g, w()) for n, g, w in ws]\n"
                "vr.bilan_tests_multiples(res)\n"
                "print('GELES', json.dumps(sorted(json.load(open('verdicts_geles.json')))))\n"
            ) % str(SCRIPTS)
            r = subprocess.run([sys.executable, "-c", code], cwd=d, capture_output=True, text=True, timeout=300)
            self.assertEqual(r.returncode, 0, r.stderr[-1500:])
            self.assertIn('GELES ["ROI bande cote 2-3 (direct)"]', r.stdout)
            self.assertIn("en attente de résultats (15,0 % sans résultat) : verdict NI verrouillé NI déclaré", r.stdout)


@unittest.skipUnless((ROOT / "verdicts_direct.json").is_file(), "verdicts_direct.json pas encore publié")
class CommittedVerdicts(unittest.TestCase):
    def test_shape_compatible_with_worker_api(self):
        doc = json.loads((ROOT / "verdicts_direct.json").read_text(encoding="utf-8"))
        self.assertIsInstance(doc["genere_le"], str)
        codes = [h["code"] for h in doc["hypotheses"]]
        self.assertEqual(codes, ["H13", "H14", "H15", "H16", "H16B", "H17", "H18"])
        for h in doc["hypotheses"]:
            o = h["out_of_sample"]
            self.assertIsInstance(o["n"], int)
            for k in ("n_detectees", "n_envoyees", "n_denouees"):
                self.assertIn(k, o)
            self.assertLessEqual(o["n"], o["n_detectees"])
            self.assertIn("cible", h)


if __name__ == "__main__":
    unittest.main()
