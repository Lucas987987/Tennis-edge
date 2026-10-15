#!/usr/bin/env python3
"""V6.5.3 read-only source mapping. No inference of timezones or hypothesis matches."""
import argparse, collections, datetime as dt, json
from pathlib import Path
import importlib.util as _ilu, pathlib as _pl
_spec = _ilu.spec_from_file_location("clv_source", _pl.Path(__file__).resolve().parent.parent / "clv_source.py")
clv_source = _ilu.module_from_spec(_spec); _spec.loader.exec_module(clv_source)   # clv_history partitionné (15/10/2026)

FILES=("odds_alerts_log.jsonl","clv_history.jsonl")
def parse_timestamp(value):
    if not isinstance(value,str) or not value.strip():
        return None,"missing"
    try:
        t=dt.datetime.fromisoformat(value.strip().replace("Z","+00:00"))
    except ValueError:
        return None,"invalid"
    if t.tzinfo is None:
        return None,"naive_unresolved"
    return t.astimezone(dt.timezone.utc),"aware"

def scan(path, freeze, sample_limit=20):
    counts=collections.Counter()
    types=collections.defaultdict(collections.Counter)
    keys=collections.Counter()
    nested=collections.defaultdict(collections.Counter)
    examples={}
    if not clv_source.exists(path):
        return {"exists":False}
    with clv_source.open_text(path) as stream:
        for line in stream:
            if not line.strip():continue
            counts["rows"]+=1
            try: row=json.loads(line)
            except json.JSONDecodeError:
                counts["invalid_json"]+=1;continue
            if not isinstance(row,dict):
                counts["non_object"]+=1;continue
            for key,value in row.items():
                keys[key]+=1
                types[key][type(value).__name__]+=1
                if isinstance(value,dict):
                    nested[key].update(value.keys())
                elif isinstance(value,list) and value and isinstance(value[0],dict):
                    nested[key].update(value[0].keys())
            stamp=row.get("logged_at")
            if stamp is None:
                stamp=row.get("commence_time")
                counts["timestamp_fallback_start_not_signal"]+=1
            t,status=parse_timestamp(stamp)
            counts["timestamp_"+status]+=1
            if t:
                counts["timestamp_after_freeze" if t>=freeze else "timestamp_before_freeze"]+=1
            for key in ("uid","fixture_id","home","away","commence_time","logged_at"):
                if row.get(key) not in (None,""):counts["has_"+key]+=1
    return {"exists":True,"bytes":path.stat().st_size,"counts":dict(counts),
            "fields":{k:{"count":n,"types":dict(types[k])} for k,n in sorted(keys.items())},
            "nested_keys":{k:dict(v) for k,v in sorted(nested.items())}}

def build(root, snapshot):
    freeze=dt.datetime.fromisoformat(snapshot["eligible_after_utc"]+"T00:00:00+00:00")
    candidates=snapshot["candidates"]
    dimensions=collections.Counter(x["dimension"] for c in candidates for x in c["criteria"])
    return {"schema_version":1,"mode":"read_only_source_mapping","selection_id":snapshot["selection_id"],
            "freeze_utc":freeze.isoformat(),
            "sources":{f:scan(root/f,freeze) for f in FILES},
            "hypothesis_dimensions":dict(sorted(dimensions.items())),
            "hypotheses_by_market":dict(collections.Counter(c["market"] for c in candidates)),
            "certified_signals":0,
            "limitations":["A naive timestamp is unresolved, not UTC.",
                           "commence_time is match start, NOT the signal time.",
                           "Source schema alone cannot verify market, book, horizon, selection or historical rule criteria.",
                           "No retrospective alerts may be promoted into prospective bets."]}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=".")
    p.add_argument("--snapshot",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    result=build(Path(a.root),json.loads(Path(a.snapshot).read_text(encoding="utf-8")))
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"mode":result["mode"],"certified_signals":0,
                      "source_rows":{k:v.get("counts",{}).get("rows",0) for k,v in result["sources"].items()}},ensure_ascii=False))
if __name__=="__main__":main()
