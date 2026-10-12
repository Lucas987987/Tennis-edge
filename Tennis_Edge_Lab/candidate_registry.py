#!/usr/bin/env python3
"""Registre chaîné de découvertes ; gel automatique et test prospectif strict.

La chaîne de hashes est AUDITABLE, pas mathématiquement impossible à
réécrire pour un administrateur Git. La protection GitHub de `main` est requise
pour une garantie organisationnelle supplémentaire.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math, pathlib, os, subprocess, sys
from autoresearch import readjson, safe_row, stats_roi, null_pvalue, frozen_results, segment_catalogue, circuit_name, ROOT

LAB=ROOT/'Tennis_Edge_Lab'
LEDGER=LAB/'registry/candidates.jsonl'

# DSL figé : les règles ne sont JAMAIS reconstruites par la recherche de
# sous-chaînes d'une phrase ou par un eval() arbitraire.
SPECS={
 'circuit ATP principal':{'field':'tour','kind':'circuit','eq':'ATP'},
 'circuit Challenger':{'field':'tour','kind':'circuit','eq':'Challenger'},
 'circuit WTA':{'field':'tour','kind':'circuit','eq':'WTA'},
 'cote 1,20–1,50':{'field':'odd','min':1.2,'max':1.5},
 'cote 1,50–1,80':{'field':'odd','min':1.5,'max':1.8},
 'cote 1,80–2,30':{'field':'odd','min':1.8,'max':2.3},
 'cote 2,30–3,00':{'field':'odd','min':2.3,'max':3.0},
 'cote 3,00–4,00':{'field':'odd','min':3.0,'max':4.0},
 'cote 4,00–8,00':{'field':'odd','min':4.0,'max':8.0},
 'mouvement ≥ 3 %':{'field':'mag','min':3.0},
 'mouvement ≥ 5 %':{'field':'mag','min':5.0},
 'mouvement ≥ 8 %':{'field':'mag','min':8.0},
 'mouvement ≥ 12 %':{'field':'mag','min':12.0},
 'délai 0–4 h':{'field':'lead','min':0.0,'max':240.0},
 'délai 4–8 h':{'field':'lead','min':240.0,'max':480.0},
 'délai 8–24 h':{'field':'lead','min':480.0,'max':1440.0},
 'délai 24–48 h':{'field':'lead','min':1440.0,'max':2880.0},
 'délai ≥ 48 h':{'field':'lead','min':2880.0},
 'Pinnacle ouv. < 1,30':{'field':'pin','max':1.3},
 'Pinnacle ouv. 1,30–1,80':{'field':'pin','min':1.3,'max':1.8},
 'Pinnacle ouv. 1,80–3,00':{'field':'pin','min':1.8,'max':3.0},
 'Pinnacle ouv. ≥ 3,00':{'field':'pin','min':3.0},
 'book unibet':{'field':'book','eq':'unibet'},
 'book bwin':{'field':'book','eq':'bwin'},
 'book betsson':{'field':'book','eq':'betsson'},
 'book bet365':{'field':'book','eq':'bet365'},
 'book betway':{'field':'book','eq':'betway'},
 'book 888sport':{'field':'book','eq':'888sport'},
 'PM avant pari ≥ 60 %':{'field':'polymarket_mid_pre','min':.6},
 'PM spread ≤ 2 pts':{'field':'polymarket_spread_pre','max':.02000001},
 'Kalshi avant pari ≥ 60 %':{'field':'kalshi_mid_pre','min':.6},
 'écart soft vs Pinnacle ≥ 5 %':{'field':'soft_vs_pin_pre_pct','min':5},
 'limite Pinnacle ≥ 300':{'field':'pin_limit_at_decision','min':300},
}
SEGMENTS={
 'Challenger uniquement':{'field':'tour','kind':'circuit','in':['Challenger']},
 'ATP + WTA uniquement':{'field':'tour','kind':'circuit','in':['ATP','WTA']},
 'Exclure les Challengers':{'field':'tour','kind':'circuit','not_in':['Challenger']},
 'ATP uniquement':{'field':'tour','kind':'circuit','in':['ATP']},
 'WTA uniquement':{'field':'tour','kind':'circuit','in':['WTA']},
 'Exclure l’ATP':{'field':'tour','kind':'circuit','not_in':['ATP']},
 'Exclure la WTA':{'field':'tour','kind':'circuit','not_in':['WTA']},
}

def dsha(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf8')).hexdigest()

def check_rule(rule):
    terms=rule.split(' ET ')
    if not 1<=len(terms)<=3:raise ValueError('Nombre de critères illégal')
    if any(t not in SPECS for t in terms):raise ValueError('Critères inconnus : '+repr(terms))
    return [dict(SPECS[t]) for t in terms]

def matches_rule(row,criteria):
    for c in criteria:
        val=circuit_name(row.get('tour')) if c.get('kind')=='circuit' else row.get(c['field'])
        if val is None:return False
        if 'eq' in c and val!=c['eq']:return False
        if 'in' in c and val not in c['in']:return False
        if 'not_in' in c and val in c['not_in']:return False
        if 'min' in c and not val>=c['min']:return False
        if 'max' in c and not val<c['max']:return False
    return True

def read_ledger(path=LEDGER):
    if not pathlib.Path(path).exists():return []
    previous='GENESIS';out=[];ids=set();previous_created=''
    for n,line in enumerate(pathlib.Path(path).read_text(encoding='utf8').splitlines(),1):
        if not line.strip():continue
        try:rec=json.loads(line)
        except json.JSONDecodeError as e:raise ValueError(f'Registre corrompu ligne {n}: {e}')
        observed=rec.get('event_hash');payload={k:v for k,v in rec.items() if k!='event_hash'}
        if rec.get('previous_hash')!=previous or observed!=dsha(payload):raise ValueError(f'Chaîne du registre invalide ligne {n}')
        if rec['candidate_id'] in ids:raise ValueError('ID candidat dupliqué : '+rec['candidate_id'])
        if str(rec.get('created_at','')) < previous_created:raise ValueError('Chronologie du registre invalide')
        previous_created=str(rec.get('created_at',''))
        ids.add(rec['candidate_id']);previous=observed;out.append(rec)
    return out

def candidate_from_research(research):
    props=[]
    for c in research.get('candidates',[]):
        a=c['train'];b=c['test']
        if a['n']<60 or b['n']<35 or a['roi']<=0 or b['roi']<=0:continue
        try:crit=check_rule(c['rule'])
        except ValueError:continue
        props.append({'kind':'market','label':c['rule'],'criteria':crit,'base_hypothesis':None,
            'source_period':research['split']['last_test'],'selection_evidence':{'train':a,'retrospective_test':b},
            'sort_score':min(a['roi'],b['roi'])+math.log1p(b['n'])/10})
    props.sort(key=lambda x:(-x['sort_score'],-x['selection_evidence']['retrospective_test']['n'],x['label']))
    seg=[]
    for c in research.get('hypothesis_circuits',{}).get('historical',[]):
        if c['rule'] not in SEGMENTS or c['n']<30 or c['excluded_n']<10 or c['roi']<=0 or c['lift']<=3:continue
        halves=c.get('first_half') or {};last=c.get('second_half') or {}
        if halves.get('n',0)<15 or last.get('n',0)<15 or (halves.get('roi') or 0)<=0 or (last.get('roi') or 0)<=0:continue
        x={'kind':'hypothesis_segment','label':c['hypothesis']+' — '+c['rule'],
           'criteria':[dict(SEGMENTS[c['rule']])],'base_hypothesis':c['hypothesis'],
           'source_period':c['end_date'],'selection_evidence':{'n':c['n'],'roi':c['roi'],
                    'baseline_roi':c['baseline_roi'],'lift':c['lift'],'first_half':halves,'second_half':last},
           'sort_score':c['lift']+max(0,last['roi'])/10}
        seg.append(x)
    # Empêcher le gel de deux règles logiquement identiques (ATP+WTA / exclure Challenger).
    uniq=[];seen=set()
    for x in sorted(seg,key=lambda v:(-v['sort_score'],v['label'])):
        k=(x['base_hypothesis'],str(x['criteria']))
        if k not in seen:seen.add(k);uniq.append(x)
    return props+uniq

def freeze(research,when=None,ledger=LEDGER):
    when=when or dt.datetime.now(dt.timezone.utc)
    current=read_ledger(ledger)
    firstday=when.date().isoformat(); start=(when.date()+dt.timedelta(days=1)).isoformat()
    known=set(x['candidate_id'] for x in current)
    official={x['code']:{'freeze':x['freeze'],'rule':x['rule']} for x in research.get('frozen_hypotheses',[])}
    raw_path=ROOT/'moves_detail_hist.csv'
    source_hash=hashlib.sha256(raw_path.read_bytes()).hexdigest() if raw_path.exists() else None
    try:commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    except Exception:commit=os.environ.get('GITHUB_SHA')
    proposed=candidate_from_research(research)
    recorded=[]
    for x in proposed:
        signature={'schema':1,'type':x['kind'],'hypothesis':x['base_hypothesis'],'criteria':x['criteria']}
        cid=dsha(signature)[:20]
        if cid in known:continue
        oldhash=current[-1]['event_hash'] if current else 'GENESIS'
        if x['base_hypothesis'] and x['base_hypothesis'] not in official:continue
        manifest={'schema_version':1,'candidate_id':cid,'created_at':when.isoformat(),
           'freeze_date':firstday,'eligible_after':start,'candidate_type':x['kind'],
           'base_hypothesis':x['base_hypothesis'],'label':x['label'],'criteria':x['criteria'],
           'signature':dsha(signature),'source_snapshot_sha256':source_hash,
           'source_commit':commit,'base_definition':official.get(x['base_hypothesis']),
           'last_known_match_date':x['source_period'],'selection_evidence':x['selection_evidence'],
           'status_at_freeze':'piste exploratoire · validation prospective future seulement',
           'previous_hash':oldhash}
        manifest['event_hash']=dsha(manifest)
        current.append(manifest);recorded.append(manifest);known.add(cid)
    if recorded:
        ledger=pathlib.Path(ledger);ledger.parent.mkdir(parents=True,exist_ok=True)
        # append only : aucune réécriture des événements passés
        with ledger.open('a',encoding='utf8') as f:
            for record in recorded:f.write(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n')
        assert len(read_ledger(ledger))==len(current)
    return recorded

def evaluate(research,ledger=LEDGER,root=ROOT):
    frozen=read_ledger(ledger)
    import csv
    moves=root/'moves_detail_hist.csv'
    if not moves.is_file():raise RuntimeError('Source historique des mouvements absente')
    with moves.open(encoding='utf-8-sig',newline='') as f:raw=list(csv.DictReader(f))
    base,qualified=frozen_results(raw)
    baseline={b['code']:(b['freeze'],b['rule']) for b in base}
    rows=[v for r in raw if (v:=safe_row(r))]
    output=[]
    for c in frozen:
        if c['candidate_type']=='hypothesis_segment':
            h=c['base_hypothesis'];pool=qualified.get(h,[])
            if c.get('base_definition') != {'freeze':baseline[h][0],'rule':baseline[h][1]}:
                output.append({'candidate_id':c['candidate_id'],'label':c['label'],'type':c['candidate_type'],
                    'base_hypothesis':h,'freeze_date':c['freeze_date'],'eligible_after':c['eligible_after'],
                    'days':0,'metrics':stats_roi([]),'status':'critère gelé de base MODIFIÉ — évaluation suspendue',
                    'p_nominal':None,'concentration_5_best_percent':None})
                continue
        else:pool=rows
        selected=[];seen=set()
        for r in sorted(pool,key=lambda a:(a['date'],a['uid'])):
            if r['date']<c['eligible_after'] or not matches_rule(r,c['criteria']):continue
            uid=r['uid'] or r['date']+r['tour']
            if uid in seen:continue
            seen.add(uid);selected.append(r)
        metrics=stats_roi(selected,bootstrap=500,seed=int(c['candidate_id'][:7],16))
        ds=len({x['date'] for x in selected});concentration=None
        if metrics['pnl'] and abs(metrics['pnl'])>.01:
            concentration=round(100*sum(sorted((max(0,r['pnl']) for r in selected),reverse=True)[:5])/abs(metrics['pnl']),1)
        output.append({'candidate_id':c['candidate_id'],'label':c['label'],'type':c['candidate_type'],
            'base_hypothesis':c['base_hypothesis'],'freeze_date':c['freeze_date'],
            'eligible_after':c['eligible_after'],'last_observed':selected[-1]['date'] if selected else None,
            'days':ds,'metrics':metrics,'concentration_5_best_percent':concentration,
            'p_nominal':null_pvalue(selected,seed=int(c['candidate_id'][:7],16),iterations=2000) if len(selected)>=10 else None,
            'status':'en attente de matchs futurs'})
    # Holm sur toute la famille des pistes gelées, pas uniquement sur les gagnantes.
    rank=sorted([i for i,c in enumerate(output) if c['p_nominal'] is not None],key=lambda i:output[i]['p_nominal'])
    maxp=0
    for k,i in enumerate(rank):
        maxp=max(maxp,min(1,(len(output)-k)*output[i]['p_nominal']))
        output[i]['p_holm']=round(maxp,4)
    for c in output:
        m=c['metrics']
        if m['n']>=60 and c['days']>=12:
            if (m['ci95'] or [-1e10])[0]>0 and c.get('p_holm',1)<.05:
                c['status']='signal prospectif statistique — audit supplémentaire nécessaire'
            elif m['roi'] is not None and m['roi']<=0:
                c['status']='ne confirme pas · rendement non positif'
            else:c['status']='non concluante statistiquement'
        elif m['n']>0:c['status']='échantillon prospectif insuffisant'
    return {'schema_version':1,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),
            'total_frozen':len(frozen),'ledger_tip':frozen[-1]['event_hash'] if frozen else 'GENESIS',
            'models':output,'validation_minimum':'≥60 matchs distincts, ≥12 jours, IC bootstrap >0 et p Holm <0,05',
            'warning':'Le registre est scellé par hashes et historique Git mais pas inaltérable contre un administrateur avec force-push. Les résultats ne sont calculés que sur les matchs datés au moins du jour suivant le gel.'}

def main():
    global ROOT,LAB,LEDGER
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['freeze','evaluate','verify']);ap.add_argument('--root',default=str(ROOT));ap.add_argument('--asof',default=None)
    a=ap.parse_args();ROOT=pathlib.Path(a.root).resolve();LAB=ROOT/'Tennis_Edge_Lab';LEDGER=LAB/'registry/candidates.jsonl'
    if a.action=='verify':
        print('Registre vérifié :',len(read_ledger(LEDGER)));return
    researchfile=LAB/'live/research.json'
    if not researchfile.exists():raise SystemExit('Faire tourner autoresearch.py avant')
    research=json.loads(researchfile.read_text(encoding='utf8'))
    if research.get('schema_version')!=1 or research.get('row_counts',{}).get('settled_quality_ok',0)<200:raise SystemExit('Research invalide, gel bloqué')
    if a.action=='freeze':
        when=dt.datetime.fromisoformat(a.asof) if a.asof else None
        events=freeze(research,when=when,ledger=LEDGER)
        print('Nouveaux gels :',len(events));[print(' ',x['label'],'à partir du',x['eligible_after']) for x in events]
    result=evaluate(research,ledger=LEDGER,root=ROOT)
    path=LAB/'live/prospective.json';path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    print('Suivi prospectif :',len(result['models']),'pistes,',sum(x['metrics']['n'] for x in result['models']),'résultats post-gel')
if __name__=='__main__':main()
