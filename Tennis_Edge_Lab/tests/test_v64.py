"""V6.4 reproducibility tests, 100% synthetic files, no remote access."""
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

LAB=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(LAB))
import economic_v64 as v


class EconomicV64Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.archive=self.root/v.ARCHIVE_REL
        self.archive.mkdir(parents=True)
        self.audit=self.root/v.AUDIT_REL
        self.audit.parent.mkdir(parents=True,exist_ok=True)

    @staticmethod
    def fixture(prefix,n=100):
        return [hashlib.sha256(f'{prefix}-{i}'.encode()).hexdigest() for i in range(n)]

    def row(self, market='match',roi=8,clv=2,key='a',n=100):
        return dict(market=market,book='pinnacle',horizon='6h',selection='favori',
                    criteria=[{'dimension':'circuit','value':key}],n=n,unique_matches=n,
                    distinct_days=40,clv_n=n,roi_pct=roi,clv_mean_pct=clv,
                    roi_ci95=[-2,17],first_half={'roi_pct':3},second_half={'roi_pct':5},
                    discovery_fixture_hashes=self.fixture(key,n),
                    p_fair_valid=True,feature_availability={'verified':True},
                    end_date='2026-10-13',start_date='2026-06-01')

    def write(self,rows):
        manifests={}
        for market in v.MARKETS:
            p=self.archive/f'{market}.jsonl.gz'
            subset=[r for r in rows if r['market']==market]
            with gzip.open(p,'wt',encoding='utf8') as f:
                for r in subset:f.write(json.dumps(r)+'\n')
            manifests[market]={'compressed_jsonl':p.relative_to(self.root).as_posix(),
                               'compressed_sha256':v.sha_file(p),'segment_count':len(subset)}
        h=v.sha_object({'demo':'a'*64})
        (self.archive/'manifest.json').write_text(json.dumps({'source_snapshot_sha256':h,'markets':manifests}))
        self.audit.write_text(json.dumps({'source_hashes':{'demo':'a'*64},'archive':{'source_snapshot_sha256':h},'segment_count':len(rows)}))

    def test_all_markets_no_quota_and_tops(self):
        rows=[self.row(market=m,key=f'{m}-{i}') for m in v.MARKETS for i in range(24)]
        self.write(rows)
        doc=v.build(self.root,dt.date(2026,10,14))
        self.assertEqual(doc['selected_count'],72)
        self.assertEqual(doc['by_market'],{'match':24,'set1':24,'set2':24})
        self.assertEqual(len(doc['tops']['top50']),50)
        self.assertEqual(len(doc['tops']['top10']),10)
        self.assertEqual(doc['eligible_after_utc'],'2026-10-15')
        self.assertTrue(v.verify(doc))

    def test_positive_roi_and_clv_both_required(self):
        rows=[self.row(roi=5,clv=1,key='good'),self.row(roi=-1,clv=2,key='roi-negative'),
              self.row(roi=10,clv=0,key='clv-zero'),self.row(n=70,key='too-small')]
        self.write(rows)
        doc=v.build(self.root,dt.date(2026,10,14))
        self.assertEqual(doc['selected_count'],1)
        self.assertEqual(doc['rejected']['roi_not_positive'],1)
        self.assertEqual(doc['rejected']['clv_not_positive'],1)

    def test_inexact_population_deduplicated_within_market(self):
        a=self.row(key='match-one')
        b=self.row(key='match-two',roi=2)
        b['discovery_fixture_hashes']=list(a['discovery_fixture_hashes'])
        self.write([a,b])
        doc=v.build(self.root,dt.date(2026,10,14))
        self.assertEqual(doc['selected_count'],1)
        self.assertEqual(doc['rejected']['near_duplicate_population'],1)

    def test_archive_corruption_blocks_selection(self):
        self.write([self.row(key='x')])
        with (self.archive/'match.jsonl.gz').open('ab') as fh:fh.write(b'break')
        with self.assertRaisesRegex(ValueError,'corrompue'):v.build(self.root,dt.date(2026,10,14))

    def test_lookahead_and_all_fail_closed(self):
        self.write([self.row(roi=-5,key='x')])
        with self.assertRaisesRegex(ValueError,'Aucune hypothèse'):v.build(self.root,dt.date(2026,10,14))
        self.write([self.row(key='future')|{'end_date':'2026-11-01'}])
        with self.assertRaisesRegex(ValueError,'Aucune hypothèse'):v.build(self.root,dt.date(2026,10,14))

    def test_scoring_ranking_is_deterministic(self):
        rows=[self.row(key='x',roi=20,clv=3),self.row(key='y',roi=5,clv=2)]
        self.write(rows)
        x=v.build(self.root,dt.date(2026,10,14))
        y=v.build(self.root,dt.date(2026,10,14))
        self.assertEqual(x['selection_id'],y['selection_id'])
        self.assertGreater(x['candidates'][0]['score'],x['candidates'][1]['score'])


if __name__=='__main__':unittest.main()
