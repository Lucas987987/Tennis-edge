#!/usr/bin/env python3
"""Tennis Edge Lab V3 — reconstruction des matchs et recherche statistique (lecture seule).

Entrée: fichiers publics du dépôt. Sorties UNIQUEMENT dans Tennis_Edge_Lab/:
  live/research.json + live/matches_index.json.

Le moteur ne passe jamais de paris, ne change aucune hypothèse gelée et ne
considère aucune découverte rétrospective comme une stratégie confirmée.
Aucune sélection n'utilise de cotes de clôture ou le résultat futur.
"""
from __future__ import annotations
import collections
import ast
import csv
import datetime as dt
import hashlib
import json
import math
import random
import re
import statistics as stats
import sys
import unicodedata
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if __name__ == '__main__' and len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
DEST = ROOT / 'Tennis_Edge_Lab' / 'live'
NOW = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def readjson(name, default=None):
    path = ROOT / name
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', s)


def key(date, a, b):
    if not date or not a or not b:
        return None
    return str(date)[:10] + '|' + '|'.join(sorted((norm(a), norm(b))))


def firststring(obj, *fields):
    for field in fields:
        if obj.get(field): return str(obj[field])
    return ''


def parseval(v):
    try:
        if v in (None, ''): return None
        x = float(v)
        return x if math.isfinite(x) else None
    except (ValueError, TypeError): return None


def create_match_index():
    # Index déterministe sans rapprochement flou : clef date + paire de joueurs.
    # En cas de résultats contradictoires, marquer le conflit, ne jamais
    # sélectionner arbitrairement le gagnant.
    out = {}
    sources = collections.Counter()
    conflicts = 0
    def put(date, a, b, winner, source, provisional=True, tournament='', fixture='', score=''):
        nonlocal conflicts
        k = key(date,a,b)
        if not k or date[:4] < '2020': return None
        nm = norm(winner)
        if nm and nm not in (norm(a),norm(b)):
            nm = ''  # vainqueur indécidable
        if k not in out:
            out[k] = {'id':k, 'date':date[:10], 'home':a, 'away':b,
                      'tournament': tournament or '', 'winner': None, 'status':'sans résultat',
                      'sources':[], 'fixture_ids':[], 'curve_points':0,'movement_ids':[],
                      'score':score or ''}
        m = out[k]
        if source not in m['sources']:m['sources'].append(source)
        if fixture and fixture not in m['fixture_ids']:m['fixture_ids'].append(fixture)
        if tournament and not m['tournament']:m['tournament']=tournament
        if score and not m['score']:m['score']=score
        if nm:
            old=norm(m['winner'])
            if old and old!=nm:
                if m['status']!='conflit':conflicts+=1
                m['status']='conflit';m['winner']=None
            elif m['status']!='conflit':
                m['winner']=a if nm==norm(a) else b
                if m['status']=='sans résultat':m['status']='provisoire' if provisional else 'résultat vérifié dans la source'
                elif m['status']=='provisoire' and not provisional:m['status']='résultat vérifié dans la source'
        sources[source]+=1
        return k

    derived=readjson('resultats_derived.json',{})
    if isinstance(derived,dict):
        for r in derived.get('results',[]):
            if not isinstance(r,dict):continue
            put(str(r.get('date') or ''),r.get('home_team'),r.get('away_team'),r.get('winner'),
                'resultats_derived',bool(r.get('provisional',True)),r.get('tournament',''),score=r.get('sets',''))
    # Conserver les dates des lignes historiques indépendantes dans l'index.
    moves=[]
    f=ROOT/'moves_detail_hist.csv'
    if f.exists():
        with f.open(encoding='utf-8-sig',newline='') as fh:moves=list(csv.DictReader(fh))
        for r in moves:
            k=put(r.get('date',''),r.get('steame',''),r.get('opp',''),None,'moves_detail_hist',True,r.get('tour',''))
            if k and r.get('uid') and r['uid'] not in out[k]['movement_ids']:out[k]['movement_ids'].append(r['uid'])
    close=readjson('closing_lines.json',{})
    fixtures=readjson('resultats_oddspapi.json',{})
    if not isinstance(close,dict):close={}
    if not isinstance(fixtures,dict):fixtures={}
    closing_with_result=0
    for cid,c in close.items():
        if not isinstance(c,dict):continue
        fid=c.get('fixture_id') or ''
        r=fixtures.get(fid,{}) if fid else {}
        winner=r.get('winner_name') if isinstance(r,dict) else None
        date=c.get('date') or str(c.get('commence_time') or '')[:10]
        k=put(date,c.get('home'),c.get('away'),winner,'closing_lines'+(' + oddspapi' if winner else ''),
              bool(r.get('provisional',True)) if isinstance(r,dict) else True,c.get('tournament',''),fid)
        if not k:continue
        if winner:closing_with_result+=1
        out[k]['curve_points'] += len(c.get('history',[]))
    # matches_oddspapi couvre les matchs futurs, et renseigne des identifiants
    # lorsqu'ils sont connus. Les cotes actuelles n'y constituent PAS des prix
    # de pari historique.
    forthcoming=readjson('matches_oddspapi.json',[])
    if isinstance(forthcoming,list):
        for r in forthcoming:
            if not isinstance(r,dict):continue
            dat=str(r.get('commence_time') or '')[:10]
            k=put(dat,r.get('home_team'),r.get('away_team'),None,'matches_oddspapi',True,r.get('sport_title',''),r.get('id',''))
            if k and r.get('id') in fixtures:
                rec=fixtures[r['id']]
                put(dat,r.get('home_team'),r.get('away_team'),rec.get('winner_name'),'resultats_oddspapi',bool(rec.get('provisional',True)),r.get('sport_title',''),r['id'])
    # Vérifier les règlements de mouvements contre le vainqueur d'une source
    # externe lorsque la paire ET la date correspondent exactement.
    # Ne jamais inventer un match à partir d'un rapprochement approximatif.
    move_result_conflicts=[]
    for r in moves:
        if r.get('steame_gagne') not in ('oui','non'):continue
        k=key(r.get('date',''),r.get('steame',''),r.get('opp',''))
        m=out.get(k)
        if not m or not m['winner'] or m['status']=='conflit':continue
        guessed=r['steame'] if r['steame_gagne']=='oui' else r['opp']
        if norm(m['winner'])!=norm(guessed):
            move_result_conflicts.append({'uid':r.get('uid'),'date':r.get('date'),'match':r.get('steame')+' / '+r.get('opp'),
                                          'winner_source':m['winner'],'winner_movement':guessed})
            m['winner']=None;m['status']='conflit'
            conflicts+=1
    # Autres fixtures Oddspapi sans date connue : conserver leur nombre en
    # inventaire mais ne PAS leur inventer de date pour une jointure.
    matches=sorted(out.values(),key=lambda x:(x['date'],x['id']),reverse=True)
    counts=collections.Counter(m['status'] for m in matches)
    coverage={'derived_rows':len(derived.get('results',[])) if isinstance(derived,dict) else 0,
              'oddspapi_fixtures':len(fixtures),'closing_events':len(close),
              'closing_with_oddspapi_result':closing_with_result,
              'set_results_entries':len(readjson('set_results.json',{})),
              'unified_matches':len(matches),'match_statuses':dict(counts),
              'contradictory_results':conflicts,'movement_result_conflicts':len(move_result_conflicts),'movement_result_conflict_examples':move_result_conflicts[:15],
              'source_entries':dict(sources),
              'warning':'Une ligne provisoire ne constitue pas un règlement officiel. Les fixtures sans date ne sont pas fusionnées par supposition. Les set_results sans date ne sont pas raccordés automatiquement.'}
    return moves, matches, coverage


_external_features=None
_pin_close=None
def _load_local(name):
    import importlib.util
    path=Path(__file__).resolve().parent/name
    spec=importlib.util.spec_from_file_location('tennis_edge_'+name.replace('.py',''),path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
BOOKS=_load_local('books.py')
CLV=_load_local('clv_stats.py')

def external_features():
    global _external_features,_pin_close
    if _external_features is None:
        import gzip
        f=ROOT/'Tennis_Edge_Lab/cache/parts_features.json'
        public=ROOT/'Tennis_Edge_Lab/cache/parts_features_public.json.gz'
        try:
            # Version légère (committée par la tâche quotidienne) en priorité.
            doc=(json.loads(gzip.decompress(public.read_bytes()).decode('utf8'))
                 if public.is_file() else json.loads(f.read_text(encoding='utf8')))
            _external_features=doc.get('features',{})
            _pin_close=doc.get('pinnacle_close_evaluation_only',{})
        except (OSError,ValueError):_external_features={};_pin_close={}
    return _external_features

def pinnacle_close(uid):
    """Clôture Pinnacle (deux côtés) d'un match : mesure APRÈS coup uniquement."""
    external_features()
    return (_pin_close or {}).get(uid)

def safe_row(r):
    date=r.get('date','')[:10];odd=parseval(r.get('entry'));pin=parseval(r.get('pin_open'))
    lead=parseval(r.get('lead_min'));mag=parseval(r.get('mag_cote_pct'));pnl=parseval(r.get('pnl'))
    win=r.get('steame_gagne')
    if not date or not odd or not 1.01<=odd<=100 or not pin or not 1.01<=pin<=100 or lead is None or mag is None or lead<0:
        return None
    if win not in ('oui','non') or pnl is None: return None
    # Les revenus sont recalculés pour rejeter une ligne dont le règlement est incohérent.
    truep=(odd-1) if win=='oui' else -1
    if abs(pnl-truep)>0.011: return None
    v={'uid':r.get('uid',''),'date':date,'tour':r.get('tour',''),'book':r.get('entry_book','').lower(),
            'odd':odd,'pin':pin,'lead':lead,'mag':mag,'pnl':pnl,'win':int(win=='oui'),
            # CLV secondaire : vs dernière cote du même book (clv_book_pct).
            'clv':parseval(r.get('clv_book_pct')),'clv_book':parseval(r.get('clv_book_pct')),
            # CLV brut du CSV : vs clôture Pinnacle AVEC marge (move_audit.py).
            'clv_pin_brut':parseval(r.get('clv_vs_pin_pct'))}
    # CLV principal : vs clôture Pinnacle SANS marge (deux côtés), prix net de commission.
    close=pinnacle_close(v['uid'])
    v['clv_pin']=(BOOKS.clv_pin_pct(v['book'],odd,close['pin_close_side'],close['pin_close_other'])
                  if close else None)
    for field,value in external_features().get(v['uid'],{}).items():
        if field in ('soft_vs_pin_pre_pct','books_quoted_pre_signal','pin_limit_at_decision',
                     'polymarket_mid_pre','polymarket_spread_pre','polymarket_age_min','polymarket_momentum_pts_pre',
                     'kalshi_mid_pre','kalshi_spread_pre','kalshi_age_min','kalshi_momentum_pts_pre'):
            v[field]=value
    return v


def stats_roi(data, bootstrap=0, seed=1):
    n=len(data)
    if not n:return {'n':0,'roi':None,'ci95':None,'pnl':0,'wins':0,'clv_moyen':None,'clv_book_moyen':None,
                     'clv_pin_moyen':None,'clv_pin_ci95':None,'clv_pin_n':0,'sans_cloture_pinnacle':0,'p_clv_pin':None}
    p=[r['pnl'] for r in data];mu=sum(p)/n
    se=stats.stdev(p)/math.sqrt(n) if n>1 else 0
    clvs=[r['clv'] for r in data if r['clv'] is not None]
    ci=[(mu-1.96*se)*100,(mu+1.96*se)*100] if n>1 else None
    if bootstrap and n>1:
        # Bootstrap par JOUR pour limiter la fausse précision des groupes
        # ayant plusieurs matchs exposés à des conditions communes.
        dates=collections.defaultdict(list)
        for r in data:dates[r['date']].append(r['pnl'])
        groups=list(dates.values());rng=random.Random(seed);out=[]
        if len(groups)>=4:
            for _ in range(bootstrap):
                bag=[groups[rng.randrange(len(groups))] for _j in range(len(groups))]
                total=sum(map(sum,bag));cnt=sum(map(len,bag));out.append(100*total/cnt)
            out.sort()
            ci=[out[int(.025*(len(out)-1))],out[int(.975*(len(out)-1))]]
    pin=CLV.summary([r.get('clv_pin') for r in data],[r['date'] for r in data])
    return {'n':n,'roi':round(mu*100,2),'ci95':None if ci is None else [round(x,2) for x in ci],
            'pnl':round(sum(p),2),'wins':sum(r['win'] for r in data),
            # CLV principal (Pinnacle sans marge, IC95 robuste aux grappes par jour).
            'clv_pin_moyen':None if pin['mean_pct'] is None else round(pin['mean_pct'],2),
            'clv_pin_ci95':None if pin['ci95'] is None else [round(x,2) for x in pin['ci95']],
            'clv_pin_n':pin['n'],'sans_cloture_pinnacle':n-pin['n'],'p_clv_pin':pin['p_one_sided'],
            # CLV secondaire : même book.
            'clv_moyen':round(stats.mean(clvs),2) if clvs else None,
            'clv_book_moyen':round(stats.mean(clvs),2) if clvs else None,
            'unique_matches':len(set(r['uid'] for r in data))}


def families():
    return [
        [('circuit ATP principal',lambda r:r['tour'].lower().startswith('atp ') and 'challenger' not in r['tour'].lower()),
         ('circuit Challenger',lambda r:'challenger' in r['tour'].lower()),
         ('circuit WTA',lambda r:r['tour'].lower().startswith('wta '))],
        [('cote 1,20–1,50',lambda r:1.2<=r['odd']<1.5),('cote 1,50–1,80',lambda r:1.5<=r['odd']<1.8),
         ('cote 1,80–2,30',lambda r:1.8<=r['odd']<2.3),('cote 2,30–3,00',lambda r:2.3<=r['odd']<3),
         ('cote 3,00–4,00',lambda r:3<=r['odd']<4),('cote 4,00–8,00',lambda r:4<=r['odd']<8)],
        [('mouvement ≥ 3 %',lambda r:r['mag']>=3),('mouvement ≥ 5 %',lambda r:r['mag']>=5),
         ('mouvement ≥ 8 %',lambda r:r['mag']>=8),('mouvement ≥ 12 %',lambda r:r['mag']>=12)],
        [('délai 0–4 h',lambda r:0<=r['lead']<240),('délai 4–8 h',lambda r:240<=r['lead']<480),
         ('délai 8–24 h',lambda r:480<=r['lead']<1440),('délai 24–48 h',lambda r:1440<=r['lead']<2880),
         ('délai ≥ 48 h',lambda r:r['lead']>=2880)],
        [('Pinnacle ouv. < 1,30',lambda r:r['pin']<1.3),
         ('Pinnacle ouv. 1,30–1,80',lambda r:1.3<=r['pin']<1.8),
         ('Pinnacle ouv. 1,80–3,00',lambda r:1.8<=r['pin']<3),
         ('Pinnacle ouv. ≥ 3,00',lambda r:r['pin']>=3)],
        [('book unibet',lambda r:r['book']=='unibet'),('book bwin',lambda r:r['book']=='bwin'),
         ('book betsson',lambda r:r['book']=='betsson'),('book bet365',lambda r:r['book']=='bet365'),
         ('book betway',lambda r:r['book']=='betway'),('book 888sport',lambda r:r['book']=='888sport')],
        [('PM avant pari ≥ 60 %',lambda r:(r.get('polymarket_mid_pre') or -1)>=.6),
         ('PM spread ≤ 2 pts',lambda r:r.get('polymarket_spread_pre') is not None and r['polymarket_spread_pre']<=.02),
         ('Kalshi avant pari ≥ 60 %',lambda r:(r.get('kalshi_mid_pre') or -1)>=.6),
         ('écart soft vs Pinnacle ≥ 5 %',lambda r:(r.get('soft_vs_pin_pre_pct') or -1e6)>=5),
         ('limite Pinnacle ≥ 300',lambda r:(r.get('pin_limit_at_decision') or -1)>=300)]
    ]


def rule_catalog():
    f=families()
    out=[]
    # Univariés puis interactions de deux familles différentes ; pas de
    # filtrage CLV/close/résultat dans les variables d'entrée.
    for group in f:
        for label,pred in group:out.append((label,(pred,)))
    for i in range(len(f)):
        for j in range(i+1,len(f)):
            for a,p in f[i]:
                for b,q in f[j]:out.append((a+' ET '+b,(p,q)))
    # Interactions à trois dimensions, preregistrées (éviter l'explosion combinatoire).
    for i,j,k in ((0,1,3),(0,2,3),(1,2,3),(2,3,4),(0,1,4),(3,4,5)):
        for aa,pa in f[i]:
            for bb,pb in f[j]:
                for cc,pc in f[k]:out.append((aa+' ET '+bb+' ET '+cc,(pa,pb,pc)))
    return out


def null_pvalue(data, seed, iterations=3000):
    # H0: prix strictement équitables P(win)=1/cote. Ceci n'est PAS une
    # preuve contre un bookmaker avec marge et ne constitue pas une cote
    # sharp dévigée; indication exploratoire seulement.
    rng=random.Random(seed);real=sum(r['pnl'] for r in data);ct=0
    for _ in range(iterations):
        fake=sum((r['odd']-1) if rng.random()<1/r['odd'] else -1 for r in data)
        if fake>=real-1e-12:ct+=1
    return (ct+1)/(iterations+1)


def research(moves):
    if moves and 'mag_cote_pct_POSTHOC' not in moves[0]:
        raise RuntimeError('Amplitude à la détection non certifiée : mag_cote_pct_POSTHOC absent')
    data=[];reject=0
    for r in moves:
        parsed=safe_row(r)
        if parsed:data.append(parsed)
        elif r.get('steame_gagne') in ('oui','non'):reject+=1
    # Refuser de publier une analyse si la couverture historique chute.
    if len(data)<200:raise RuntimeError(f'Stats insuffisantes : seulement {len(data)} mouvements réglés vérifiés')
    data.sort(key=lambda r:(r['date'],r['uid']))
    cut=data[int(len(data)*.70)]['date']
    training=[r for r in data if r['date']<cut]
    testing=[r for r in data if r['date']>=cut]
    if not training or not testing:raise RuntimeError('Échantillon chronologique invalide')
    cand=[]; total=0; eligible=0
    for label,terms in rule_catalog():
        total+=1
        train=[r for r in training if all(t(r) for t in terms)]
        if len(train)<60:continue
        tstat=stats_roi(train)
        # V6.6 : classement sur le CLV Pinnacle (entraînement uniquement) ;
        # le ROI n'est plus qu'une mesure secondaire.
        if tstat['clv_pin_n']<60 or tstat['clv_pin_moyen'] is None or tstat['clv_pin_moyen']<=0:continue
        low,high=tstat['clv_pin_ci95'] or (tstat['clv_pin_moyen'],tstat['clv_pin_moyen'])
        score=tstat['clv_pin_moyen']-1.645*((high-low)/3.92)
        test=[r for r in testing if all(t(r) for t in terms)]
        if len(test)<30:continue
        eligible+=1
        cand.append((score,label,terms,train,test))
    cand.sort(key=lambda v:(-v[0],v[1]))
    chosen=[]; sets=[]
    for v in cand:
        ids=set(r['uid'] for r in v[3])
        if any(len(ids&prev)/len(ids|prev)>.78 for prev in sets):continue
        chosen.append(v);sets.append(ids)
        if len(chosen)>=10:break
    candidates=[]
    for ix,(score,label,terms,tr,te) in enumerate(chosen):
        trstat=stats_roi(tr);teststat=stats_roi(te,bootstrap=1000,seed=301+ix)
        p=null_pvalue(te,seed=2000+ix)
        candidates.append({'id':f'c{ix+1:02d}','rule':label,'train':trstat,'test':teststat,
                           'training_rank_score':round(score,2),'ranking_metric':'CLV Pinnacle (borne basse 90 %, entraînement)',
                           'p_nominal_fair_price':round(p,4),'p_holm_fair_price':None,
                           'p_nominal_clv_pin':teststat['p_clv_pin'],'p_holm_clv_pin':None,
                           'status':'exploratoire','freeze_automatic':False})
    for c,adj in zip(candidates,CLV.holm([c['p_nominal_clv_pin'] for c in candidates])):
        c['p_holm_clv_pin']=None if adj is None else round(adj,4)
    # Correction de Holm sur les pistes évaluées : toutes incluses, même les
    # résultats négatifs, afin de ne pas trier les validations a posteriori.
    order=sorted(range(len(candidates)),key=lambda i:candidates[i]['p_nominal_fair_price'])
    maximum=0
    for rank,i in enumerate(order):
        p=candidates[i]['p_nominal_fair_price']
        maximum=max(maximum,min(1,(len(order)-rank)*p))
        candidates[i]['p_holm_fair_price']=round(maximum,4)
    # Statut V6.6 : décidé sur le CLV Pinnacle du test (Holm sur les pistes évaluées).
    for c in candidates:
        low=(c['test']['clv_pin_ci95'] or [float('-inf')])[0]
        mean=c['test']['clv_pin_moyen']
        if (c['test']['clv_pin_n']>=50 and mean is not None and mean>0 and low>0
                and c['p_holm_clv_pin'] is not None and c['p_holm_clv_pin']<.05):
            c['status']='signal CLV Pinnacle rétrospectif — validation prospective requise'
        elif mean is None or mean<=0:
            c['status']='CLV Pinnacle non répliqué sur période récente'
        else:c['status']='piste non confirmée'
    return {'generated_at':NOW,'schema_version':1,'dataset':'moves_detail_hist.csv',
            'row_counts':{'raw_moves':len(moves),'settled_quality_ok':len(data),'settled_rejected':reject,
                          'train':len(training),'test':len(testing)},
            'split':{'method':'séparation chronologique stricte','test_from':cut,
                     'train_to':training[-1]['date'],'last_test':testing[-1]['date'],
                     'random_split':False},
            'candidates_total_scanned':total,'candidates_train_eligible':eligible,
            'candidates_validation':len(candidates), 'candidates':candidates,
            'baseline':{'train':stats_roi(training),'test':stats_roi(testing,bootstrap=1000,seed=123)},
            'methodology':{'inputs':['cote entrée','prix Pinnacle ouverture','amplitude à la détection','timing','bookmaker','tournoi'],
                           'excluded_from_selection':['cote de clôture','CLV','vainqueur','profit','amplitude POSTHOC'],
                           'ranking':'Le CLV Pinnacle de la période d\'entraînement sert de cible de classement (jamais de variable d\'entrée) ; le test n\'est jamais consulté pour classer.',
                           'clv_primary':'clv_pin = 100 × (cote d\'entrée nette de commission / clôture Pinnacle sans marge − 1). Clôture = dernier point Pinnacle avant le début, deux côtés (cache/parts_features.json). clv_vs_pin_pct du CSV (clôture AVEC marge) conservé comme clv_pin_brut.',
                           'clv_secondary':'clv_book_pct : vs dernière cote du même book.',
                           'unit':'un mouvement par UID et match dans la base actuelle',
                           'inference':'CLV Pinnacle : IC95 et p unilatérale robustes aux grappes par jour, Holm sur les pistes évaluées. ROI (secondaire) : bootstrap par jour et prix équitables p=1/cote, Holm.',
                           'disclaimer':'Exploration sur historique utilisé à répétition ; des filtres positifs ne sont ni une stratégie validée prospectivement ni un profit garanti. Les montants théoriques ne représentent pas nécessairement des cotes jouables.'}}


def frozen_results(rawmoves):
    """Règles historiques du validateur officiel : valeurs extraites au build.

    Si une constante cesse d'être littérale ou disparaît, refuser le rapport :
    une hypothèse gelée ne doit jamais être recalculée avec un seuil deviné.
    """
    target=ROOT/'scripts'/'validation_report.py'
    if not target.exists():raise RuntimeError('validation_report.py absent : impossible de vérifier les critères gelés')
    source=target.read_text(encoding='utf-8')
    tree=ast.parse(source)
    needed={
        'FREEZE_DATE_ROIBANDE','H13_COTE_MIN','H13_COTE_MAX',
        'FREEZE_DATE_AMPLI','H14_MOVE_MIN_PCT','H14_LEAD_MIN','H14_LEAD_MAX',
        'FREEZE_DATE_H15','H15_COTE_MIN','H15_COTE_MAX',
        'FREEZE_DATE_H16','H16_PIN_OPEN_MAX',
        'FREEZE_DATE_H16B','H16B_PIN_OPEN_MIN',
        'FREEZE_DATE_H17','H17_ECART_MIN','H17_ECART_MAX','FREEZE_DATE_H18'
    }
    cfg={}
    for node in tree.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            if node.targets[0].id in needed:cfg[node.targets[0].id]=ast.literal_eval(node.value)
    miss=needed-set(cfg)
    if miss:raise RuntimeError('Constantes officielles introuvables : '+','.join(sorted(miss)))
    rows=[x for r in rawmoves if (x:=safe_row(r))]
    h=cfg
    definitions=[
        ('H13',h['FREEZE_DATE_ROIBANDE'],f"{h['H13_COTE_MIN']:.2f} ≤ cote entrée ≤ {h['H13_COTE_MAX']:.2f}",
         lambda r:h['H13_COTE_MIN']<=r['odd']<=h['H13_COTE_MAX']),
        ('H14',h['FREEZE_DATE_AMPLI'],f"mouvement > {h['H14_MOVE_MIN_PCT']} % · {h['H14_LEAD_MIN']/60:.0f}–{h['H14_LEAD_MAX']/60:.0f} h",
         lambda r:r['mag']>h['H14_MOVE_MIN_PCT'] and h['H14_LEAD_MIN']<=r['lead']<=h['H14_LEAD_MAX']),
        ('H15',h['FREEZE_DATE_H15'],f"{h['H15_COTE_MIN']:.2f} ≤ cote entrée < {h['H15_COTE_MAX']:.2f}",
         lambda r:h['H15_COTE_MIN']<=r['odd']<h['H15_COTE_MAX']),
        ('H16',h['FREEZE_DATE_H16'],f"Pinnacle ouverture < {h['H16_PIN_OPEN_MAX']:.2f}",
         lambda r:r['pin']<h['H16_PIN_OPEN_MAX']),
        ('H16B',h['FREEZE_DATE_H16B'],f"{h['H16B_PIN_OPEN_MIN']:.2f} ≤ Pinnacle ouverture < {h['H16_PIN_OPEN_MAX']:.2f}",
         lambda r:h['H16B_PIN_OPEN_MIN']<=r['pin']<h['H16_PIN_OPEN_MAX']),
        ('H17',h['FREEZE_DATE_H17'],f"{h['H17_ECART_MIN']:.0f} ≤ écart entrée vs Pinnacle ouv. < {h['H17_ECART_MAX']:.0f} %",
         lambda r:h['H17_ECART_MIN']<=100*(r['odd']/r['pin']-1)<h['H17_ECART_MAX']),
        ('H18',h['FREEZE_DATE_H18'],'Intersection stricte H16 et H17',
         lambda r:r['pin']<h['H16_PIN_OPEN_MAX'] and h['H17_ECART_MIN']<=100*(r['odd']/r['pin']-1)<h['H17_ECART_MAX'])
    ]
    out=[]
    qualified={}
    for code,freeze,rule,pred in definitions:
        filtered=[r for r in rows if r['date']>=freeze and pred(r)]
        obj={'code':code,'freeze':freeze,'rule':rule,'metrics':stats_roi(filtered,bootstrap=500,seed=100+len(out)),
             'source':'moves_detail_hist.csv · validation_report.py', 'data_last_date':max([r['date'] for r in filtered],default=None)}
        out.append(obj)
        qualified[code]=filtered
    return out, qualified



# Croisements exploratoires : mêmes critères gelés, seul le circuit varie.
# Ne modifie aucun seuil historique. Les comparaisons sont POST-HOC.
def circuit_name(tour):
    t=str(tour or '').lower()
    if 'challenger' in t:return 'Challenger'
    if t.startswith('wta ') or t=='wta':return 'WTA'
    if t.startswith('atp ') or t=='atp':return 'ATP'
    return 'Autre'


def segment_catalogue():
    return [
        ('Challenger uniquement',lambda c:c=='Challenger'),
        ('ATP + WTA uniquement',lambda c:c in ('ATP','WTA')),
        ('Exclure les Challengers',lambda c:c!='Challenger'),
        ('ATP uniquement',lambda c:c=='ATP'),
        ('WTA uniquement',lambda c:c=='WTA'),
        ('Exclure l’ATP',lambda c:c!='ATP'),
        ('Exclure la WTA',lambda c:c!='WTA'),
    ]


def segment_audit_from_rows(populations, origin, min_n=10):
    """Calcule un tableau de TOUS les croisements, sans filtrer sur leurs gains.

    Un changement de population après avoir vu les résultats est exploratoire.
    Les ratios sans amélioration doivent rester visibles dans le JSON.
    """
    out=[]
    rulebook=segment_catalogue()
    for code, full in populations.items():
        if not full:continue
        base=stats_roi(full)
        for name, rule in rulebook:
            selected=sorted([r for r in full if rule(circuit_name(r['tour']))],key=lambda r:(r['date'],r['uid']))
            if not selected:continue
            metric=stats_roi(selected,bootstrap=350,seed=129+len(out))
            n=len(selected)
            half=n//2
            a=selected[:half]
            b=selected[half:]
            # Les moitiés servent uniquement à visualiser la stabilité,
            # PAS à valider une règle choisie sur l'ensemble des résultats.
            out.append({
                'hypothesis':code,'rule':name,'source':origin,
                'population_n':len(full),'n':n,'excluded_n':len(full)-n,
                'roi':metric['roi'],'baseline_roi':base['roi'],
                'lift':round(metric['roi']-base['roi'],2) if metric['roi'] is not None and base['roi'] is not None else None,
                'profit_units':metric['pnl'],'ci95':metric['ci95'],
                'clv_pin_moyen':metric['clv_pin_moyen'],'clv_pin_ci95':metric['clv_pin_ci95'],
                'clv_pin_n':metric['clv_pin_n'],'sans_cloture_pinnacle':metric['sans_cloture_pinnacle'],
                'first_half':stats_roi(a),'second_half':stats_roi(b),
                'start_date':selected[0]['date'],'end_date':selected[-1]['date'],
                'sample_size_warning':n<30,'provisional':origin=='signaux Telegram (résultats provisoires)',
                'status':'exploratoire — sous-groupe choisi après observation',
            })
    return out


def hypothesis_circuits(official_populations):
    # Base 1 : prédicats et dates de gel extraits de validation_report.py.
    historic=segment_audit_from_rows(official_populations,'historique officiel (moves_detail_hist.csv)')
    # Base 2 : suivi INDÉPENDANT des signaux Telegram ; règlements indicatifs.
    # Ne jamais remplacer les lignes officielles par ces rapprochements.
    dataset=readjson('Tennis_Edge_Lab/data.json',{})
    labrows=dataset.get('rows',[]) if isinstance(dataset,dict) else []
    signal_pops={}
    for tag in ['h13','h15','h16','h16b','h17','h18']:
        records=[]
        for r in labrows:
            if not isinstance(r,dict) or r.get('source')!=tag or not r.get('settled'):continue
            pnl=parseval(r.get('pnl'))
            if pnl is None:continue
            records.append({'uid':str(r.get('uid') or ''),'date':str(r.get('date') or '')[:10],
                            'tour':str(r.get('circuit') or ''),'pnl':pnl,
                            'win':int(pnl>0),'clv':None,'clv_pin':None})
        if records:signal_pops[tag.upper()]=records
    signals=segment_audit_from_rows(signal_pops,'signaux Telegram (résultats provisoires)')
    # Découvertes illustrées dans la navigation : au moins 20 résultats et
    # 10 exclus (sinon une seule observation pourrait créer un faux lift).
    # Ne pas masquer les analyses restantes : elles figurent dans `historical`.
    highlighted=sorted([r for r in historic if r['n']>=20 and r['excluded_n']>=10],
        key=lambda r:(-r['lift'], -r['n'], r['hypothesis'], r['rule']))[:12]
    return {'scanned':len(historic)+len(signals),'historical':historic,
            'provisional_signals':signals,'highlights':highlighted,
            'methodology':{
              'source_of_truth':'validation_report.py pour filtres gelés et dates de gel',
              'selection':'circuits connus avant match; les exclusions sont sélectionnées rétrospectivement',
              'warning':'Les ROI rétrospectifs, même avec IC95 positif, ne démontrent PAS la rentabilité future; corrections multi-tests et enregistrement prospectif nécessaires.',
              'provisional':'Résultats des journaux Telegram rapprochés de manière indicative; ne jamais fusionner aux résultats officiels.',
              'split':'deux moitiés chronologiques descriptives, toutes deux utilisées dans la recherche',
            }}


def main():
    moves,matches,coverage=create_match_index()
    work=research(moves)
    work['match_coverage']=coverage
    work['frozen_hypotheses'], official_populations=frozen_results(moves)
    work['hypothesis_circuits']=hypothesis_circuits(official_populations)
    DEST.mkdir(parents=True,exist_ok=True)
    (DEST/'research.json').write_text(json.dumps(work,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (DEST/'matches_index.json').write_text(json.dumps({'generated_at':NOW,'schema_version':1,'coverage':coverage,'matches':matches},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(f"Recherche V3: {coverage['unified_matches']} matchs indexés, {work['row_counts']['settled_quality_ok']} mouvements réglés, {work['candidates_total_scanned']} filtres examinés, {len(work['candidates'])} pistes affichées")
    print('Croisements hypothèses × circuits :',work['hypothesis_circuits']['scanned'])
    for c in work['hypothesis_circuits']['highlights'][:5]:print(' ',c['hypothesis'],c['rule'],c['n'],'ROI',c['roi'],'Δ',c['lift'])
    for c in work['candidates'][:8]:print(' ',c['rule'],'train',c['train']['roi'],'test',c['test']['roi'],'n',c['test']['n'],'status',c['status'])
    return 0

if __name__=='__main__':sys.exit(main())
