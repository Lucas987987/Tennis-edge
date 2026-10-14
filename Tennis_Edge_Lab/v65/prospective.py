#!/usr/bin/env python3
"""V6.5 observation-only: prequalified signals, no historical reranking or betting."""
import argparse, datetime as dt, hashlib, json, math
from pathlib import Path

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def parse_time(s):
    if not isinstance(s, str):
        raise ValueError("timestamp must be ISO8601")
    t=dt.datetime.fromisoformat(s.replace("Z","+00:00"))
    if t.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return t.astimezone(dt.timezone.utc)

def valid_number(v):
    return type(v) in (int,float) and math.isfinite(v)

def load_events(path):
    if not Path(path).exists():
        return []
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]

def process(snapshot, events, now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    candidates={c["id"]:c for c in snapshot["candidates"]}
    groups={k:set(v) for k,v in snapshot["tops"].items()}
    eligible=parse_time(snapshot["eligible_after_utc"]+"T00:00:00Z")
    by_id={}
    errors=[]
    for index,event in enumerate(events,1):
        try:
            if not isinstance(event,dict): raise ValueError("not an object")
            required=("event_id","hypothesis_id","fixture_id","signal_at_utc","book","market","odds_at_signal")
            if any(not event.get(k) for k in required): raise ValueError("missing required field")
            eid=str(event["event_id"])
            if eid in by_id:
                if event != by_id[eid]: raise ValueError("conflicting duplicate event_id")
                continue
            hid=event["hypothesis_id"]
            if hid not in candidates: raise ValueError("unknown hypothesis_id")
            c=candidates[hid]
            if event["book"] != c["book"] or event["market"] != c["market"]:
                raise ValueError("market/book mismatch")
            signal=parse_time(event["signal_at_utc"])
            if signal < eligible: raise ValueError("pre-freeze signal")
            if signal > now: raise ValueError("future signal")
            odds=event["odds_at_signal"]
            if not valid_number(odds) or odds<=1: raise ValueError("invalid odds")
            # Only prequalified records; the adapter must attest that ALL V6.4 rules
            # were checked using information available at signal time.
            if event.get("rules_verified_at_signal") is not True:
                raise ValueError("rules not verified at signal time")
            close=event.get("closing_odds")
            result=event.get("result")
            if close is not None and (not valid_number(close) or close<=1):
                raise ValueError("invalid closing odds")
            if result not in (None,"win","loss","void"): raise ValueError("invalid result")
            if (close is not None or result is not None) and not event.get("settled_at_utc"):
                raise ValueError("closing/result requires settled_at_utc")
            if event.get("settled_at_utc"):
                settled=parse_time(event["settled_at_utc"])
                if settled < signal or settled > now: raise ValueError("invalid settlement timestamp")
            by_id[eid]=event
        except (ValueError,TypeError,KeyError) as e:
            errors.append({"line":index,"error":str(e)})
    if errors: raise ValueError(json.dumps(errors,ensure_ascii=False))
    rows=[]
    for group,ids in groups.items():
        chosen=[e for e in by_id.values() if e["hypothesis_id"] in ids]
        settled=[e for e in chosen if e.get("result") in ("win","loss")]
        clvs=[100*(e["odds_at_signal"]/e["closing_odds"]-1) for e in chosen if e.get("closing_odds")]
        profits=[e["odds_at_signal"]-1 if e["result"]=="win" else -1 for e in settled]
        rows.append({"group":group,"signals":len(chosen),"settled":len(settled),
                     "roi_pct":round(100*sum(profits)/len(profits),4) if profits else None,
                     "clv_n":len(clvs),"clv_mean_pct":round(sum(clvs)/len(clvs),4) if clvs else None})
    return {"schema_version":1,"mode":"observation_only","selection_id":snapshot["selection_id"],
            "eligible_after_utc":snapshot["eligible_after_utc"],"event_count":len(by_id),
            "groups":rows,"warning":"Prequalified input only. Not an automatic matching engine. No live betting recommendation."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",required=True)
    p.add_argument("--events",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    result=process(load_json(a.snapshot),load_events(a.events))
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__": main()
