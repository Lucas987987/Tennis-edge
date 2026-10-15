#!/usr/bin/env python3
"""V6.5.1 read-only audit of actual signal sources; never guesses hypothesis matches."""
import argparse, collections, csv, json, pathlib
import importlib.util as _ilu, pathlib as _pl
_spec = _ilu.spec_from_file_location("clv_source", _pl.Path(__file__).resolve().parent.parent / "clv_source.py")
clv_source = _ilu.module_from_spec(_spec); _spec.loader.exec_module(clv_source)   # clv_history partitionné (15/10/2026)
SOURCES=("odds_alerts_log.jsonl","clv_history.jsonl","moves_detail_hist.csv",
         "set_results.json","h16_signal_log.jsonl","h17_signal_log.jsonl",
         "Tennis_Edge_Lab/v65/selection_v64_frozen.json")
def inspect(path):
    if not clv_source.exists(path): return {"exists":False}
    obj={"exists":True,"bytes":clv_source.total_bytes(path)}
    try:
        if path.suffix==".csv":
            with path.open(encoding="utf-8-sig",newline="") as f:
                r=csv.DictReader(f);obj["fields"]=r.fieldnames or []
                obj["rows"]=sum(1 for _ in r)
        elif path.suffix==".jsonl":
            keys=collections.Counter()
            with clv_source.open_text(path) as f:
                for line in f:
                    if line.strip():
                        row=json.loads(line)
                        if isinstance(row,dict):keys.update(row.keys())
            obj["fields"]=sorted(keys);obj["rows"]=max(keys.values(),default=0)
        else:
            data=json.loads(path.read_text(encoding="utf-8"))
            obj["type"]=type(data).__name__
            obj["fields"]=sorted(data.keys()) if isinstance(data,dict) else []
            obj["rows"]=len(data.get("candidates",[])) if isinstance(data,dict) else len(data)
    except (ValueError,UnicodeError,OSError) as e:
        obj["error"]=str(e)
    return obj
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",default=".")
    p.add_argument("--output",required=True);a=p.parse_args()
    root=pathlib.Path(a.root).resolve()
    report={"status":"schema_audit_only","sources":{name:inspect(root/name) for name in SOURCES},
            "note":"No raw events, names, odds or player data exported; keys and counts only."}
    dest=pathlib.Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v.get("rows",0) for k,v in report["sources"].items()}))
if __name__=="__main__":main()
