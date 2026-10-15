#!/usr/bin/env python3
"""Read-only ingestion of existing JSONL sources into V6.5.4 preview.
Only explicitly attested, complete bookmaker snapshots are forwarded.
"""
import argparse, collections, datetime as dt, hashlib, importlib.util, json
from pathlib import Path
import importlib.util as _ilu, pathlib as _pl
_spec = _ilu.spec_from_file_location("clv_source", _pl.Path(__file__).resolve().parent.parent / "clv_source.py")
clv_source = _ilu.module_from_spec(_spec); _spec.loader.exec_module(clv_source)   # clv_history partitionné (15/10/2026)

REQUIRED=('observation_id','fixture_id','market','book','horizon','selection','observed_at_utc','match_starts_at_utc','source','metrics','field_observed_at_utc')
DEFAULT_SOURCES=('odds_alerts_log.jsonl','clv_history.jsonl','Tennis_Edge_Lab/v65/bookmaker_snapshots.jsonl')

def import_matcher(path):
    spec=importlib.util.spec_from_file_location('matcher_v654',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def read_sources(root,paths):
    stats=collections.Counter(); rejects=collections.Counter(); eligible=[]; seen={}
    for name in paths:
        file=root/name
        if not clv_source.exists(file):
            stats['missing_sources']+=1;continue
        stats['found_sources']+=1
        with clv_source.open_text(file) as f:
            for line in f:
                if not line.strip():continue
                stats['rows_seen']+=1
                try:
                    row=json.loads(line)
                    if not isinstance(row,dict):raise ValueError('not_object')
                    missing=[k for k in REQUIRED if k not in row]
                    if missing:raise ValueError('missing:'+','.join(missing))
                    if row.get('source_kind')!='bookmaker_quote_snapshot' or row.get('verified_source') is not True:
                        raise ValueError('source_not_attested')
                    # Preserve only exact source assertions. Never infer from historical curves.
                    if row.get('horizon_verified') is not True or row.get('market_verified') is not True or row.get('selection_verified') is not True:
                        raise ValueError('identity_not_attested')
                    if row.get('uses_match_result') is True or row.get('uses_closing_odds') is True:
                        raise ValueError('lookahead')
                    key=str(row['observation_id'])
                    digest=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                    if key in seen:
                        if seen[key]!=digest:raise ValueError('conflicting_observation_id')
                        stats['duplicate_identical']+=1;continue
                    seen[key]=digest;eligible.append(row)
                except (ValueError,TypeError,KeyError) as exc:
                    rejects[str(exc).split(':')[0]]+=1
    return eligible,dict(stats),dict(rejects)

def run(root,source_paths,now=None):
    snapshot=json.loads((root/'Tennis_Edge_Lab/v65/selection_v64_frozen.json').read_text(encoding='utf-8'))
    matcher=import_matcher(root/'Tennis_Edge_Lab/v65/matcher_v654.py')
    rows,stats,reasons=read_sources(root,source_paths)
    outcome=matcher.evaluate(snapshot,rows,now=now)
    return {'schema_version':1,'mode':'read_only_ingestion_preview',
            'selection_id':snapshot['selection_id'],'sources':list(source_paths),
            'ingestion_stats':stats,'ingestion_rejections':reasons,
            'forwarded_snapshots':len(rows),'matcher':outcome,
            'persistent_storage':False,'automatic_bookmaker_api_connection':False,
            'warning':'Scheduled source scan only. Does not create bookmaker observations, archive signals or certify bets.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',default='.')
    p.add_argument('--output',required=True);p.add_argument('--source',action='append')
    args=p.parse_args();root=Path(args.root).resolve()
    result=run(root,args.source or DEFAULT_SOURCES)
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'rows':result['ingestion_stats'].get('rows_seen',0),
      'forwarded':result['forwarded_snapshots'],'provisional_matches':result['matcher']['provisional_matches'],
      'certified_bets':result['matcher']['certified_bets']},ensure_ascii=False))
if __name__=='__main__':main()
