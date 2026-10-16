"""depot_neuf.py : ce qui reste hors du dépôt neuf est TOUJOURS couvert par R2,
et `verifier` attrape tout écart."""
import datetime as dt
import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r2_fakes import FakeS3, install, uninstall  # noqa: E402
import r2_io  # noqa: E402
import depot_neuf as dn  # noqa: E402

NOW = dt.datetime(2026, 10, 28, 12, tzinfo=dt.timezone.utc)


def gz(lines):
    return gzip.compress("".join(l + "\n" for l in lines).encode())


def git(*a, cwd):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.makedirs("parts")
        self.fake = FakeS3()
        install(self.fake, mode="on")
        self.r2 = r2_io.client()
        self.mans = {}

    def tearDown(self):
        os.chdir(self.old)
        uninstall()
        self.tmp.cleanup()

    def local(self, name, data):
        with open(os.path.join("parts", name), "wb") as f:
            f.write(data)
        return os.path.join("parts", name)

    def distant(self, fam, name, data):
        key = r2_io.FAMILIES[fam]["prefix"] + name
        self.fake.put_raw(key, data)
        man_key = r2_io.FAMILIES[fam]["manifest"]
        raw = self.fake.raw(man_key)
        man = json.loads(raw) if raw else r2_io.empty_manifest(fam)
        man["files"][name] = {"key": key, "sha256": hashlib.sha256(data).hexdigest()}
        self.fake.put_raw(man_key, json.dumps(man).encode())


class Couverture(Base):
    def etat(self, path):
        return dn.couverture(path, self.r2, self.mans, now=NOW)

    def test_identique(self):
        d = gz(["a", "b"])
        p = self.local("pm_ticks_2026-10-20.jsonl.gz", d)
        self.distant("pm", "pm_ticks_2026-10-20.jsonl.gz", d)
        self.assertEqual(self.etat(p), "identique")

    def test_r2_plus_complet(self):
        p = self.local("live_match_2026-10-20.jsonl.gz", gz(["a", "b"]))
        self.distant("live", "live_match_2026-10-20.jsonl.gz", gz(["a", "b", "c"]))
        self.assertEqual(self.etat(p), "r2_contient")

    def test_r2_moins_complet_reste_dans_git(self):
        p = self.local("kx_ticks_2026-10-20.jsonl.gz", gz(["a", "b", "c"]))
        self.distant("kx", "kx_ticks_2026-10-20.jsonl.gz", gz(["a", "b"]))
        self.assertEqual(self.etat(p), "different")

    def test_absent_de_r2(self):
        p = self.local("pm_ticks_2026-10-21.jsonl.gz", gz(["a"]))
        self.assertEqual(self.etat(p), "absent_r2")

    def test_hist_courant_reste(self):
        p = self.local("hist_book_2026-W44.jsonl.gz", gz(["a"]))
        self.distant("hist", "hist_book_2026-W44.jsonl.gz", gz(["a"]))
        self.assertEqual(self.etat(p), "courante")

    def test_hist_fige_couvert(self):
        d = gz(["a"])
        p = self.local("hist_book_2026-W40.jsonl.gz", d)
        self.distant("hist", "hist_book_2026-W40.jsonl.gz", d)
        self.assertEqual(self.etat(p), "identique")

    def test_hors_familles(self):
        p = self.local("ARCHIVE_INDEX.json", b"{}")
        self.assertIsNone(self.etat(p))
        with open("clv_history.jsonl", "w") as f:
            f.write("x\n")
        self.assertIsNone(self.etat("clv_history.jsonl"))


class InstantaneEtVerifier(Base):
    def setUp(self):
        super().setUp()
        git("init", "-q", "-b", "main", cwd=".")
        git("config", "user.email", "t@t", cwd=".")
        git("config", "user.name", "t", cwd=".")
        d = gz(["a", "b"])
        self.local("pm_ticks_2026-10-20.jsonl.gz", d)
        self.distant("pm", "pm_ticks_2026-10-20.jsonl.gz", d)
        self.local("kx_ticks_2026-10-20.jsonl.gz", gz(["x", "y"]))          # pas dans R2
        os.makedirs("scripts")
        Path("scripts/a.py").write_text("print(1)\n")
        Path("index.html").write_text("<p>\n")
        git("add", "-A", cwd=".")
        git("commit", "-q", "-m", "init", cwd=".")
        self.neuf = os.path.join(self.tmp.name, "..", os.path.basename(self.tmp.name) + "_neuf")

    def tearDown(self):
        subprocess.run(["rm", "-rf", self.neuf])
        super().tearDown()

    def construire(self):
        self.assertEqual(dn.cmd_instantane(self.neuf), 0)
        git("init", "-q", "-b", "main", cwd=self.neuf)
        git("config", "user.email", "t@t", cwd=self.neuf)
        git("config", "user.name", "t", cwd=self.neuf)
        git("add", "-A", cwd=self.neuf)
        git("commit", "-q", "-m", "import", cwd=self.neuf)

    def test_seul_le_couvert_reste_dehors(self):
        self.construire()
        self.assertFalse(os.path.exists(os.path.join(self.neuf, "parts/pm_ticks_2026-10-20.jsonl.gz")))
        self.assertTrue(os.path.exists(os.path.join(self.neuf, "parts/kx_ticks_2026-10-20.jsonl.gz")))
        self.assertTrue(os.path.exists(os.path.join(self.neuf, "scripts/a.py")))
        imp = json.loads(Path(self.neuf, dn.IMPORT_JSON).read_text())
        self.assertEqual(list(imp["laisses_dans_r2"]), ["parts/pm_ticks_2026-10-20.jsonl.gz"])

    def test_verifier_ok(self):
        self.construire()
        self.assertEqual(dn.cmd_verifier(self.neuf), 0)

    def test_verifier_attrape_un_fichier_modifie(self):
        self.construire()
        Path(self.neuf, "index.html").write_text("<p>modifié\n")
        git("commit", "-q", "-am", "x", cwd=self.neuf)
        self.assertEqual(dn.cmd_verifier(self.neuf), 1)

    def test_verifier_attrape_l_ancien_qui_bouge(self):
        self.construire()
        Path("index.html").write_text("<p>nouveau\n")
        git("commit", "-q", "-am", "x", cwd=".")
        self.assertEqual(dn.cmd_verifier(self.neuf), 1)

    def test_verifier_attrape_r2_qui_perd_la_partition(self):
        self.construire()
        self.fake.objects.clear()
        r2_io.reset_cache()
        r2_io._CLIENT_CACHE["client"] = r2_io.R2(self.fake, r2_io.DEFAULT_BUCKET)
        self.assertEqual(dn.cmd_verifier(self.neuf), 1)

    def test_instantane_refuse_sans_r2(self):
        r2_io.reset_cache()
        r2_io._CLIENT_CACHE["client"] = None
        self.assertEqual(dn.cmd_instantane(self.neuf), 1)


if __name__ == "__main__":
    unittest.main()
