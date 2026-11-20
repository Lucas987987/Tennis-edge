"""V6.6 : invariants des workflows (aucun gel automatique, déploiement léger,
aucun appel RapidAPI, V6.5 en pause, workflows retirés)."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
WF = ROOT / ".github/workflows"
LAB = ROOT / "Tennis_Edge_Lab"


def read(name):
    return (WF / name).read_text(encoding="utf-8")


class WorkflowsV66Tests(unittest.TestCase):
    def test_daily_job_never_freezes(self):
        daily = read("lab_quotidien.yml")
        self.assertIn("cron: '20 4 * * *'", daily)
        for forbidden in ("selection_v66.py freeze", "candidate_registry_v6.py freeze",
                          "candidate_watch_v61.py discover", "candidate_selection_v63.py run",
                          "push --force", "push -f", "git add -f"):
            self.assertNotIn(forbidden, daily, forbidden)
        self.assertIn("selection_v66.py propose", daily)
        self.assertIn("commit_guard.py", daily)
        self.assertIn("git pull --rebase --autostash", daily)
        self.assertIn("group: lab-automatic-registry", daily)
        self.assertIn("gel_v66.jsonl", daily)  # registre protégé (doit rester inchangé)

    def test_freeze_only_by_manual_dispatch_with_ids(self):
        gel = read("lab_gel.yml")
        self.assertNotIn("schedule:", gel)
        self.assertIn("workflow_dispatch:", gel)
        self.assertIn("ids:", gel)
        self.assertIn('freeze --root . --ids "$IDS"', gel)
        self.assertNotIn("${{ inputs.ids }}\"", gel.split("run:")[-1])  # pas d'injection shell
        self.assertNotIn("push --force", gel)
        self.assertIn("group: lab-automatic-registry", gel)

    def test_pages_hourly_and_light(self):
        pages = read("pages.yml")
        self.assertIn("cron: '7 * * * *'", pages)
        sparse = pages.split("sparse-checkout: |", 1)[1].split("\n\n", 1)[0]
        lines = {line.strip() for line in sparse.splitlines()}
        self.assertNotIn("parts", lines)
        for heavy in ("restore_curves", "prospective_v64", "bookmakers_sets_v5.py",
                      "history_stability.py", "incremental_v631"):
            self.assertNotIn(heavy, pages, heavy)
        for asset in ("research_v66.js", "research_v66.css", "books.py", "clv_stats.py",
                      "history_stability.json", "propositions_v66.json", "gel_v66_prospective.json"):
            self.assertIn(asset, pages, asset)

    def test_retired_workflows_and_v65_paused(self):
        for name in ("lab_autonomous.yml", "lab_autonomous_auto_v63.yml", "lab_incremental_v631.yml",
                     "lab_economic_v64.yml", "lab_prospective_v65.yml"):
            self.assertFalse((WF / name).exists(), f"{name} doit être supprimé")
        self.assertNotIn("schedule:", read("lab_v655_ingestion.yml"))

    def test_no_rapidapi_in_lab(self):
        pattern = re.compile(r"rapidapi|odds-api1|x-rapidapi", re.I)
        files = [WF / "lab_quotidien.yml", WF / "lab_gel.yml", WF / "pages.yml"]
        files += [p for p in LAB.glob("*.py")] + [p for p in LAB.glob("*.js") if p.name != "data.js"]
        for path in files:
            self.assertIsNone(pattern.search(path.read_text(encoding="utf-8")), path.name)

    def test_page_drops_v64_and_noise_cards(self):
        html = (LAB / "research.html").read_text(encoding="utf-8")
        self.assertNotIn("research_v64.js", html)
        self.assertNotIn("v64Economic", html)
        self.assertNotIn("v5Unconfirmed", html)
        self.assertIn("Jouables en France", (LAB / "research_v66.js").read_text(encoding="utf-8"))
        self.assertIn("Stabilité sur 16 ans (tennis-data, clôture Pinnacle)", html)
        self.assertIn("Propositions de la semaine", html)
        self.assertIn("Pistes gelées (V6.6)", html)


if __name__ == "__main__":
    unittest.main()
