"""Tests de r2_parts : envoi groupé, modes off/double/on, gate git, verify,
archive_ticks et restore_curves côté R2, cohérence des workflows."""
from __future__ import annotations

import datetime as dt
import gzip
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r2_fakes import FakeS3, install, uninstall  # noqa: E402
import r2_io  # noqa: E402
import r2_parts  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
TODAY = dt.datetime.now(dt.timezone.utc).date()
D0, D1 = TODAY.isoformat(), (TODAY - dt.timedelta(days=1)).isoformat()


def gz(*lines):
    return gzip.compress(("".join(l + "\n" for l in lines)).encode(), mtime=0)


def git(*args):
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                          check=True, capture_output=True, text=True).stdout


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        os.makedirs("parts")
        self.fake = FakeS3()
        self.state = Path(self.tmp.name, "state.json")
        self._state = mock.patch.object(r2_parts, "STATE_FILE", str(self.state))
        self._state.start()

    def tearDown(self):
        self._state.stop()
        os.chdir(self.cwd)
        uninstall()
        self.tmp.cleanup()

    def manifest(self, fam):
        raw = self.fake.raw(r2_io.FAMILIES[fam]["manifest"])
        return json.loads(raw) if raw else {"files": {}}


class PushTests(Base):
    def test_double_one_put_per_partition_and_per_run_then_nothing(self):
        install(self.fake, "double")
        for name in (f"pm_ticks_{D1}.jsonl.gz", f"pm_ticks_{D0}.jsonl.gz",
                     f"pm_ticks_{D0}_2.jsonl.gz"):
            Path("parts", name).write_bytes(gz("a", "b"))
        r2_parts.cmd_push(["pm"])
        self.assertEqual(self.fake.count("PUT"), 3 + 1)            # 3 partitions + manifeste
        man = self.manifest("pm")
        self.assertEqual(sorted(man["files"]), sorted(os.listdir("parts")))
        self.assertEqual({e["lines"] for e in man["files"].values()}, {2})
        self.fake.calls.clear()
        r2_parts.cmd_push(["pm"])                                   # rien n'a changé
        self.assertEqual(self.fake.count("PUT"), 0)
        self.assertEqual(self.fake.count("GET"), 1)                 # le manifeste seul

    def test_collector_run_of_500_ticks_costs_two_class_a_ops(self):
        install(self.fake, "double")
        import gz_append
        path = f"parts/kx_ticks_{D0}.jsonl.gz"
        Path(path).write_bytes(gz("ancien"))
        r2_parts.cmd_push(["kx"])
        r2_io.OPS.update(A=0, B=0)
        self.fake.calls.clear()
        with mock.patch.object(gz_append, "LOT_LIGNES", 50):
            for i in range(500):
                gz_append.append_ligne(path, json.dumps({"ts": f"t{i}", "mid": 0.5}))
            gz_append.flush_tout()
        r2_parts.cmd_push(["kx"])
        self.assertEqual(r2_io.OPS["A"], 2)                         # 1 partition + 1 manifeste
        self.assertEqual(self.manifest("kx")["files"][os.path.basename(path)]["lines"], 501)

    def test_off_mode_never_calls_r2(self):
        install(self.fake, "off")
        Path("parts", f"live_match_{D0}.jsonl.gz").write_bytes(gz("x"))
        r2_parts.cmd_push(["live"])
        self.assertEqual(self.fake.calls, [])

    def test_unreadable_partition_is_not_sent(self):
        install(self.fake, "double")
        Path("parts", f"pm_ticks_{D0}.jsonl.gz").write_bytes(b"pas du gzip")
        r2_parts.cmd_push(["pm"])
        self.assertEqual(self.fake.count("PUT"), 0)

    def test_no_credentials_is_harmless(self):
        r2_io.reset_cache()
        Path("parts", f"pm_ticks_{D0}.jsonl.gz").write_bytes(gz("x"))
        with mock.patch.dict(os.environ, {"R2_PRIMARY": "on"}, clear=False):
            for k in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT"):
                os.environ.pop(k, None)
            self.assertEqual(r2_parts.cmd_push(["pm"]), 0)
            self.assertEqual(r2_parts.cmd_pull(["pm"]), 0)


class OnModeTests(Base):
    def test_pull_append_push_roundtrip(self):
        install(self.fake, "on")
        name = f"pm_ticks_{D0}.jsonl.gz"
        Path("parts", name).write_bytes(gz("t1"))
        r2_parts.cmd_push(["pm"])                     # R2 a t1
        os.remove(Path("parts", name))                # checkout frais : rien dans git
        r2_parts.cmd_pull(["pm"])
        self.assertTrue(Path("parts", name).exists())
        with open(Path("parts", name), "ab") as f:    # le collecteur ajoute
            f.write(gz("t2"))
        r2_parts.cmd_push(["pm"])
        remote = self.fake.raw("parts/ticks/" + name)
        self.assertEqual(gzip.decompress(remote).split(), [b"t1", b"t2"])

    def test_concurrent_writer_lines_are_kept(self):
        install(self.fake, "on")
        name = f"live_match_{D0}.jsonl.gz"
        Path("parts", name).write_bytes(gz("base"))
        r2_parts.cmd_push(["live"])
        os.remove(Path("parts", name))
        r2_parts.cmd_pull(["live"])
        # Pendant notre run, un autre écrivain prolonge la version R2…
        key = "parts/live/" + name
        self.fake.put_raw(key, self.fake.raw(key) + gz("autre_run"))
        # … et nous ajoutons nos propres points.
        with open(Path("parts", name), "ab") as f:
            f.write(gz("notre_run"))
        r2_io._MANIFEST_CACHE.clear()
        r2_parts.cmd_push(["live"])
        lines = gzip.decompress(self.fake.raw(key)).split()
        self.assertEqual(lines, [b"base", b"autre_run", b"notre_run"])
        # Le local est aligné sur R2 : gate pourra le retirer du commit.
        self.assertEqual(Path("parts", name).read_bytes(), self.fake.raw(key))
        self.assertEqual(self.manifest("live")["files"][name]["lines"], 3)


    def test_back_to_double_never_shrinks_r2(self):
        # Données écrites pendant « on » : présentes dans R2 seulement.
        install(self.fake, "on")
        name = f"kx_ticks_{D0}.jsonl.gz"
        Path("parts", name).write_bytes(gz("on1", "on2"))
        r2_parts.cmd_push(["kx"])
        os.remove(Path("parts", name))
        # Retour arrière : R2_PRIMARY=double, checkout git sans la partition.
        install(self.fake, "double")
        r2_parts.cmd_pull(["kx"])                     # reprise de la partition absente
        with open(Path("parts", name), "ab") as f:
            f.write(gz("double1"))
        r2_parts.cmd_push(["kx"])
        self.assertEqual(gzip.decompress(self.fake.raw("parts/ticks/" + name)).split(),
                         [b"on1", b"on2", b"double1"])
        # Même sans pull (base inconnue), un fichier local partiel ne remplace
        # jamais une version R2 plus complète : il y est greffé.
        os.remove(self.state)
        Path("parts", name).write_bytes(gz("autre"))
        r2_io._MANIFEST_CACHE.clear()
        r2_parts.cmd_push(["kx"])
        self.assertEqual(gzip.decompress(self.fake.raw("parts/ticks/" + name)).split(),
                         [b"on1", b"on2", b"double1", b"autre"])


class GateTests(Base):
    def setUp(self):
        super().setUp()
        git("init", "-q")
        Path("parts", f"kx_ticks_{D1}.jsonl.gz").write_bytes(gz("vieux"))
        Path("autre.json").write_text("{}")
        git("add", "-A")
        git("commit", "-qm", "init")

    def _stage_changes(self):
        with open(Path("parts", f"kx_ticks_{D1}.jsonl.gz"), "ab") as f:
            f.write(gz("ajout"))
        Path("parts", f"kx_ticks_{D0}.jsonl.gz").write_bytes(gz("nouveau"))
        Path("autre.json").write_text('{"a": 1}')
        git("add", "-A")

    def staged(self):
        return sorted(git("diff", "--cached", "--name-only").split())

    def test_on_mode_removes_only_partitions_identical_in_r2(self):
        install(self.fake, "on")
        self._stage_changes()
        r2_parts.cmd_push(["kx"])
        # Une partition dont l'envoi a « raté » (R2 différent) doit rester.
        with open(Path("parts", f"kx_ticks_{D0}.jsonl.gz"), "ab") as f:
            f.write(gz("non_envoye"))
        git("add", "-A")
        r2_parts.cmd_gate()
        self.assertEqual(self.staged(), ["autre.json", f"parts/kx_ticks_{D0}.jsonl.gz"])
        # La partition modifiée et retirée retrouve sa version git (R2 a la suite).
        self.assertEqual(Path("parts", f"kx_ticks_{D1}.jsonl.gz").read_bytes(), gz("vieux"))

    def test_double_mode_commits_everything_as_before(self):
        install(self.fake, "double")
        self._stage_changes()
        r2_parts.cmd_push(["kx"])
        before = self.staged()
        r2_parts.cmd_gate()
        self.assertEqual(self.staged(), before)
        self.assertEqual(len(before), 3)

    def test_on_mode_without_r2_keeps_everything(self):
        r2_io.reset_cache()
        r2_io._CLIENT_CACHE["client"] = None
        os.environ["R2_PRIMARY"] = "on"
        self._stage_changes()
        before = self.staged()
        r2_parts.cmd_gate()
        self.assertEqual(self.staged(), before)

    def test_deletions_always_pass(self):
        install(self.fake, "on")
        git("rm", "-q", f"parts/kx_ticks_{D1}.jsonl.gz")
        r2_parts.cmd_gate()
        self.assertEqual(self.staged(), [f"parts/kx_ticks_{D1}.jsonl.gz"])


class VerifyTests(Base):
    def test_identical_then_closed_day_divergence_fails(self):
        install(self.fake, "double")
        Path("parts", f"pm_ticks_{D1}.jsonl.gz").write_bytes(gz("a"))
        Path("parts", f"pm_ticks_{D0}.jsonl.gz").write_bytes(gz("b"))
        r2_parts.cmd_push(["pm"])
        self.assertEqual(r2_parts.cmd_verify(["pm"], report_path="r.json"), 0)
        rep = json.load(open("r.json"))
        self.assertEqual(rep["identiques"], 2)
        # Jour en cours qui avance : pas bloquant.
        with open(Path("parts", f"pm_ticks_{D0}.jsonl.gz"), "ab") as f:
            f.write(gz("c"))
        self.assertEqual(r2_parts.cmd_verify(["pm"]), 0)
        # Jour clos différent : bloquant.
        Path("parts", f"pm_ticks_{D1}.jsonl.gz").write_bytes(gz("z"))
        self.assertEqual(r2_parts.cmd_verify(["pm"]), 1)


class ArchiveAndRestoreTests(Base):
    def test_archive_ticks_on_mode_removes_only_what_r2_holds(self):
        install(self.fake, "on")
        old = (TODAY - dt.timedelta(days=10)).isoformat()
        a, b = f"parts/pm_ticks_{old}.jsonl.gz", f"parts/kx_ticks_{old}.jsonl.gz"
        Path(a).write_bytes(gz("x"))
        Path(b).write_bytes(gz("y"))
        r2_parts.cmd_push(["pm"])                      # seul pm est dans R2
        import archive_ticks
        importlib.reload(archive_ticks)
        with mock.patch.object(archive_ticks, "gh", side_effect=AssertionError("release !")):
            code = archive_ticks.main()
        self.assertEqual(code, 1)                      # kx gardé -> run rouge
        self.assertFalse(Path(a).exists())
        self.assertTrue(Path(b).exists())
        idx = json.load(open("parts/ARCHIVE_INDEX.json"))
        self.assertEqual(idx["archives"][0]["release"], "r2:parts/ticks/" + os.path.basename(a))

    def test_restore_curves_takes_r2_first_then_releases(self):
        install(self.fake, "double")
        self.fake.put_raw("parts/hist_book_2026-06.jsonl.gz", gz("h1", "h2"))
        self.fake.put_raw("parts/_manifest.json", json.dumps({"fichiers": {
            "hist_book_2026-06.jsonl.gz": {"octets": len(gz("h1", "h2")), "lignes": 2}}}).encode())
        Path("parts/ARCHIVE_INDEX.json").write_text(json.dumps({"archives": [
            {"fichier": "hist_book_2026-06.jsonl.gz", "release": "curves-2026-06"},
            {"fichier": "hist_book_2026-07.jsonl.gz", "release": "curves-2026-07"}]}))
        import restore_curves
        importlib.reload(restore_curves)
        calls = []

        def fake_gh(*args):
            calls.append(args)
            if args[:2] == ("release", "list"):
                return 0, ""
            if args[:2] == ("release", "download"):
                Path("parts/hist_book_2026-07.jsonl.gz").write_bytes(gz("h3"))
                return 0, ""
            return 1, ""
        with mock.patch.object(restore_curves, "gh", side_effect=fake_gh):
            self.assertEqual(restore_curves.main(), 0)
        self.assertEqual(r2_io.gz_lines(Path("parts/hist_book_2026-06.jsonl.gz").read_bytes()), 2)
        downloads = [c for c in calls if c[:2] == ("release", "download")]
        self.assertEqual(len(downloads), 1)
        self.assertIn("hist_book_2026-07.jsonl.gz", downloads[0])
        self.assertNotIn("hist_book_2026-06.jsonl.gz", downloads[0])


class CentralReaderHookTests(Base):
    def test_load_partitions_and_curves_rebuild_materialize_in_on_mode(self):
        install(self.fake, "on")
        name = f"live_match_{D0}.jsonl.gz"
        ev = json.dumps({"t": f"{D0}T10:00:00", "uid": "u1", "book": "pinnacle", "ho": 1.8,
                         "ao": 2.0, "commence_time": f"{D0}T18:00:00"})
        Path("parts", name).write_bytes(gz(ev))
        r2_parts.cmd_push(["live"])
        os.remove(Path("parts", name))
        import curves_parts
        importlib.reload(curves_parts)
        n = curves_parts.rebuild("match", out_file="book_curves_live.jsonl")
        self.assertEqual(n, 1)
        tick = f"pm_ticks_{D0}.jsonl.gz"
        Path("parts", tick).write_bytes(gz("{}"))
        r2_parts.cmd_push(["pm"])
        os.remove(Path("parts", tick))
        import oddspapi_v5
        self.assertEqual([os.path.basename(p) for p in oddspapi_v5.load_partitions(
            "parts/pm_ticks_*.jsonl")], [tick])


class WorkflowWiringTests(unittest.TestCase):
    """Chaque écrivain de partitions R2 envoie puis filtre son commit."""
    W = REPO / ".github/workflows"

    def test_writers_push_then_gate(self):
        for wf, kinds in (("kalshi_collector.yml", "kx"), ("polymarket_collector.yml", "pm"),
                          ("courbes_alertes.yml", "live")):
            text = (self.W / wf).read_text()
            pull = text.index(f"r2_parts.py pull --kinds {kinds}")
            push = text.index(f"r2_parts.py push --kinds {kinds}")
            gate = text.index("r2_parts.py gate")
            commit = text.index("git commit -m")
            self.assertLess(pull, push, wf)
            self.assertLess(push, gate, wf)
            self.assertLess(gate, commit, wf)

    def test_every_broad_partition_add_is_gated(self):
        for path in self.W.glob("*.yml"):
            text = path.read_text()
            # parts/ entier, exclusion des seuls ticks (donc live inclus),
            # ou motifs ticks/live explicites. parts/hist_* seul : hors R2.
            broad = re.search(r"git add -A -- (?:['\"]?parts/['\"]?\s|':!parts/pm_ticks"
                              r"|'parts/(?:pm|kx)_ticks|'?parts/live)", text)
            if broad:
                self.assertIn("r2_parts.py gate", text, path.name)

    def test_r2_mode_comes_from_repository_variable_with_double_default(self):
        for path in self.W.glob("*.yml"):
            text = path.read_text()
            for m in re.finditer(r"R2_PRIMARY: (.*)", text):
                self.assertEqual(m.group(1).strip(), "${{ vars.R2_PRIMARY || 'double' }}", path.name)

    def test_no_workflow_force_pushes(self):
        for path in self.W.glob("*.yml"):
            text = path.read_text()
            self.assertNotRegex(text, r"git push[^\n]*(--force|-f\b|\+HEAD|--mirror)", path.name)


if __name__ == "__main__":
    unittest.main()
