"""croissance_depot : versions × taille sur un petit dépôt."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import croissance_depot as cd  # noqa: E402


def git(*a, env=None):
    e = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
             GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t", **(env or {}))
    return subprocess.run(["git", *a], check=True, capture_output=True, text=True, env=e).stdout


class CroissanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        git("init", "-q")
        old = {"GIT_AUTHOR_DATE": "2020-01-01T00:00:00", "GIT_COMMITTER_DATE": "2020-01-01T00:00:00"}
        Path("vieux.json").write_text("x" * 5000)
        git("add", "-A"); git("commit", "-qm", "vieux", env=old)
        os.makedirs("parts")
        for i in range(3):                               # 3 versions d'un gros fichier
            Path("closing_lines.json").write_text("c" * (1000 + i))
            Path(f"parts/pm_ticks_2026-10-1{i}.jsonl.gz").write_text("t" * 200)
            git("add", "-A"); git("commit", "-qm", f"run {i}")
        Path("petit.json").write_text("p")
        git("add", "-A"); git("commit", "-qm", "petit")

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_versions_times_head_size_grouped_by_family(self):
        rep = cd.measure(hours=24, top=5)
        self.assertEqual(rep["commits"], 4)
        top = {r["fichier"]: r for r in rep["top"]}
        self.assertEqual(rep["top"][0]["fichier"], "closing_lines.json")
        self.assertEqual(top["closing_lines.json"]["versions"], 3)
        self.assertEqual(top["closing_lines.json"]["octets"], 3 * 1002)
        self.assertEqual(top["parts/pm_ticks_*.jsonl.gz"]["versions"], 3)
        self.assertNotIn("vieux.json", top)              # hors fenêtre
        ligne = cd.ligne_telegram(rep)
        self.assertTrue(ligne.startswith("croissance 24 h : "))
        self.assertIn("closing_lines.json", ligne)

    def test_deleted_file_has_versions_but_unknown_size(self):
        git("rm", "-q", "parts/pm_ticks_2026-10-10.jsonl.gz"); git("commit", "-qm", "rm")
        rep = cd.measure(hours=24, top=5)
        fam = next(r for r in rep["top"] if r["fichier"] == "parts/pm_ticks_*.jsonl.gz")
        self.assertEqual(fam["taille_inconnue"], 1)
        self.assertEqual(fam["octets"], 2 * 200)

    def test_cli_writes_json_and_never_fails(self):
        self.assertEqual(cd.main(["--json", "c.json"]), 0)
        self.assertTrue(Path("c.json").exists())
        os.chdir(tempfile.gettempdir())                  # hors dépôt : pas d'erreur
        self.assertEqual(cd.main(["--json", os.path.join(self.tmp.name, "d.json")]), 0)


if __name__ == "__main__":
    unittest.main()
