import importlib.util, pathlib, unittest, datetime as dt
P=pathlib.Path(__file__).resolve().parents[1]/"v65"/"prospective.py"
spec=importlib.util.spec_from_file_location("prospective_v65",P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
S={"selection_id":"s","eligible_after_utc":"2026-10-15","candidates":[{"id":"a","book":"unibet","market":"match"}],"tops":{"top10":["a"]}}
NOW=dt.datetime(2026,10,20,tzinfo=dt.timezone.utc)
def event(**kw):
    x={"event_id":"e1","hypothesis_id":"a","fixture_id":"f1","signal_at_utc":"2026-10-16T10:00:00Z","book":"unibet","market":"match","odds_at_signal":2.2,"rules_verified_at_signal":True}
    x.update(kw);return x
class TestV65(unittest.TestCase):
    def test_empty(self): self.assertEqual(m.process(S,[],NOW)["event_count"],0)
    def test_roi_clv(self):
        e=event(result="win",closing_odds=2.0,settled_at_utc="2026-10-17T10:00:00Z")
        g=m.process(S,[e],NOW)["groups"][0]
        self.assertEqual(g["roi_pct"],120.0)
        self.assertEqual(g["clv_mean_pct"],10.0)
    def test_pre_freeze(self):
        with self.assertRaises(ValueError):m.process(S,[event(signal_at_utc="2026-10-14T10:00:00Z")],NOW)
    def test_unverified(self):
        with self.assertRaises(ValueError):m.process(S,[event(rules_verified_at_signal=False)],NOW)
    def test_duplicate_conflict(self):
        with self.assertRaises(ValueError):m.process(S,[event(),event(odds_at_signal=3.0)],NOW)
    def test_no_future(self):
        with self.assertRaises(ValueError):m.process(S,[event(signal_at_utc="2026-10-21T10:00:00Z")],NOW)
if __name__=="__main__": unittest.main()
