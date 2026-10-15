#!/usr/bin/env python3
"""V6.5.4: fail-closed V6.4 rule matcher for independently proven live snapshots.
No source collector, no historic replay, no result-informed selection, no bets.
"""
import argparse, datetime as dt, hashlib, json, math, re
from pathlib import Path

DIMENSIONS={'tranche_cote':'odds','sens_mouvement':'direction','marge':'margin_pct',
 'fraîcheur_cote':'freshness_min','amplitude_mouvement':'amplitude_pct',
 'circuit':'circuit','limite':'limit','ecart_pinnacle':'pinnacle_gap_pct'}
MEASURES=('odds','margin_pct','freshness_min','amplitude_pct','limit','pinnacle_gap_pct')

def time_utc(v):
    if not isinstance(v,str): raise ValueError('timestamp_missing')
    try: t=dt.datetime.fromisoformat(v.replace('Z','+00:00'))
    except ValueError: raise ValueError('timestamp_invalid')
    if t.tzinfo is None: raise ValueError('timestamp_timezone_missing')
    return t.astimezone(dt.timezone.utc)

def number(v):return type(v) in (float,int) and math.isfinite(v)

def criterion(dimension, label, metrics):
    if dimension not in DIMENSIONS or not isinstance(label,str):return False
    field=DIMENSIONS[dimension];v=metrics.get(field)
    if dimension in ('circuit','sens_mouvement'):
        if not isinstance(v,str):return False
        return (v==label if dimension=='circuit' else {'cote en hausse':'up','cote en baisse':'down','stable':'stable'}.get(label)==v)
    if not number(v):return False
    if dimension in ('tranche_cote','limite','fraîcheur_cote','amplitude_mouvement','marge','ecart_pinnacle'):
        # Labels are exactly the frozen V6.4 bins; unknown labels fail closed.
        values=re.findall(r'\d+(?:,\d+)?',label)
        nums=[float(x.replace(',','.')) for x in values]
        if '≤' in label and '<' in label and len(nums)==2:return nums[0]<=v<nums[1]
        if '≥' in label and len(nums)==1:return v>=nums[0]
        if '<' in label and len(nums)==1:return v<nums[0]
    return False

def evaluate(snapshot, observations, now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    cutoff=time_utc(snapshot['eligible_after_utc']+'T00:00:00Z')
    candidates=snapshot['candidates']; seen=set(); matches=[]; rejected=[]
    for idx,obs in enumerate(observations,1):
        try:
            required=('observation_id','fixture_id','market','book','horizon','selection',
                      'observed_at_utc','match_starts_at_utc','source','metrics','field_observed_at_utc')
            if not isinstance(obs,dict) or any(k not in obs for k in required):raise ValueError('required_fields_missing')
            if obs['observation_id'] in seen:raise ValueError('duplicate_observation_id')
            seen.add(obs['observation_id'])
            if not all(isinstance(obs[k],str) and obs[k].strip() for k in ('observation_id','fixture_id','market','book','horizon','selection','source')):
                raise ValueError('invalid_identity')
            if obs['market'] not in ('match','set1','set2') or obs['selection'] not in ('favorite','outsider'):
                raise ValueError('unsupported_market_or_selection')
            observed=time_utc(obs['observed_at_utc']);starts=time_utc(obs['match_starts_at_utc'])
            if not cutoff<=observed<=now or not observed<starts:raise ValueError('outside_prospective_window')
            if obs.get('source_kind')!='bookmaker_quote_snapshot' or obs.get('verified_source') is not True:
                raise ValueError('source_not_verified')
            metrics=obs['metrics']; times=obs['field_observed_at_utc']
            if not isinstance(metrics,dict) or not isinstance(times,dict):raise ValueError('metrics_or_evidence_missing')
            if not number(metrics.get('odds')) or metrics['odds']<=1:raise ValueError('odds_invalid')
            if not number(metrics.get('minutes_to_start')) or metrics['minutes_to_start']<0:raise ValueError('horizon_unverified')
            if abs((starts-observed).total_seconds()/60-metrics['minutes_to_start'])>1:raise ValueError('horizon_mismatch')
            if not isinstance(obs.get('horizon_verified'),bool) or not obs['horizon_verified']:
                raise ValueError('horizon_unverified')
            # Never assume that historical labels 10m,1h,6h,24h imply a specific
            # exact live timing: source must explicitly attest its V6.1 bucket.
            if obs.get('market_verified') is not True or obs.get('selection_verified') is not True:
                raise ValueError('market_or_selection_unverified')
            for key in metrics:
                if key not in times:raise ValueError('field_timestamp_missing:'+key)
                if time_utc(times[key])>observed:raise ValueError('future_feature:'+key)
            if obs.get('uses_match_result') is True or obs.get('uses_closing_odds') is True:
                raise ValueError('leakage')
            hits=[]
            for c in candidates:
                if any(obs[k]!=c.get(k) for k in ('market','book','horizon','selection')):continue
                if all(criterion(x['dimension'],x['value'],metrics) for x in c['criteria']):hits.append(c['id'])
            for hid in hits:
                matches.append({'observation_id':obs['observation_id'],'fixture_id':obs['fixture_id'],
                                'hypothesis_id':hid,'market':obs['market'],'book':obs['book'],
                                'observed_at_utc':obs['observed_at_utc'],'odds_at_signal':metrics['odds'],
                                'status':'provisional_rule_match_not_certified_bet'})
        except (ValueError,TypeError,KeyError) as exc:
            rejected.append({'line':idx,'reason':str(exc)})
    return {'schema_version':1,'mode':'provisional_evidence_matcher','selection_id':snapshot['selection_id'],
            'observations':len(observations),'provisional_matches':len(matches),
            'certified_bets':0,'matches':matches,'rejected':rejected,
            'warning':'No automatic collection, no persisted signals, no validated future ROI/CLV. Only independently verified snapshot input.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--observations',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    snapshot=json.loads(Path(a.snapshot).read_text(encoding='utf-8'))
    observations=[json.loads(line) for line in Path(a.observations).read_text(encoding='utf-8').splitlines() if line.strip()]
    report=evaluate(snapshot,observations)
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('observations','provisional_matches','certified_bets')},ensure_ascii=False))
if __name__=='__main__':main()
