#!/usr/bin/env python3
"""Index des résultats de tennis 2010+ sans rapprochement flou des identités.

Données d'historique souvent avec noms abrégés ; jamais utilisées pour régler
silencieusement un signal contemporain sans correspondance d'identité forte.
"""
import collections,csv,datetime as dt,gzip,json,math,pathlib,statistics

ROOT=pathlib.Path(__file__).resolve().parents[1]
DEST=ROOT/'Tennis_Edge_Lab/cache/archive'

def read(root,fn):
    p=root/'historique'/fn
    if not p.exists():return []
    with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def num(v):
    try:
        x=float(v);return x if math.isfinite(x) and 1<x<100 else None
    except (TypeError,ValueError):return None

def build(root=ROOT):
    root=pathlib.Path(root);a=read(root,'tennis_data.csv.gz');b=read(root,'tennis_data_resultats.csv.gz')
    # Même paire/date peuvent être dans les deux sources; la plus riche l'emporte.
    byid={};conflicts=0
    for batch,source in [(b,'tennis_data_resultats'),(a,'tennis_data')]:
        for r in batch:
            date=r.get('date','')[:10]
            if not date or len(date)!=10 or r.get('vainqueur','')==r.get('perdant',''):continue
            w=r.get('vainqueur','');l=r.get('perdant','')
            key=(date,tuple(sorted([w.lower().strip(),l.lower().strip()])))
            if key in byid:
                old=byid[key]
                if old['winner'].lower().strip()!=w.lower().strip():conflicts+=1;old['status']='conflit'
                if source=='tennis_data':
                    old.update({'surface':r.get('surface') or None,'psw':num(r.get('psw')),'psl':num(r.get('psl')),'circuit':r.get('circuit'), 'tournament':r.get('tournoi','')})
                continue
            byid[key]={'date':date,'winner':w,'loser':l,'circuit':r.get('circuit',''),
                       'tournament':r.get('tournoi',''), 'surface':r.get('surface') or None,
                       'psw':num(r.get('psw')),'psl':num(r.get('psl')), 'source':source,'status':'résultat rapporté par source'}
    shards=collections.defaultdict(list)
    for v in byid.values():shards[v['date'][:4]].append(v)
    DEST.mkdir(parents=True,exist_ok=True)
    for year,rows in shards.items():
        (DEST/f'{year}.json').write_text(json.dumps({'schema_version':1,'year':year,'matches':sorted(rows,key=lambda a:a['date'],reverse=True)},ensure_ascii=False,separators=(',',':')),encoding='utf8')
    # Bilan historique indépendant des stratégies d'alertes: odds de référence non garanties comme jouables.
    summary=[];overall=collections.Counter();group=collections.defaultdict(list)
    for v in byid.values():
        overall['matches']+=1
        if v['status']=='conflit':overall['conflicts']+=1;continue
        if v['psw'] is None or v['psl'] is None:continue
        if v['psw']<=v['psl']:favorite=v['psw'];favorite_won=True
        else:favorite=v['psl'];favorite_won=False
        pnl=(favorite-1) if favorite_won else -1
        base=('ATP' if 'ATP' in v['circuit'].upper() else 'WTA' if 'WTA' in v['circuit'].upper() else 'Autre')
        surface=v['surface'] or 'Inconnue'
        bracket='<1.3' if favorite<1.3 else '1.3-1.6' if favorite<1.6 else '1.6-2' if favorite<2 else '>=2'
        group[(base,surface,bracket)].append((v['date'],pnl,favorite_won))
    for key,arr in group.items():
        arr.sort();cut=dt.date(2024,1,1).isoformat();train=[a for a in arr if a[0]<cut];test=[a for a in arr if a[0]>=cut]
        summary.append({'circuit':key[0],'surface':key[1],'prix_favori':key[2],
                        'count':len(arr),'roi_total':round(100*sum(x[1] for x in arr)/len(arr),2),
                        'before_2024':{'n':len(train),'roi':round(100*sum(x[1] for x in train)/len(train),2) if train else None},
                        'since_2024':{'n':len(test),'roi':round(100*sum(x[1] for x in test)/len(test),2) if test else None}})
    info={'schema_version':1,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),
          'raw_rows':len(a)+len(b),'unique_matches':len(byid),'duplicates':len(a)+len(b)-len(byid),
          'conflicts':conflicts,'years':sorted(shards),'with_reference_odds':sum(len(a) for a in group.values()),
          'historical_segments':sorted(summary,key=lambda x:-x['count']),
          'warning':'Noms abrégés; ne jamais utiliser cette archive pour régler un ticket par similarité approximative. Les prix psw/psl sont des repères historiques, pas une preuve de cotes disponibles au pari.'}
    (DEST/'index.json').write_text(json.dumps(info,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    print(f"Archive historique : {len(byid)} rencontres, {len(shards)} années, {conflicts} conflits")
    return info
if __name__=='__main__':build()
