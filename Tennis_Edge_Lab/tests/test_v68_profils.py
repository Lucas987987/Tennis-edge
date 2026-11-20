"""V6.8 Profils : test d'hétérogénéité, Holm, phrases prudentes, variantes gelables."""
import datetime as dt
import json
import pathlib
import random
import sys
import tempfile
import unittest

LAB = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))
import explorer_gel  # noqa: E402
import profils  # noqa: E402


def make_rows(effect_by_circuit, roi_by_circuit=None, n_days=40, per_day=2, seed=1, halves_flip=False):
    rng = random.Random(seed)
    rows = []
    start = dt.date(2026, 6, 1)
    for d in range(n_days):
        date = (start + dt.timedelta(days=d)).isoformat()
        for circuit, effect in effect_by_circuit.items():
            if halves_flip and d < n_days // 2:
                effect = -effect
            for _ in range(per_day):
                pnl = (roi_by_circuit or {}).get(circuit)
                rows.append({"date": date, "type": "H13", "circuit": circuit, "clv_pin": effect + rng.gauss(0, 2),
                             "pnl": (pnl if pnl is not None else rng.choice([1.0, -1.0])),
                             "surface": "Hard", "tranche_cote": "2,00–2,50", "cote_pinnacle": "outsider",
                             "tranche_delai": "3–8 h", "tranche_ampleur": "2–3 pts", "famille_book": "autres jouables",
                             "pin_move_avant": "sans courbe"})
    return rows


def phrases(doc, subject="H13", source="alertes envoyées", field="circuit"):
    card = next(c for c in doc["sujets"] if c["sujet"] == subject and c["source"] == source)
    crit = next(c for c in card["criteres"] if c["critere"] == field)
    return crit, crit["phrases"]


class StatsTests(unittest.TestCase):
    def test_chi2_and_heterogeneity(self):
        self.assertAlmostEqual(profils.chi2_sf(3.841459, 1), 0.05, places=4)
        self.assertAlmostEqual(profils.chi2_sf(5.991465, 2), 0.05, places=4)
        effect = profils.analyse_criterion(make_rows({"Challenger": -3, "ATP": 0, "WTA": 0}), "circuit")
        self.assertLess(effect["p"], 1e-6)
        null = profils.analyse_criterion(make_rows({"Challenger": 0, "ATP": 0, "WTA": 0}, seed=7), "circuit")
        self.assertGreater(null["p"], 0.05)

    def test_rare_levels_are_merged(self):
        rows = make_rows({"Challenger": 0, "ATP": 0}) + make_rows({"WTA": 0}, n_days=3, per_day=1)
        res = profils.analyse_criterion(rows, "circuit")
        self.assertNotIn("WTA", [lv["valeur"] for lv in res["levels"]])


class SentenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, rows):
        return profils.build(self.root, explorer_rows={"H13": rows}, official_rows={})

    def test_proven_gap_with_valid_variant(self):
        doc = self.build(make_rows({"Challenger": -3, "ATP": 0.5, "WTA": 0.5}))
        crit, items = phrases(doc)
        proven = [p for p in items if p["force"] == "prouve"]
        self.assertTrue(proven)
        self.assertTrue(any("Challenger" in p["texte"] and "moins bonne" in p["texte"] for p in proven))
        variant = next(p["variante"] for p in proven if p["niveau"] == "Challenger")
        self.assertEqual(variant["criteres"], {"type": ["H13"], "circuit": ["ATP", "WTA"]})
        explorer_gel.validate_spec(json.dumps(variant))       # format accepté par le gel
        self.assertEqual(doc["k_tests"], len([c for s in doc["sujets"] for c in s["criteres"]]))
        self.assertIsNotNone(crit["p_holm"])

    def test_roi_only_difference_is_never_proven(self):
        rows = make_rows({"Challenger": 0, "ATP": 0}, roi_by_circuit={"Challenger": -1.0, "ATP": 1.5}, seed=3)
        _, items = phrases(self.build(rows))
        self.assertTrue(all(p["force"] == "aucune" for p in items))
        self.assertIn("probablement du hasard", items[0]["texte"])

    def test_effect_in_one_half_only_is_not_proven(self):
        rows = make_rows({"Challenger": -3, "ATP": 0}, halves_flip=True)
        _, items = phrases(self.build(rows))
        self.assertFalse(any(p["force"] == "prouve" for p in items))

    def test_holm_counts_all_tests(self):
        rows = make_rows({"Challenger": -3, "ATP": 0.5, "WTA": 0.5})
        doc = profils.build(self.root, explorer_rows={"H13": rows, "PUBLIC": rows, "MOUVEMENT": rows},
                            official_rows={"H16": rows})
        tests = [c for s in doc["sujets"] for c in s["criteres"]]
        self.assertEqual(doc["k_tests"], len(tests))
        self.assertGreaterEqual(doc["k_tests"], 4)
        self.assertTrue(all(c["p_holm"] >= c["p"] for c in tests))


if __name__ == "__main__":
    unittest.main()
