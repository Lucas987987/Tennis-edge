"""Tests V4 sans réseau ni données personnelles externes."""
import datetime as dt, json, pathlib, tempfile, unittest, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import candidate_registry as reg
import source_features as sf

class AutonomyTests(unittest.TestCase):
 def test_freeze_append_only_future(self):
  research={'row_counts':{'settled_quality_ok':1452},'split':{'last_test':'2026-10-11'},
   'candidates':[{'rule':'mouvement ≥ 5 % ET délai 8–24 h',
    'train':{'n':140,'roi':12},'test':{'n':50,'roi':4}}],
   'hypothesis_circuits':{'historical':[]},'frozen_hypotheses':[]}
  with tempfile.TemporaryDirectory() as tmp:
   path=pathlib.Path(tmp)/'candidates.jsonl'
   stamp=dt.datetime.fromisoformat('2026-10-12T13:00:00+00:00')
   created=reg.freeze(research,when=stamp,ledger=path)
   self.assertEqual(len(created),1)
   self.assertEqual(created[0]['eligible_after'],'2026-10-13')
   old=path.read_bytes()
   self.assertEqual(reg.freeze(research,when=stamp,ledger=path),[])
   self.assertEqual(old,path.read_bytes())
   self.assertEqual(len(reg.read_ledger(path)),1)
   corrupted=json.loads(old.decode());corrupted['criteria'][0]['min']=0
   path.write_text(json.dumps(corrupted,ensure_ascii=False)+'\n')
   with self.assertRaisesRegex(ValueError,'Chaîne'):reg.read_ledger(path)
 def test_compiled_predicates_known_before_bet(self):
  filt=reg.check_rule('mouvement ≥ 5 % ET délai 8–24 h')
  self.assertTrue(reg.matches_rule({'mag':7,'lead':800},filt))
  self.assertFalse(reg.matches_rule({'mag':4,'lead':800},filt))
  with self.assertRaises(ValueError):reg.check_rule('match gagné')
 def test_ticks_after_signal_are_excluded(self):
  with tempfile.TemporaryDirectory() as temp:
   path=pathlib.Path(temp)/'pm_ticks_demo.jsonl'
   rows=[{'ts':'2026-10-12T09:55:00Z','local_uid':'u','market_type':'match','local_side':'home','mid':.51,'spread':.02},
         {'ts':'2026-10-12T10:05:00Z','local_uid':'u','market_type':'match','local_side':'home','mid':.99,'spread':.01}]
   path.write_text('\n'.join(json.dumps(x) for x in rows))
   r=sf.process_ticks(path,{'u':{'decision_ts':sf.epoch('2026-10-12T10:00:00Z')}},{'u':'home'},'polymarket')
   self.assertEqual(r['quotes']['u']['mid'],.51)
   self.assertEqual(r['matched'],1)
 def test_empty_registry_evaluates_zero(self):
  with tempfile.TemporaryDirectory() as temp:
   self.assertEqual(reg.read_ledger(pathlib.Path(temp)/'none.jsonl'),[])

if __name__=='__main__':unittest.main()
