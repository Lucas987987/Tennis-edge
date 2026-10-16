"""Registres de marchés en ajout seul : équivalence, collecte, idempotence, retour."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import market_registry as mr  # noqa: E402


def pm(i, liq=10.0, **kw):
    m = {"market_id": str(i), "question": f"A{i} vs B{i}", "token_ids": [f"t{i}a", f"t{i}b"],
         "start_time": "2026-10-16T10:00:00Z", "liquidity": liq, "volume": 1.0,
         "discovered_at": "2026-10-16T09:00:00Z"}
    m.update(kw)
    return m


def kx(t, **kw):
    m = {"ticker": t, "event_ticker": "E", "local_uid": "u", "home": "A", "away": "B"}
    m.update(kw)
    return m


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.pm0 = [pm(i) for i in range(5)]
        self.kx0 = [kx(f"K{i}") for i in range(4)]
        for name, ms in (("polymarket_markets.json", self.pm0), ("kalshi_markets.json", self.kx0)):
            with open(os.path.join(self.root, name), "w") as f:
                json.dump({"updated_at": "2026-10-16T09:00:00Z", "count": len(ms), "actifs": 2,
                           "markets": ms}, f)

    def tearDown(self):
        self.tmp.cleanup()

    def test_before_migration_nothing_changes(self):
        self.assertFalse(mr.active(self.root))
        self.assertEqual(mr.load("polymarket", self.root), self.pm0)
        mr.save("polymarket", [pm(9)], self.root)
        data = json.load(open(os.path.join(self.root, "polymarket_markets.json")))
        self.assertEqual([m["market_id"] for m in data["markets"]], ["0", "1", "2", "3", "4", "9"])
        self.assertFalse(os.path.exists(mr.reg_dir(self.root)))

    def test_migration_is_equivalent_and_idempotent(self):
        res = mr.migrer(self.root, verbose=False)
        self.assertTrue(res["ok"])
        self.assertEqual(mr.load("polymarket", self.root), self.pm0)
        self.assertEqual(mr.load("kalshi", self.root), self.kx0)
        res2 = mr.migrer(self.root, verbose=False)
        self.assertEqual(res2["migration"]["polymarket"]["ajoutees"], 0)

    def test_run_appends_only_new_or_changed_markets(self):
        mr.migrer(self.root, verbose=False)
        before = {p: open(p, "rb").read() for p in mr.files("polymarket", self.root)}
        # Run 1 : volatils changés seulement -> aucune ligne.
        rep = mr.save("polymarket", [pm(1, liq=999.0), pm(2, liq=5.0)], self.root,
                      now_iso="2026-10-16T12:00:00.000Z")
        self.assertEqual(rep["nouvelles_lignes"], 0)
        self.assertEqual({p: open(p, "rb").read() for p in mr.files("polymarket", self.root)}, before)
        # … mais le run voit les valeurs fraîches (cache hors git).
        self.assertEqual(mr.load("polymarket", self.root)[1]["liquidity"], 999.0)
        # Run 2 : un nouveau marché + un horaire changé -> 2 lignes, fichier du jour.
        rep = mr.save("polymarket", [pm(7), pm(3, start_time="2026-10-17T10:00:00Z")], self.root,
                      now_iso="2026-10-16T12:20:00.000Z")
        self.assertEqual(rep["nouvelles_lignes"], 2)
        ids = [m["market_id"] for m in mr.load("polymarket", self.root)]
        self.assertEqual(ids, ["0", "1", "2", "3", "4", "7"])       # ordre de 1re apparition
        self.assertEqual(mr.load("polymarket", self.root)[3]["start_time"], "2026-10-17T10:00:00Z")
        self.assertTrue(os.path.exists(os.path.join(mr.reg_dir(self.root),
                                                    "polymarket_2026-10-16.jsonl")))
        # Le cache volatil n'est pas un fichier de registre (et il est ignoré par git).
        self.assertNotIn(".volatil_polymarket.json",
                         [os.path.basename(p) for p in mr.files("polymarket", self.root)])
        self.assertIn("registres_marches/.volatil_*", (REPO / ".gitignore").read_text())
        # Vérification toujours verte : le registre a une version plus récente, c'est normal.
        self.assertTrue(mr.verifier(self.root, verbose=False)["ok"])

    def test_late_legacy_write_is_caught_up_by_migrer(self):
        mr.migrer(self.root, verbose=False)
        path = os.path.join(self.root, "kalshi_markets.json")
        data = json.load(open(path))
        data["markets"].append(kx("K_TARD"))                  # vieux collecteur passé après
        json.dump(data, open(path, "w"))
        self.assertFalse(mr.verifier(self.root, verbose=False)["ok"])
        self.assertTrue(mr.migrer(self.root, verbose=False)["ok"])
        self.assertEqual(mr.load("kalshi", self.root)[-1]["ticker"], "K_TARD")

    def test_supprimer_ancien_then_annuler(self):
        mr.migrer(self.root, verbose=False)
        mr.save("kalshi", [kx("K9")], self.root, now_iso="2026-10-16T12:00:00.000Z")
        self.assertTrue(mr.supprimer_ancien(self.root))
        self.assertFalse(os.path.exists(os.path.join(self.root, "kalshi_markets.json")))
        expected = mr.load("kalshi", self.root)
        self.assertTrue(mr.annuler(self.root))
        self.assertFalse(mr.active(self.root))
        data = json.load(open(os.path.join(self.root, "kalshi_markets.json")))
        self.assertEqual(data["markets"], expected)

    def test_collectors_use_the_registry_after_migration(self):
        mr.migrer(self.root, verbose=False)
        cwd = os.getcwd()
        os.chdir(self.root)
        try:
            import importlib
            import kalshi_collector
            importlib.reload(kalshi_collector)
            kalshi_collector.sauver_registre([kx("K_NEW")])
            self.assertEqual(mr.load("kalshi", ".")[-1]["ticker"], "K_NEW")
        finally:
            os.chdir(cwd)


class PolymarketCollectorTests(unittest.TestCase):
    def test_save_and_load_markets_go_through_the_registry(self):
        try:
            import polymarket_collector_scripts as pcs
        except ImportError as exc:                       # websocket-client absent en local
            self.skipTest(f"dépendance absente : {exc}")
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "polymarket_markets.json"
            path.write_text(json.dumps({"markets": [pm(1)]}))
            with mock.patch.object(pcs, "MARKETS_FILE", path):
                mr.migrer(tmp, verbose=False)
                pcs.save_markets([pm(2)])
                self.assertEqual([m["market_id"] for m in pcs.load_markets()], ["1", "2"])
                self.assertEqual(json.loads(path.read_text())["markets"], [pm(1)])  # plus réécrit


@unittest.skipUnless((REPO / "polymarket_markets.json").is_file()
                     and (REPO / "kalshi_markets.json").is_file()
                     and not (REPO / mr.DIRNAME).is_dir(), "fichiers réels absents ou déjà migrés")
class RealFilesTests(unittest.TestCase):
    def test_real_files_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            for n in ("polymarket_markets.json", "kalshi_markets.json"):
                shutil.copy(REPO / n, tmp)
            old = {p: json.load(open(os.path.join(tmp, s["legacy"])))["markets"]
                   for p, s in mr.PROVIDERS.items()}
            self.assertTrue(mr.migrer(tmp, verbose=False)["ok"])
            for p in mr.PROVIDERS:
                self.assertEqual(mr.load(p, tmp), old[p])


if __name__ == "__main__":
    unittest.main()
