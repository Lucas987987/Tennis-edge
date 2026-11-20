#!/usr/bin/env python3
"""V6.5.2: conservative, read-only V6.4 rule compatibility diagnostic.
Does NOT certify signals, emit bets, or rewrite frozen hypotheses.
"""
import argparse, collections, datetime as dt, json, pathlib
ALERT_FIELDS={"uid","home","away","commence_time","logged_at","mins_before",
              "amplitude_pct","mv_home_pct","mv_away_pct","o_home_first",
              "o_away_first","o_home_last","o_away_last","tournament","niveau",
              "n_points","sport_key"}
# These fields are intentionally NOT equivalent to the historical V6.1 dimensions.
# Only exact, proven matches may be declared supported.
SUPPORTED_DIMENSIONS=frozenset()

def inspect(snapshot, rows, cutoff=None):
    cutoff=cutoff or snapshot["eligible_after_utc"]
    by_market=collections.Counter()
    reasons=collections.Counter()
    observed=collections.Counter()
    for row in rows:
        try:
            stamp=row.get("logged_at")
            if not isinstance(stamp,str):raise ValueError("missing_logged_at")
            parsed=dt.datetime.fromisoformat(stamp.replace("Z","+00:00"))
            if parsed.tzinfo is None:raise ValueError("timezone_missing")
            if parsed.astimezone(dt.timezone.utc).date().isoformat()<cutoff:
                reasons["before_freeze"]+=1;continue
            observed["post_freeze_alerts"]+=1
            if not row.get("uid") or not row.get("home") or not row.get("away"):
                reasons["identity_incomplete"]+=1
        except (ValueError,TypeError,AttributeError) as exc:
            reasons[str(exc) if str(exc) in ("missing_logged_at","timezone_missing") else "invalid_timestamp"]+=1
    candidate_rows=[]
    for c in snapshot["candidates"]:
        by_market[c["market"]]+=1
        missing=[x["dimension"] for x in c["criteria"] if x["dimension"] not in SUPPORTED_DIMENSIONS]
        # Even criteria-free records require book, horizon, selection and market proofs
        missing+=["book_at_signal","horizon_at_signal","selection_at_signal","market_at_signal"]
        missing=sorted(set(missing))
        reasons["hypotheses_unverifiable"]+=1
        candidate_rows.append({"hypothesis_id":c["id"],"market":c["market"],"book":c["book"],
                               "unverified_dimensions":missing,"status":"blocked"})
    return {"schema_version":1,"mode":"compatibility_audit_only",
            "selection_id":snapshot["selection_id"],"eligible_after_utc":cutoff,
            "historical_hypotheses":len(candidate_rows),
            "by_market":dict(by_market),"alert_rows":len(rows),
            "post_freeze_alert_rows":observed["post_freeze_alerts"],
            "eligible_signals":0,"blocked_hypotheses":len(candidate_rows),
            "reasons":dict(reasons),"candidates":candidate_rows,
            "warning":"NO rule verified. No betting signals generated. Missing book/horizon/market/selection evidence."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",required=True)
    p.add_argument("--alerts",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    snapshot=json.loads(pathlib.Path(a.snapshot).read_text(encoding="utf-8"))
    rows=[]
    # 16/10/2026 : odds_alerts_log.jsonl peut être découpé par mois (clv_source).
    import importlib.util as _ilu
    _sp=_ilu.spec_from_file_location("clv_source",pathlib.Path(__file__).resolve().parent.parent/"clv_source.py")
    _cs=_ilu.module_from_spec(_sp);_sp.loader.exec_module(_cs)
    with _cs.open_text(pathlib.Path(a.alerts)) as f:
        for line in f:
            if line.strip():rows.append(json.loads(line))
    result=inspect(snapshot,rows)
    out=pathlib.Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("historical_hypotheses","alert_rows","post_freeze_alert_rows","eligible_signals","blocked_hypotheses")}))
if __name__=="__main__":main()
