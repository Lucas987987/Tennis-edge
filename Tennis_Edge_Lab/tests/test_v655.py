import importlib.util, pathlib, tempfile, unittest, json
P=pathlib.Path(__file__).resolve().parents[1]/'v65'/'ingest_v655.py'
s=importlib.util.spec_from_file_location('ingest_v655',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_missing_source(self):
  with tempfile.TemporaryDirectory() as d:
   rows,stats,rej=m.read_sources(pathlib.Path(d),['none.jsonl'])
   self.assertEqual(rows,[]);self.assertEqual(stats['missing_sources'],1)
 def test_historical_alert_not_forwarded(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'alerts.jsonl';p.write_text('{"uid":"a","logged_at":"2026-10-15T12:00:00Z"}\n')
   rows,stats,rej=m.read_sources(pathlib.Path(d),['alerts.jsonl'])
   self.assertEqual(len(rows),0);self.assertEqual(rej['missing'],1)
 def test_no_fabricated_attestation(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'quotes.jsonl';p.write_text(json.dumps({k:'x' for k in m.REQUIRED})+'\n')
   rows,_,rej=m.read_sources(pathlib.Path(d),['quotes.jsonl'])
   self.assertEqual(rows,[]);self.assertEqual(rej['source_not_attested'],1)
 def test_conflicting_duplicates_blocked(self):
  with tempfile.TemporaryDirectory() as d:
   row={k:'x' for k in m.REQUIRED};row.update(source_kind='bookmaker_quote_snapshot',verified_source=True,horizon_verified=True,market_verified=True,selection_verified=True)
   p=pathlib.Path(d)/'quotes.jsonl';p.write_text(json.dumps(row)+'\n'+json.dumps(dict(row,book='other'))+'\n')
   rows,_,rej=m.read_sources(pathlib.Path(d),['quotes.jsonl'])
   self.assertEqual(len(rows),1);self.assertEqual(rej['conflicting_observation_id'],1)
 def test_identical_duplicate_deduped(self):
  with tempfile.TemporaryDirectory() as d:
   row={k:'x' for k in m.REQUIRED};row.update(source_kind='bookmaker_quote_snapshot',verified_source=True,horizon_verified=True,market_verified=True,selection_verified=True)
   p=pathlib.Path(d)/'quotes.jsonl';p.write_text((json.dumps(row)+'\n')*2)
   rows,stats,_=m.read_sources(pathlib.Path(d),['quotes.jsonl'])
   self.assertEqual(len(rows),1);self.assertEqual(stats['duplicate_identical'],1)
if __name__=='__main__':unittest.main()
