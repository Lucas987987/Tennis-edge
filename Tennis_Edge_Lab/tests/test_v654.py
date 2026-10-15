import importlib.util, pathlib, unittest, datetime as dt
p=pathlib.Path(__file__).resolve().parents[1]/'v65'/'matcher_v654.py';spec=importlib.util.spec_from_file_location('v654',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
S={'selection_id':'s','eligible_after_utc':'2026-10-15','candidates':[{'id':'a','market':'match','book':'Unibet','horizon':'1h','selection':'outsider','criteria':[{'dimension':'amplitude_mouvement','value':'5,00 ≤ amplitude < 10,00 %'}]}]}
NOW=dt.datetime(2026,10,20,tzinfo=dt.timezone.utc)
def obs(**changes):
 x={'observation_id':'o','fixture_id':'f','market':'match','book':'Unibet','horizon':'1h','selection':'outsider','observed_at_utc':'2026-10-16T10:00:00Z','match_starts_at_utc':'2026-10-16T11:00:00Z','source':'verified-adapter','source_kind':'bookmaker_quote_snapshot','verified_source':True,'market_verified':True,'selection_verified':True,'horizon_verified':True,'metrics':{'odds':2.5,'minutes_to_start':60,'amplitude_pct':7},'field_observed_at_utc':{'odds':'2026-10-16T10:00:00Z','minutes_to_start':'2026-10-16T10:00:00Z','amplitude_pct':'2026-10-16T09:59:00Z'}}
 x.update(changes);return x
class Tests(unittest.TestCase):
 def test_match(self):
  r=m.evaluate(S,[obs()],NOW);self.assertEqual(r['provisional_matches'],1);self.assertEqual(r['certified_bets'],0)
 def test_future_feature(self):
  x=obs();x['field_observed_at_utc']['amplitude_pct']='2026-10-16T10:01:00Z';self.assertEqual(m.evaluate(S,[x],NOW)['provisional_matches'],0)
 def test_no_source(self):self.assertEqual(m.evaluate(S,[obs(verified_source=False)],NOW)['provisional_matches'],0)
 def test_freeze(self):self.assertEqual(m.evaluate(S,[obs(observed_at_utc='2026-10-14T10:00:00Z')],NOW)['provisional_matches'],0)
 def test_criteria(self):
  self.assertTrue(m.criterion('marge','2,00 ≤ marge < 4,00 %',{'margin_pct':3}))
  self.assertFalse(m.criterion('limite','100,00 ≤ limite < 300,00',{'limit':300}))
  self.assertTrue(m.criterion('tranche_cote','cote < 1,50',{'odds':1.4}))
 def test_horizon(self):self.assertEqual(m.evaluate(S,[obs(horizon_verified=False)],NOW)['provisional_matches'],0)
 def test_naive(self):self.assertEqual(m.evaluate(S,[obs(observed_at_utc='2026-10-16T10:00:00')],NOW)['provisional_matches'],0)
 def test_empty(self):self.assertEqual(m.evaluate(S,[],NOW)['observations'],0)
if __name__=='__main__':unittest.main()
