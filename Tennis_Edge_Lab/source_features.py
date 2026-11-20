#!/usr/bin/env python3
"""Index incrémental des partitions bookmakers, Polymarket et Kalshi.

Les snapshots ne sont candidats à l'analyse que lorsque `tick.ts <= instant_de_detection`.
Le programme ne publie jamais les ticks individuels : seules des features
agrégées et auditables sont conservées dans cache/parts_features.json.
"""
from __future__ import annotations
import argparse, collections, csv, datetime as dt, gzip, hashlib, json, math, pathlib, subprocess, sys
from source_catalog import main as source_catalog

ROOT=pathlib.Path(__file__).resolve().parents[1]
# V6.6 : version du cache par partition. 2 = ajoute la clôture Pinnacle des
# deux côtés (mesure d'évaluation uniquement, jamais une variable d'entrée).
CACHE_VERSION=2
PIN_CLOSE_MAX_GAP_SEC=1800

def num(v):
    try:
        f=float(v)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):return None

def timestamp(v):
    if not v:return None
    try:return dt.datetime.fromisoformat(str(v).replace('Z','+00:00')).replace(tzinfo=None)
    except (TypeError,ValueError):return None

def epoch(v):
    d=timestamp(v)
    return (d-dt.datetime(1970,1,1)).total_seconds() if d else None

def blob_oids(root):
    try:
        r=subprocess.run(['git','ls-files','-s','--','parts'],cwd=root,capture_output=True,check=True)
        return {line.split('\t',1)[1]:line.split()[1] for line in r.stdout.decode().splitlines() if '\t' in line}
    except Exception:return {}

def category(path):
    s=path.lower().split('/')[-1]
    if s.startswith('hist_book_'):return 'book'
    if s.startswith(('pm_ticks_','polymarket_')):return 'polymarket'
    if s.startswith(('kx_ticks_','kalshi_')):return 'kalshi'
    return 'other'

def readlines(path):
    opener=gzip.open if str(path).endswith('.gz') else open
    with opener(path,'rt',encoding='utf-8',errors='replace') as f:
        for line in f:
            if line.strip():yield line

def load_moves(root):
    path=root/'moves_detail_hist.csv'
    if not path.exists():raise RuntimeError('moves_detail_hist.csv introuvable')
    with path.open(encoding='utf-8-sig',newline='') as f:r=list(csv.DictReader(f))
    out={}
    for x in r:
        uid=x.get('uid')
        if not uid:continue
        lead=num(x.get('lead_min'))
        if lead is None or lead<0:continue
        out[uid]={'lead_min':lead,'player':x.get('steame',''),'opponent':x.get('opp',''),
                  'date':str(x.get('date',''))[:10], 'book':x.get('entry_book','')}
    return out

def normalize_name(v):
    import unicodedata,re
    return re.sub('[^a-z0-9]+','',unicodedata.normalize('NFKD',str(v or '')).encode('ascii','ignore').decode().lower())

def read_cached(root):
    fn=root/'Tennis_Edge_Lab/cache/parts_features.json'
    try:return json.loads(fn.read_text(encoding='utf8'))
    except (OSError,json.JSONDecodeError):return {}

def make_anchor(known,starts):
    for uid,start in starts.items():
        if uid not in known:continue
        ts=epoch(start)
        if ts is not None:
            known[uid]['decision_ts']=ts-known[uid]['lead_min']*60

def get_part_files(root):
    p=root/'parts'
    return sorted((f for f in p.rglob('*') if f.is_file() and (str(f).endswith('.jsonl.gz') or str(f).endswith('.jsonl'))),key=str) if p.exists() else []

def _last_before(points,limit):
    best=None
    for pt in points or []:
        if not isinstance(pt,(list,tuple)) or len(pt)<2:continue
        t=epoch(pt[0]);v=num(pt[1])
        if t is None or v is None or v<=1 or t>=limit:continue
        if best is None or t>best[0]:best=(t,v)
    return best

def process_hist(path,moves,starts,conflicts=None):
    record=0;invalid=0;found=0;quotes={};sides={};pin_close={}
    if conflicts is None:conflicts=set()
    for line in readlines(path):
        record+=1
        try:x=json.loads(line)
        except json.JSONDecodeError:invalid+=1;continue
        if not isinstance(x,dict):continue
        uid=x.get('uid')
        if uid not in moves:continue
        start=x.get('commence_time')
        if start and uid in starts and epoch(start) is not None and epoch(starts[uid]) is not None and abs(epoch(start)-epoch(starts[uid]))>1800:
            conflicts.add(uid)
        if start and uid not in starts:starts[uid]=start
        match=moves[uid]
        if start is None:continue
        ts=epoch(start)
        if ts is None:continue
        deadline=ts-match['lead_min']*60
        # Les prévisions se fondent sur les quotes effectivement publiées avant l'alerte.
        side='home' if normalize_name(match['player'])==normalize_name(x.get('home')) else ('away' if normalize_name(match['player'])==normalize_name(x.get('away')) else None)
        if not side:continue
        sides[uid]=side
        if str(x.get('book','')).lower()=='pinnacle':
            # Clôture = dernier point strictement avant le début, deux côtés.
            # Sert UNIQUEMENT à mesurer le CLV (après coup), jamais de filtre.
            other='away' if side=='home' else 'home'
            cs=_last_before(x.get(side+'_curve'),ts);co=_last_before(x.get(other+'_curve'),ts)
            if cs and co and abs(cs[0]-co[0])<=PIN_CLOSE_MAX_GAP_SEC:
                prev=pin_close.get(uid)
                if prev is None or cs[0]>prev['time']:
                    pin_close[uid]={'time':cs[0],'side_close':cs[1],'other_close':co[1],'deadline':deadline}
        pts=x.get(side+'_curve',[]) or []
        quote=None
        for pt in pts:
            if not isinstance(pt,(list,tuple)) or len(pt)<2:continue
            t=epoch(pt[0]);v=num(pt[1]);limit=num(pt[2]) if len(pt)>2 else None
            if t is None or v is None or v<=1 or t>deadline:continue
            if quote is None or t>quote[0]:quote=(t,v,limit)
        if quote is None:continue
        book=str(x.get('book','')).lower()
        if not book:continue
        key=uid+'|'+book
        if key not in quotes or quote[0]>quotes[key]['time']:
            quotes[key]={'time':quote[0],'odds':quote[1],'limit':quote[2],'book':book,'uid':uid}
        found+=1
    return {'records':record,'invalid':invalid,'matched':found,'quotes':quotes,'sides':sides,'pin_close':pin_close}

def process_ticks(path,moves,side_maps,cat):
    record=0;invalid=0;found=0;quotes={}
    for line in readlines(path):
        record+=1
        try:x=json.loads(line)
        except json.JSONDecodeError:invalid+=1;continue
        if not isinstance(x,dict):continue
        uid=x.get('local_uid')
        m=moves.get(uid)
        if m is None or 'decision_ts' not in m:continue
        if cat=='polymarket' and x.get('market_type') not in ('match','h2h','moneyline'):continue
        if cat=='kalshi' and 'SET' in str(x.get('event_ticker','')).upper():continue
        side=side_maps.get(uid)
        if not side or str(x.get('local_side','')).lower()!=side:continue
        t=epoch(x.get('ts'))
        if t is None or t>m['decision_ts']:continue
        mid=num(x.get('mid'));spread=num(x.get('spread'))
        if mid is None or not 0<=mid<=1:continue
        label=uid
        prev=quotes.get(label)
        if prev is None:quotes[label]={'uid':uid,'time':t,'first_time':t,'mid':mid,'first_mid':mid,'spread':spread,'matched_ticks':1}
        else:
            prev['matched_ticks']+=1
            if t<prev['first_time']:prev['first_time']=t;prev['first_mid']=mid
            if t>=prev['time']:prev['time']=t;prev['mid']=mid;prev['spread']=spread
        found+=1
    return {'records':record,'invalid':invalid,'matched':found,'quotes':quotes}

PUBLIC='Tennis_Edge_Lab/cache/parts_features_public.json.gz'

_BOOKS=None
def _books():
    global _BOOKS
    if _BOOKS is None:
        import importlib.util
        path=pathlib.Path(__file__).resolve().parent/'books.py'
        spec=importlib.util.spec_from_file_location('tennis_edge_books_sf',path)
        _BOOKS=importlib.util.module_from_spec(spec);spec.loader.exec_module(_BOOKS)
    return _BOOKS

def write_public(root,summary):
    """Version légère committée chaque jour (sans le cache par partition, ~100 Ko).

    Lue par autoresearch.py dans le déploiement horaire, qui n'a pas parts/.
    Écrite seulement si le contenu change (mtime gzip fixé à 0).
    """
    public={k:summary[k] for k in ('schema_version','cache_version','movement_sha','features',
            'eligible_matches','input_count','pinnacle_close_evaluation_only','causality','warning')
            if k in summary}
    raw=json.dumps(public,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode('utf8')
    path=pathlib.Path(root)/PUBLIC
    try:
        if gzip.decompress(path.read_bytes())==raw:return
    except (OSError,EOFError):pass
    import io
    buffer=io.BytesIO()
    with gzip.GzipFile(fileobj=buffer,mode='wb',mtime=0) as stream:stream.write(raw)
    path.write_bytes(buffer.getvalue())

def build(root=ROOT, max_files=None):
    root=pathlib.Path(root)
    moves=load_moves(root)
    cache=read_cached(root)
    blob=blob_oids(root)
    # La clé de cache inclut les heures d'entrée. Sans cela, une modification
    # de lead_min pourrait invalider tous les filtres "connus avant le pari".
    raw=(root/'moves_detail_hist.csv').read_bytes()
    movement_sha=hashlib.sha256(raw).hexdigest()
    reused=0;fresh=0
    oldfiles=cache.get('files',{}) if (cache.get('movement_sha')==movement_sha
                                      and cache.get('cache_version')==CACHE_VERSION) else {}
    files=get_part_files(root)
    if max_files is not None:files=files[:max_files]
    starts={}
    conflicts=set(cache.get('start_time_conflicts',[])) if oldfiles else set()
    # Si présents, les horaires match sont également dans les fixtures actuels.
    fixtures=root/'matches_oddspapi.json'
    if fixtures.is_file():
        try:
            for f in json.loads(fixtures.read_text()):
                uid=str(f.get('uid') or '')
                if uid in moves and f.get('commence_time'):starts[uid]=f['commence_time']
        except (ValueError,TypeError):pass
    cachefiles={}
    # Premier passage hist_book: donne le début du match et les quotes à l'instant d'entrée.
    for path in files:
        rel=str(path.relative_to(root));cat=category(rel)
        if cat!='book':continue
        oid=blob.get(rel) or f'{path.stat().st_size}:{path.stat().st_mtime_ns}'
        old=oldfiles.get(rel)
        if old and old.get('oid')==oid:
            obs=old['summary'];reused+=1
            for uid,start in old.get('starts',{}).items():starts.setdefault(uid,start)
        else:
            prior=set(starts)
            obs=process_hist(path,moves,starts,conflicts);fresh+=1
        # Bâtir une correspondance start fiable même si la partition est réutilisée.
        cachefiles[rel]={'oid':oid,'category':cat,'summary':obs}
        # NOTE : commence_time disponible par les fichiers bruts (dès la première lecture).
    # Réutilisation du cache des horaires issus de chaque partition historique.
    if oldfiles and cache.get('starts'):
        for uid,t in cache['starts'].items():starts.setdefault(uid,t)
    make_anchor(moves,starts)
    side_maps={}
    for rec in cachefiles.values():
        if rec['category']=='book':side_maps.update(rec['summary'].get('sides',{}))
    # UID est stocké chronologiquement avec ordre alphabétique, mais pas un
    # indicateur home/away. La seule source autorisée ici est le fixture.
    if fixtures.is_file():
        try:
            for f in json.loads(fixtures.read_text()):
                uid=f.get('uid')
                if uid not in moves:continue
                p=normalize_name(moves[uid]['player'])
                side_maps[uid]='home' if p==normalize_name(f.get('home_team')) else ('away' if p==normalize_name(f.get('away_team')) else '')
        except (ValueError,TypeError):pass
    # Pour le tick historique, seul le côté issu d'une source structurée est utilisé.
    # Un fichier dépourvu de local_side vérifié reste catalogué, non joint.
    for path in files:
        rel=str(path.relative_to(root));cat=category(rel)
        if cat in ('book','other'):
            if cat=='other':cachefiles[rel]={'oid':blob.get(rel),'category':cat,'summary':{'records':None,'matched':0,'invalid':0,'quotes':{}}}
            continue
        oid=blob.get(rel) or f'{path.stat().st_size}:{path.stat().st_mtime_ns}'
        old=oldfiles.get(rel)
        # Quand le mapping du côté peut changer, hash inputs exacts.
        sidesig=hashlib.sha256(json.dumps(side_maps,sort_keys=True).encode()).hexdigest()
        if old and old.get('oid')==oid and old.get('sidesig')==sidesig:
            obs=old['summary'];reused+=1
        else:
            obs=process_ticks(path,moves,side_maps,cat);fresh+=1
        cachefiles[rel]={'oid':oid,'category':cat,'summary':obs,'sidesig':sidesig}
    complete=collections.Counter()
    permatch={}
    pin_close={}
    for rec in cachefiles.values():
        if rec['category']!='book':continue
        for uid,obs in (rec['summary'].get('pin_close') or {}).items():
            prev=pin_close.get(uid)
            if prev is None or obs['time']>prev['time']:pin_close[uid]=obs
    for path,rec in cachefiles.items():
        x=rec['summary'];cat=rec['category'];complete[cat+'_files']+=1
        complete[cat+'_rows']+=x.get('records') or 0
        complete[cat+'_matched_pre_signal_ticks']+=x.get('matched') or 0
        for obs in x.get('quotes',{}).values():
            uid=obs['uid'];m=permatch.setdefault(uid,{})
            if cat=='book':
                key='books';d=m.setdefault(key,{})
                name=obs['book'];prev=d.get(name)
                if prev is None or obs['time']>prev['time']:d[name]=obs
            else:
                prev=m.get(cat)
                if prev is None or obs['time']>prev['time']:m[cat]=obs
    features={}
    for uid,m in permatch.items():
        if uid in conflicts or 'decision_ts' not in moves[uid]:continue
        row={'uid':uid,'decision_ts':moves[uid]['decision_ts']}
        books=m.get('books',{})
        if books:
            p=books.get('pinnacle');b=max((v for k,v in books.items() if k!='pinnacle'),key=lambda v:v['odds'],default=None)
            if p:row.update({'pin_at_decision':p['odds'],'pin_limit_at_decision':p.get('limit')})
            if p and b:row['soft_vs_pin_pre_pct']=round(100*(b['odds']/p['odds']-1),4)
            row['books_quoted_pre_signal']=len(books)
        for cat in ('polymarket','kalshi'):
            if cat in m:
                x=m[cat]
                age=(row['decision_ts']-x['time'])/60
                row[cat+'_mid_pre']=x['mid']
                row[cat+'_spread_pre']=x['spread']
                row[cat+'_age_min']=round(age,2)
                row[cat+'_momentum_pts_pre']=round(100*(x['mid']-x['first_mid']),3)
        features[uid]=row
    evaluation_only={}
    for uid,obs in pin_close.items():
        if uid in conflicts or uid not in moves:continue
        # La clôture doit être postérieure à la décision, sinon ce n'est pas une clôture.
        if obs['time']<=obs['deadline']:continue
        # Cote juste via le référentiel unique (méthode puissance).
        evaluation_only[uid]={'pin_close_side':obs['side_close'],'pin_close_other':obs['other_close'],
                              'pin_fair_close':round(_books().fair_close(obs['side_close'],obs['other_close']),5)}
    summary={'schema_version':1,'cache_version':CACHE_VERSION,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),
             'movement_sha':movement_sha,'files':cachefiles,'starts':starts,'start_time_conflicts':sorted(conflicts),
             'stats':dict(complete),'features':features,'eligible_matches':len(features),
             # Mesures APRÈS coup (clôture) : jamais lues comme variables d'entrée.
             'pinnacle_close_evaluation_only':evaluation_only,
             'input_count':len(files),'fresh_files':fresh,'reused_files':reused,
             'causality':'toutes les quotes retenues ont ts <= début du match - lead_min ; si heure/côté manquent, pas de feature',
             'warning':'Les sources sans UID + horodatage + côté vérifié ne sont pas exploitées comme prédicteurs. Les prix après signal sont exclus.'}
    fn=root/'Tennis_Edge_Lab/cache/parts_features.json';fn.parent.mkdir(parents=True,exist_ok=True)
    fn.write_text(json.dumps(summary,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    write_public(root,summary)
    source_catalog(root,root/'Tennis_Edge_Lab/cache/source_catalog.json')
    print(f"Partitions indexées {len(cachefiles)} · fraîches {fresh} · réutilisées {reused} · matches comparables avant signal {len(features)}")
    return summary
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',nargs='?',default=str(ROOT));ap.add_argument('--max-files',type=int)
    a=ap.parse_args();build(a.root,a.max_files)
