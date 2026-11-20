import json, pathlib, datetime as dt, importlib.util, collections
def calculate(root,selection):
    path=root/'Tennis_Edge_Lab/bookmakers_sets_v5.py'
    spec=importlib.util.spec_from_file_location('v5',path)
    v5=importlib.util.module_from_spec(spec);spec.loader.exec_module(v5)
    rows,_,_=v5.load_observations(root)
    groups=collections.defaultdict(list)
    for c in selection['candidates']:
        groups[(c['market'],c['book'],c['horizon'],c['selection'])].append(c)
    matched=collections.defaultdict(dict)
    cutoff=dt.datetime.fromisoformat(selection['eligible_after_utc']+'T00:00:00+00:00')
    for r in rows:
        t=v5.parse_time(r.get('decision_ts'))
        if not t or t<cutoff or not r.get('feature_available_by_decision'):continue
        side={'favori':'favorite','outsider':'outsider'}.get(r.get('side_type'))
        key=(r['market'],r['book'],r['horizon'],side)
        candidates=groups.get(key,[])
        if not candidates:continue
        features=dict(v5._criteria(r))
        for c in candidates:
            if all(features.get(x['dimension'])==x['value'] for x in c['criteria']):
                matched[c['id']].setdefault((r.get('fixture_id') or r['uid'],r['market']),r)
    stats={}
    for c in selection['candidates']:
        rs=list(matched[c['id']].values());n=len(rs)
        clv=[r['clv_pct'] for r in rs if isinstance(r.get('clv_pct'),(int,float))]
        stats[c['id']]={'n':n,'roi_pct':round(sum(r['pnl'] for r in rs)/n*100,2) if n else None,'clv_n':len(clv),'clv_mean_pct':round(sum(clv)/len(clv),2) if clv else None}
    return {'schema_version':1,'selection_id':selection['selection_id'],'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'hypotheses':stats}
if __name__=='__main__':
    root=pathlib.Path('.').resolve()
    sel=json.loads((root/'Tennis_Edge_Lab/live/economic_v64.json').read_text())
    result=calculate(root,sel)
    p=root/'Tennis_Edge_Lab/live/prospective_v64.json'
    p.write_text(json.dumps(result,ensure_ascii=False))
    print('Hypothèses suivies :',sum(v['n']>0 for v in result['hypotheses'].values()))
