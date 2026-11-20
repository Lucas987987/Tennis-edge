import importlib.util, pathlib, unittest, datetime as dt, tempfile, json
path=pathlib.Path(__file__).resolve().parents[1]/"v65"/"source_mapping_v653.py"
spec=importlib.util.spec_from_file_location("v653",path)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_naive_unresolved(self):self.assertEqual(m.parse_timestamp("2026-10-15T12:00:00")[1],"naive_unresolved")
 def test_aware_utc(self):self.assertEqual(m.parse_timestamp("2026-10-15T12:00:00+02:00")[0].hour,10)
 def test_invalid(self):self.assertEqual(m.parse_timestamp("bad")[1],"invalid")
 def test_freeze(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/"odds_alerts_log.jsonl"
   p.write_text('{"logged_at":"2026-10-15T00:30:00+02:00"}\n{"logged_at":"2026-10-15T00:30:00Z"}\n')
   d=m.scan(p,dt.datetime(2026,10,15,tzinfo=dt.timezone.utc))
   self.assertEqual(d["counts"]["timestamp_before_freeze"],1)
   self.assertEqual(d["counts"]["timestamp_after_freeze"],1)
 def test_no_signal(self):
  with tempfile.TemporaryDirectory() as tmp:
   s={"eligible_after_utc":"2026-10-15","selection_id":"s","candidates":[{"market":"match","criteria":[{"dimension":"marge"}]}]}
   self.assertEqual(m.build(pathlib.Path(tmp),s)["certified_signals"],0)
if __name__=="__main__":unittest.main()
