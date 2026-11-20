"""Étape 4 stockage : historique des courbes -> R2, Releases -> R2, alertes
mensuelles, rapport V6.1 compressé, fenêtre chaude de closing_lines."""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r2_fakes import FakeS3, install, uninstall  # noqa: E402
import r2_io  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import alerts_store  # noqa: E402
import hist_r2  # noqa: E402

NOW = dt.datetime(2026, 10, 16, 12, 0, tzinfo=dt.timezone.utc)      # jeudi, S42


def gz(*lines):
    return gzip.compress("".join(l + "\n" for l in lines).encode(), mtime=0)


def git(*a):
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a],
                          check=True, capture_output=True, text=True).stdout


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.fake = FakeS3()
        install(self.fake, "double")

    def tearDown(self):
        os.chdir(self.cwd)
        uninstall()
        os.environ.pop("R2_HIST_MATERIALIZE", None)
        self.tmp.cleanup()


class FrozenRuleTests(unittest.TestCase):
    def test_current_week_and_grace_are_never_frozen(self):
        self.assertTrue(hist_r2.is_frozen("hist_book_2026-W41.jsonl.gz", NOW))
        self.assertTrue(hist_r2.is_frozen("hist_set1_2026-08.jsonl.gz", NOW))
        self.assertFalse(hist_r2.is_frozen("hist_book_2026-W42.jsonl.gz", NOW))
        self.assertFalse(hist_r2.is_frozen("hist_set2_2026-W42_2.jsonl", NOW))
        self.assertFalse(hist_r2.is_frozen("hist_book_2026-10.jsonl.gz", NOW))
        monday_early = dt.datetime(2026, 10, 19, 3, 0, tzinfo=dt.timezone.utc)   # S43, < 6 h
        self.assertFalse(hist_r2.is_frozen("hist_book_2026-W42.jsonl.gz", monday_early))
        self.assertTrue(hist_r2.is_frozen("hist_book_2026-W42.jsonl.gz",
                                          monday_early + dt.timedelta(hours=4)))
        self.assertFalse(hist_r2.is_frozen("autre.jsonl", NOW))


class DupTests(unittest.TestCase):
    def test_prefix_duplicate_is_reported_as_included(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp, "x.jsonl"), Path(tmp, "x.jsonl.gz")
            a.write_bytes(b"l1\n")
            b.write_bytes(gz("l1", "l2"))
            self.assertEqual(hist_r2.compare_dup(a, b), "inclus")
            b.write_bytes(gz("l1"))
            self.assertEqual(hist_r2.compare_dup(a, b), "identique")
            b.write_bytes(gz("autre"))
            self.assertEqual(hist_r2.compare_dup(a, b), "different")


class HistMigrationTests(Base):
    def setUp(self):
        super().setUp()
        git("init", "-q")
        os.makedirs("parts")
        self.files = {
            "hist_book_2026-W40.jsonl.gz": gz("a", "b"),
            "hist_book_2026-W41.jsonl.gz": gz("c"),
            "hist_book_2026-W42.jsonl.gz": gz("courante"),          # semaine en cours
            "hist_set1_2026-W37.jsonl": b"x\ny\n",                  # doublon identique
            "hist_set1_2026-W37.jsonl.gz": gz("x", "y"),
            "hist_set2_2026-W37.jsonl": b"autre\n",                 # doublon DIFFÉRENT
            "hist_set2_2026-W37.jsonl.gz": gz("z"),
        }
        for n, d in self.files.items():
            Path("parts", n).write_bytes(d)
        Path(".gitignore").write_text("*.tmp\n")
        git("add", "-A")
        git("commit", "-qm", "init")

    def test_inventory_is_read_only(self):
        rep = hist_r2.inventaire(now=NOW, report_path="inv.json")
        self.assertEqual(rep["dans_git"], 7)
        self.assertEqual(rep["figees"], 6)
        dup = {r["fichier"]: r.get("doublon_identique") for r in rep["fichiers"] if "doublon_de" in r}
        self.assertEqual(dup, {"hist_set1_2026-W37.jsonl": True, "hist_set2_2026-W37.jsonl": False})
        self.assertEqual(r2_io.OPS["A"], 1)           # un LIST, aucune écriture
        self.assertEqual(self.fake.count("PUT"), 0)

    def test_migrate_verify_materialize_and_rollback(self):
        self.assertEqual(hist_r2.migrer(now=NOW), 0)
        tracked = set(git("ls-files", "parts").split())
        self.assertEqual(tracked, {"parts/hist_book_2026-W42.jsonl.gz"})   # seule la courante reste
        man = json.loads(self.fake.raw("parts/hist/_manifest.json"))["files"]
        self.assertNotIn("hist_set1_2026-W37.jsonl", man)                  # couvert par son .gz
        self.assertIn("hist_set2_2026-W37.jsonl", man)                     # différent : gardé
        for n in man:
            self.assertEqual(self.fake.raw("parts/hist/" + n), self.files[n])
        block = hist_r2.read_block()
        self.assertEqual(len(block), 6)
        # Un `git add -A` ne peut plus les remettre dans git.
        git("add", "-A")
        status = dict(l.split("\t")[::-1] for l in git("diff", "--cached", "--name-status").splitlines())
        self.assertEqual(status["parts/hist_book_2026-W40.jsonl.gz"], "D")   # retiré, pas ré-ajouté
        self.assertEqual(hist_r2.verifier(complet=True), 0)
        # Relance : rien de plus à faire.
        self.assertEqual(hist_r2.migrer(now=NOW), 0)
        # Un checkout neuf n'a pas les figées : les lecteurs les rapatrient.
        for n in block:
            os.remove(os.path.join("parts", n))
        self.assertEqual(r2_io.materialize_hist(), {})                     # désactivé par défaut
        os.environ["R2_HIST_MATERIALIZE"] = "1"
        import oddspapi_v5
        lines = list(oddspapi_v5.iter_hist_lines("book"))
        self.assertEqual([l.strip() for l in lines], ["a", "b", "c", "courante"])
        # Retour arrière : tout revient dans git, à l'identique.
        self.assertEqual(hist_r2.annuler(), 0)
        self.assertEqual(hist_r2.read_block(), [])
        tracked = set(git("ls-files", "--cached", "parts").split())
        self.assertEqual(len(tracked), 7)
        for n, d in self.files.items():
            self.assertEqual(Path("parts", n).read_bytes(), d, n)

    def test_conflicting_r2_copy_keeps_the_file_in_git(self):
        self.fake.put_raw("parts/hist/hist_book_2026-W40.jsonl.gz", gz("AUTRE"))
        self.assertEqual(hist_r2.migrer(now=NOW), 1)
        self.assertIn("parts/hist_book_2026-W40.jsonl.gz", git("ls-files", "parts").split())

    def test_cache_dir_is_used_and_never_overwrites_checkout(self):
        hist_r2.migrer(now=NOW)
        cache = os.path.join(self.tmp.name, "cache")
        for n in hist_r2.read_block():
            os.remove(os.path.join("parts", n))
        hist_r2.pull(cache_dir=cache)                                      # remplit le cache
        self.assertTrue(os.path.exists(os.path.join(cache, "hist_book_2026-W40.jsonl.gz")))
        for n in hist_r2.read_block():
            if os.path.exists(os.path.join("parts", n)):
                os.remove(os.path.join("parts", n))
        Path("parts/hist_book_2026-W42.jsonl.gz").write_bytes(gz("courante", "ajout"))
        self.fake.calls.clear()
        hist_r2.pull(cache_dir=cache)
        # Au plus le manifeste : aucune partition retéléchargée (cache).
        self.assertEqual([k for v, k in self.fake.calls if v == "GET" and not k.endswith("_manifest.json")], [])
        self.assertEqual(Path("parts/hist_book_2026-W42.jsonl.gz").read_bytes(),
                         gz("courante", "ajout"))


class TicksReleasesTests(Base):
    def setUp(self):
        super().setUp()
        os.makedirs("parts")
        import ticks_releases_r2 as tr
        self.tr = importlib.reload(tr)
        self.assets = {"pm_ticks_2026-08-19.jsonl.gz": gz("t1", "t2"),
                       "kx_ticks_2026-08-20.jsonl.gz": gz("k1")}
        Path("parts/ARCHIVE_INDEX.json").write_text(json.dumps({"archives": [
            {"fichier": "pm_ticks_2026-08-19.jsonl.gz", "release": "ticks-2026-08"},
            {"fichier": "kx_ticks_2026-08-20.jsonl.gz", "release": "ticks-2026-08"},
            {"fichier": "pm_ticks_2026-09-29.jsonl.gz", "release": "ticks-2026-09"},
            {"fichier": "pm_ticks_2026-10-07.jsonl.gz", "release": "r2:parts/ticks/pm_ticks_2026-10-07.jsonl.gz"},
        ]}))

    def fake_gh(self, *args):
        if args[:2] == ("release", "list"):
            return 0, "ticks-2026-08\n"
        if args[:2] == ("release", "view"):
            return 0, "".join(f"{n}\t{len(d)}\n" for n, d in self.assets.items())
        if args[:2] == ("release", "download"):
            name, folder = args[args.index("-p") + 1], args[args.index("--dir") + 1]
            Path(folder, name).write_bytes(self.assets[name])
            return 0, ""
        return 1, "?"

    def test_inventory_lists_missing_releases_then_copy_verifies_and_is_resumable(self):
        with mock.patch.object(self.tr, "gh", side_effect=self.fake_gh):
            rep = self.tr.inventaire(report_path=None)
            self.assertEqual(rep["releases_absentes"], ["ticks-2026-09"])
            self.assertEqual(rep["etats"]["deja_r2"], 1)
            self.assertEqual(self.tr.copier(max_files=1), 0)
            self.assertEqual(self.tr.copier(max_files=10), 0)
            self.assertEqual(self.tr.copier(max_files=10), 0)        # rien à refaire
        for n, d in self.assets.items():
            self.assertEqual(self.fake.raw("parts/ticks/" + n), d)
        state = json.load(open("parts/RELEASES_R2_STATE.json"))["fichiers"]
        self.assertEqual({v["etat"] for v in state.values()}, {"copie"})
        man = json.loads(self.fake.raw("parts/ticks/_manifest_pm.json"))["files"]
        self.assertIn("pm_ticks_2026-08-19.jsonl.gz", man)
        self.assertEqual(self.fake.count("DELETE"), 0)

    def test_existing_more_complete_r2_copy_is_never_overwritten(self):
        longer = self.assets["pm_ticks_2026-08-19.jsonl.gz"] + gz("t3")
        self.fake.put_raw("parts/ticks/pm_ticks_2026-08-19.jsonl.gz", longer)
        with mock.patch.object(self.tr, "gh", side_effect=self.fake_gh):
            self.tr.copier(max_files=10)
        self.assertEqual(self.fake.raw("parts/ticks/pm_ticks_2026-08-19.jsonl.gz"), longer)
        state = json.load(open("parts/RELEASES_R2_STATE.json"))["fichiers"]
        self.assertEqual(state["pm_ticks_2026-08-19.jsonl.gz"]["etat"], "r2_plus_complet")


class AlertsStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        rows = [{"logged_at": "2026-09-30T23:59:00", "uid": "a"},
                {"logged_at": "2026-10-01T00:01:00", "uid": "b"},
                {"logged_at": "2026-09-30T22:00:00", "uid": "c_en_retard"},
                {"uid": "sans_date"},
                {"logged_at": "2026-10-02T10:00:00", "uid": "d"}]
        Path("odds_alerts_log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_split_reader_equivalence_idempotence_rollback(self):
        before = list(alerts_store.iter_lines("odds_alerts_log.jsonl"))
        self.assertTrue(alerts_store.migrate(".", verbose=False)["ok"])
        self.assertEqual(list(alerts_store.iter_lines("odds_alerts_log.jsonl")), before)
        self.assertEqual(alerts_store.migrate(".", verbose=False)["status"], "deja_migre")
        with open(alerts_store.append_path("."), "a") as f:          # écrivain : mois courant
            f.write(json.dumps({"logged_at": "2026-10-16T10:00:00", "uid": "e"}) + "\n")
        self.assertEqual(len(list(alerts_store.iter_records("odds_alerts_log.jsonl"))), 6)
        self.assertTrue(alerts_store.remove_legacy("."))
        self.assertTrue(alerts_store.restore("."))
        self.assertFalse(os.path.isdir("odds_alerts_log"))
        self.assertEqual(open("odds_alerts_log.jsonl").read().count("\n"), 6)

    def test_real_readers_and_lab(self):
        import decay_study  # noqa: F401  (import sans effet de bord)
        import alert_continuation
        importlib.reload(alert_continuation)
        alerts_store.migrate(".", verbose=False)
        alerts_store.remove_legacy(".")
        recs = list(alerts_store.iter_records(alert_continuation.ALERTS_LOG))
        self.assertEqual([r["uid"] for r in recs], ["a", "b", "c_en_retard", "sans_date", "d"])
        spec = importlib.util.spec_from_file_location(
            "clv_source", REPO / "Tennis_Edge_Lab" / "clv_source.py")
        lab = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lab)
        with lab.open_text(Path(self.tmp.name) / "odds_alerts_log.jsonl") as s:
            self.assertEqual(len(list(s)), 5)


class V61ReportTests(unittest.TestCase):
    def test_written_compressed_published_both_ways(self):
        sys.path.insert(0, str(REPO / "Tennis_Edge_Lab"))
        import candidate_watch_v61 as watch
        import publish_guard
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp, "Tennis_Edge_Lab/live")
            live.mkdir(parents=True)
            plain = live / "candidate_watch_v61_prospective.json"
            plain.write_text("{}")
            report = {"generated_at": "2026-10-16T10:00:00Z", "total_frozen": 1, "candidates": [1]}
            watch._write_report(plain, dict(report))
            self.assertFalse(plain.exists())
            gzf = live / "candidate_watch_v61_prospective.json.gz"
            first = gzf.read_bytes()
            self.assertEqual(watch.read_report(plain)["total_frozen"], 1)
            # Même contenu, autre horodatage : fichier inchangé (pas de commit).
            watch._write_report(plain, dict(report, generated_at="2026-10-17T10:00:00Z"))
            self.assertEqual(gzf.read_bytes(), first)
            site = Path(tmp, "_site")
            publish_guard.stage(tmp, site, "", dt.datetime(2026, 10, 16, 12, tzinfo=dt.timezone.utc))
            pub = site / "Tennis_Edge_Lab/live/candidate_watch_v61_prospective.json"
            self.assertEqual(json.loads(pub.read_text())["total_frozen"], 1)
            self.assertEqual(json.loads(gzip.decompress(Path(str(pub) + ".gz").read_bytes())),
                             json.loads(pub.read_text()))
            # Les autres rapports gardent l'ancien format.
            other = live / "candidate_watch_v62_prospective.json"
            watch._write_report(other, {"generated_at": "x", "candidates": []})
            self.assertTrue(other.exists())


class ClosingWindowTests(unittest.TestCase):
    def test_hot_window_is_two_days_and_unsettled_stay_hot(self):
        import closing_store as cs
        now = dt.datetime(2026, 10, 16, 12, 0)
        def e(days, **kw):
            ct = (now - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
            return {"commence_time": ct, "date": ct[:10], **kw}
        settled = {"clv_hist_done": True, "clv_home": {"c": 1}}
        self.assertEqual(cs.HOT_DAYS, 2)
        self.assertTrue(cs.is_hot(e(1.5, **settled), now))
        self.assertFalse(cs.is_hot(e(2.5, **settled), now))
        self.assertTrue(cs.is_hot(e(10, clv_hist_done=False), now))


if __name__ == "__main__":
    unittest.main()
