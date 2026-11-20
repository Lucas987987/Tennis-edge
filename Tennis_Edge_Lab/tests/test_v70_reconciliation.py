"""V7.1 Réconciliation : suivi officiel = alertes EN DIRECT (verdicts_direct.json), reconstruction = contrôle."""
import csv
import gzip
import importlib.util
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

LAB = pathlib.Path(__file__).resolve().parents[1]
ROOT = LAB.parent
sys.path.insert(0, str(LAB))
import reconciliation as rc  # noqa: E402

HEADER = ["date", "tour", "steame", "opp", "mag_cote_pct", "mag_cote_pct_POSTHOC", "mag_proba_pts",
          "mag_proba_pts_POSTHOC", "pin_open", "pin_close", "lead_min", "entry_book", "entry", "soft_close",
          "clv_book_pct", "clv_vs_pin_pct", "steame_gagne", "pnl", "uid"]
HAS_VR = all((ROOT / "scripts" / f).is_file() for f in ("validation_report.py", "oddspapi_v5.py", "match_key.py"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    return module


def move(uid, player, opp, entry, pin, win="oui", lead=600, date=None):
    pnl = "" if win == "" else (round(entry - 1, 4) if win == "oui" else -1)
    return {"date": date or uid[:10], "tour": "ATP Test", "steame": player, "opp": opp, "mag_cote_pct": 6,
            "mag_cote_pct_POSTHOC": 6, "mag_proba_pts": 3, "mag_proba_pts_POSTHOC": 3, "pin_open": pin,
            "pin_close": pin, "lead_min": lead, "entry_book": "unibet", "entry": entry, "soft_close": entry,
            "clv_book_pct": 0, "clv_vs_pin_pct": 0, "steame_gagne": win, "pnl": pnl, "uid": uid}


def log(uid, player, opp, cote, side="home", envoye=True, doublon="", at=None, pin_open=None):
    return {"uid": uid, "detecte_le": at or uid[:10] + "T08:00:00", "signale_le": at or uid[:10] + "T08:00:05",
            "joueur": player, "adversaire": opp, "side": side, "tournoi": "ATP Test", "circuit": "ATP",
            "cote": cote, "book": "unibet", "pin_open": pin_open, "ampleur_pts": 3, "lead_min": 600,
            "commence": uid[:10] + "T12:00:00", "envoye": envoye, "doublon": doublon}


class FakeAjouts:
    """Résultats imposés par uid : (gagné, clôture côté, clôture adverse)."""

    def __init__(self, sd, results):
        self.sd, self.results = sd, results

    def pour(self, r):
        won, close, other = self.results.get(r["uid"], (None, None, None))
        book, cote = self.sd.books.normalize(r.get("book")), float(r["cote"])
        clv = self.sd.books.clv_pin_pct(book, cote, close, other) if close else None
        pnl = self.sd.books.pnl(book, cote, won) if won is not None else None
        return {"gagne": None if won is None else int(won), "pnl": pnl, "pin_close": close, "pin_close_adv": other,
                "clv_pin": clv, "source_resultat": "test", "denoue": won is not None}


@unittest.skipUnless(HAS_VR, "validation_report.py et ses imports absents")
class SyntheticReconciliation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(cls.tmp.name)
        (root / "scripts").mkdir()
        shutil.copy(ROOT / "scripts" / "validation_report.py", root / "scripts" / "validation_report.py")
        moves = [
            move("2026-10-01_alpha_one_beta_two", "Alpha One", "Beta Two", 2.5, 2.6),       # H13+H15 communes
            move("2026-10-02_gamma_g_delta_d", "Gamma G", "Delta D", 2.2, 2.3, win="non"),  # H13 non envoyée (échec)
            move("2026-10-03_echo_e_fox_f", "Echo E", "Fox F", 2.8, 2.9),                   # H13 reconstruction seule
            move("2026-10-03_golf_g_hotel_h", "Hotel H", "Golf G", 2.4, 2.5, win="non"),    # H13 autre côté
            move("2026-10-04_india_i_juliet_j", "India I", "Juliet J", 1.6, 1.5),           # H16 inexpliqué / H16B commune
            move("2026-09-25_kilo_k_lima_l", "Kilo K", "Lima L", 1.9, 1.7, win="non"),      # H16 avant canal
            move("2026-10-05_mike_m_november_n", "November N", "Mike M", 2.5, 2.6),         # direct seule : autre joueur
            move("2026-09-01_sierra_s_tango_t", "Sierra S", "Tango T", 2.5, 2.6),           # direct seule : hors gel
            move("2026-10-06_uniform_u_victor_v", "Uniform U", "Victor V", 3.4, 3.5),       # direct seule : prix
        ]
        with (root / "moves_detail_hist.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, HEADER)
            w.writeheader()
            w.writerows(moves)
        alpha = log("2026-10-01_alpha_one_beta_two", "Alpha One", "Beta Two", 2.5)
        logs = {
            "h13": [alpha, alpha,  # ligne dupliquée par la fusion « union »
                    log("2026-10-01_alpha_one_beta_two", "Alpha One", "Beta Two", 2.9, at="2026-10-01T09:00:00"),
                    log("2026-10-02_gamma_g_delta_d", "Gamma G", "Delta D", 2.2, envoye=False),
                    log("2026-10-03_golf_g_hotel_h", "Golf G", "Hotel H", 2.3),
                    log("2026-10-05_mike_m_november_n", "Mike M", "November N", 2.4),
                    log("2026-12-01_oscar_o_papa_p", "Oscar O", "Papa P", 2.4),
                    log("2026-09-20_quebec_q_romeo_r", "Quebec Q", "Romeo R", 2.4),
                    log("2026-09-01_sierra_s_tango_t", "Sierra S", "Tango T", 2.5, at="2026-09-07T08:00:00"),
                    log("2026-09-06_zz_a_zz_b", "Zz A", "Zz B", 2.5, at="2026-09-06T23:00:00"),  # jour du gel : exclu
                    log("2026-10-06_uniform_u_victor_v", "Uniform U", "Victor V", 2.9)],
            "h15": [log("2026-10-01_alpha_one_beta_two", "Alpha One", "Beta Two", 2.5, envoye=False, doublon="h13")],
            "h16": [log("2026-09-26_zulu_z_yankee_y", "Zulu Z", "Yankee Y", 1.5)],
            "h16b": [log("2026-10-04_india_i_juliet_j", "India I", "Juliet J", 1.6, pin_open=1.5)],
            "h17": [], "h18": [],
        }
        for name, rows in logs.items():
            (root / f"{name}_signal_log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        sd = load("tennis_edge_t_sd", ROOT / "scripts" / "suivi_direct.py")
        vr = sd.load_validation_report(ROOT)
        results = {"2026-10-01_alpha_one_beta_two": (True, 2.4, 1.6), "2026-10-02_gamma_g_delta_d": (False, 2.1, 1.8),
                   "2026-10-03_golf_g_hotel_h": (False, 2.2, 1.7), "2026-10-06_uniform_u_victor_v": (False, 2.8, 1.45),
                   "2026-10-04_india_i_juliet_j": (True, 1.5, 2.6)}
        cls.verdicts, table = sd.verdicts(root, vr=vr, ajouts=FakeAjouts(sd, results))
        (root / "verdicts_direct.json").write_text(json.dumps(cls.verdicts), encoding="utf-8")
        (root / "suivi_direct").mkdir()
        (root / "suivi_direct/resultats.json").write_text(json.dumps({"paris": table}), encoding="utf-8")
        cls.worker = {"schema_version": 1, "status": "ok", "fetched_at": "2026-10-16T09:09:00Z",
                      "hypotheses": [{"code": "H13", "gele_le": "2026-09-06",
                                      "out_of_sample": {"n": 132, "roi": 3.6, "clv_moyen": 0.8}}]}
        (root / "worker.json").write_text(json.dumps(cls.worker), encoding="utf-8")
        cls.doc, cls.rows = rc.build(root, root / "worker.json", check_validator=False)
        cls.vby = {h["code"]: h for h in cls.verdicts["hypotheses"]}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def reasons(self, code, sens):
        return {e["uid"]: e["raison"] for e in self.doc["hypotheses"][code]["ecarts"] if e["sens"] == sens}

    def test_counting_rules(self):
        o = self.vby["H13"]["out_of_sample"]
        # alpha (1re détection, doublon de fusion ignoré), gamma, golf, mike, oscar, quebec, sierra, uniform ;
        # la ligne du jour du gel est exclue (strictement après le gel).
        self.assertEqual(o["n_detectees"], 8)
        self.assertEqual((o["n_envoyees"], o["n_non_envoyees_autres"]), (7, 1))
        self.assertEqual(o["n"], 4)
        alpha = next(r for r in self.rows if r["type"] == "H13" and r["uid"].startswith("2026-10-01_alpha"))
        self.assertEqual(alpha["cote"], 2.5)  # première détection, pas la seconde à 2,9
        h15 = self.vby["H15"]["out_of_sample"]
        self.assertEqual((h15["n_detectees"], h15["n_doublons"], h15["n_envoyees"], h15["n"]), (1, 1, 0, 1))

    def test_reconstruction_only_reasons(self):
        r = self.reasons("H13", "reconstruction seule")
        self.assertEqual(r, {"2026-10-03_echo_e_fox_f": "apres_coup", "2026-10-03_golf_g_hotel_h": "cote_opposee_live",
                             "2026-10-05_mike_m_november_n": "cote_opposee_live"})
        h16 = self.reasons("H16", "reconstruction seule")
        self.assertEqual(h16["2026-09-25_kilo_k_lima_l"], "avant_canal")
        self.assertEqual(h16["2026-10-04_india_i_juliet_j"], "inexplique_inclusion")
        self.assertEqual(self.doc["hypotheses"]["H16"]["entonnoir"]["inexpliques"], 1)
        self.assertEqual(set(self.reasons("H14", "reconstruction seule").values()), {"sans_canal"})

    def test_live_only_reasons(self):
        r = self.reasons("H13", "direct seule")
        self.assertEqual(r, {"2026-10-05_mike_m_november_n": "cote_opposee_reco",
                             "2026-10-03_golf_g_hotel_h": "cote_opposee_reco",
                             "2026-12-01_oscar_o_papa_p": "pas_encore_reconstruit",
                             "2026-09-20_quebec_q_romeo_r": "absent_reconstruction",
                             "2026-09-01_sierra_s_tango_t": "hors_gel",
                             "2026-10-06_uniform_u_victor_v": "prix_different"})

    def test_lab_equals_verdicts_direct(self):
        for code, h in self.doc["hypotheses"].items():
            o = self.vby[code]["out_of_sample"]
            off, e = h["suivi_officiel"], h["entonnoir"]
            self.assertEqual((off["n"], off["roi"], off["pts"], off["clv_pin"], off["n_detectees"], off["n_envoyees"]),
                             (o.get("n", 0), o.get("roi"), o.get("ecart"), o.get("clv_pin_moyen"),
                              o["n_detectees"], o["n_envoyees"]), code)
            self.assertEqual(e["direct_detectees"], o["n_detectees"], code)
            self.assertEqual(e["communes"] + e["direct_seule"], e["direct_detectees"], code)
            self.assertEqual(e["communes"] + e["reconstruction_seule"], e["reconstruction_detectees"], code)
            m = h["mesures"]["suivi_officiel"]
            self.assertEqual(m["n"], o.get("n", 0), code)
            if m["n"]:
                self.assertAlmostEqual(m["roi"], o["roi"], delta=0.051)
        doc = rc.detections_doc(self.rows)
        for code, h in self.doc["hypotheses"].items():
            self.assertEqual(doc["summary"]["by_type"].get(code, 0), h["suivi_officiel"]["n_detectees"], code)
            self.assertEqual(doc["summary"]["settled_by_type"].get(code, 0), h["suivi_officiel"]["n"], code)

    def test_worker_numbers_copied_verbatim(self):
        w = self.doc["hypotheses"]["H13"]["worker"]
        self.assertEqual((w["n"], w["roi"], w["out_of_sample"]), (132, 3.6, {"n": 132, "roi": 3.6, "clv_moyen": 0.8}))
        self.assertIsNone(self.doc["hypotheses"]["H14"]["worker"])


@unittest.skipUnless((ROOT / "moves_detail_hist.csv").is_file() and HAS_VR, "données du dépôt absentes")
class RealData(unittest.TestCase):
    def test_reconstruction_control_equals_validation_report(self):
        watch = rc.validator_watch(ROOT)
        doc, _ = rc.build(ROOT, check_validator=False)
        for code in rc.OFFICIAL:
            k = doc["hypotheses"][code]["reconstruction"]
            self.assertIsNotNone(watch[code], code)
            self.assertEqual((k["n"], k["gagnes"]), (watch[code]["n"], watch[code]["k"]), code)


COMMITTED = LAB / "live" / "reconciliation_hypotheses.json"
CAPTURE = LAB / "live" / "worker_hypotheses_capture.json"
VERDICTS = ROOT / "verdicts_direct.json"


@unittest.skipUnless(COMMITTED.is_file(), "réconciliation pas encore publiée")
class CommittedJson(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(COMMITTED.read_text(encoding="utf-8"))

    @unittest.skipUnless(CAPTURE.is_file(), "capture Worker pas encore publiée")
    def test_worker_numbers_equal_committed_capture(self):
        expected = rc.worker_block(ROOT, CAPTURE)
        for code in rc.OFFICIAL:
            self.assertEqual(self.doc["hypotheses"][code]["worker"], expected["hypotheses"].get(code), code)

    @unittest.skipUnless(VERDICTS.is_file(), "verdicts_direct.json absent")
    def test_lab_equals_committed_verdicts_direct(self):
        verdicts = json.loads(VERDICTS.read_text(encoding="utf-8"))
        if self.doc["hypotheses"]["H13"]["suivi_officiel"].get("genere_le") != verdicts.get("genere_le"):
            self.skipTest("réconciliation calculée sur une autre version de verdicts_direct.json")
        for h in verdicts["hypotheses"]:
            o, off = h["out_of_sample"], self.doc["hypotheses"][h["code"]]["suivi_officiel"]
            self.assertEqual((off["n"], off["roi"], off["pts"], off["clv_pin"], off["n_detectees"]),
                             (o.get("n", 0), o.get("roi"), o.get("ecart"), o.get("clv_pin_moyen"), o["n_detectees"]),
                             h["code"])

    def test_explorer_detections_equal_official_n(self):
        path = LAB / "live" / "explorateur_detections.json.gz"
        if not path.is_file():
            self.skipTest("jeu Détections absent")
        summary = json.loads(gzip.decompress(path.read_bytes()))["summary"]
        for code, h in self.doc["hypotheses"].items():
            # Le jeu « Détections » et l'entonnoir viennent du MÊME passage sur le journal.
            self.assertEqual(summary["by_type"].get(code, 0), h["entonnoir"]["direct_detectees"], code)
            self.assertIs(h["reconstruction"]["egal_validation_report"], True, code)
            # Chiffres officiels : égaux quand ils portent sur le même état du journal (depuis le
            # 16/10, reconciliation.py recalcule les verdicts si verdicts_direct.json est en retard).
            if h["suivi_officiel"]["n_detectees"] == h["entonnoir"]["direct_detectees"]:
                self.assertEqual(summary.get("settled_by_type", {}).get(code, 0), h["suivi_officiel"]["n"], code)


if __name__ == "__main__":
    unittest.main()
