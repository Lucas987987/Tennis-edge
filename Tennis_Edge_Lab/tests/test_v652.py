import importlib.util, pathlib, unittest
path=pathlib.Path(__file__).resolve().parents[1]/"v65"/"compatibility_v652.py"
spec=importlib.util.spec_from_file_location("v652",path)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
SNAP={"selection_id":"fixed","eligible_after_utc":"2026-10-15",
      "candidates":[{"id":"x","market":"match","book":"Unibet","criteria":[{"dimension":"amplitude_mouvement","value":"5-10"}]}]}
class Tests(unittest.TestCase):
    def test_never_certifies(self):
        a={"uid":"u","home":"A","away":"B","logged_at":"2026-10-16T11:00:00Z"}
        r=m.inspect(SNAP,[a])
        self.assertEqual(r["eligible_signals"],0)
        self.assertEqual(r["post_freeze_alert_rows"],1)
        self.assertIn("amplitude_mouvement",r["candidates"][0]["unverified_dimensions"])
    def test_historical_rejected(self):
        r=m.inspect(SNAP,[{"logged_at":"2026-10-14T11:00:00Z"}])
        self.assertEqual(r["post_freeze_alert_rows"],0)
    def test_missing_timestamp(self):
        r=m.inspect(SNAP,[{}])
        self.assertEqual(r["reasons"]["missing_logged_at"],1)
    def test_naive_timestamp(self):
        r=m.inspect(SNAP,[{"logged_at":"2026-10-16T11:00:00"}])
        self.assertEqual(r["reasons"]["timezone_missing"],1)
if __name__=="__main__":unittest.main()
