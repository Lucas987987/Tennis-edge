#!/usr/bin/env python3
"""Tennis Edge Lab V1: réimporte les données locales depuis l'archive source.
Aucun réseau. Ne modifie pas le dépôt Tennis Edge.
"""
import csv, json, zipfile, io, sys, os, re, unicodedata, datetime, statistics, collections, hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parent
ARCHIVE=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'Tennis-edge-main.zip'
OUTPUT=ROOT/'data.js'

def norm(s):
    s=unicodedata.normalize('NFKD', str(s or '')).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+','',s)
def pair(a,b): return '|'.join(sorted([norm(a),norm(b)]))
def fnum(v):
    try:
        if v is None or v=='' or isinstance(v,bool): return None
        n=float(v)
        return round(n,5) if abs(n)<1e10 else None
    except: return None
def fdate(s): return str(s or '')[:10]
def dt_diff(a,b):
    try:return abs((datetime.date.fromisoformat(fdate(a))-datetime.date.fromisoformat(fdate(b))).days)
    except:return 999

def circuit(s):
    s=str(s or '').lower()
    if 'challenger' in s:return 'Challenger'
    if 'wta' in s:return 'WTA'
    if 'atp' in s:return 'ATP'
    if 'itf' in s:return 'ITF'
    return 'Autre'

def lnum(x): return '' if x is None else x

def main():
    if not ARCHIVE.is_file(): raise SystemExit('Archive introuvable : '+str(ARCHIVE))
    with zipfile.ZipFile(ARCHIVE) as z:
        names=z.namelist()
        root='Tennis-edge-main/' if 'Tennis-edge-main/moves_detail_hist.csv' in names else ''
        def loadj(n):
            name=root+n
            if name not in names: return {}
            with z.open(name) as f:return json.load(f)
        def loadl(n):
            name=root+n
            if name not in names:return []
            with z.open(name) as f:
                return [json.loads(line) for line in f if line.strip()]
        def loadcsv(n):
            name=root+n
            if name not in names:return []
            with z.open(name) as f:return list(csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig',newline='')))
        # Precedence de l'identifiant fixture; sinon appariement conservateur par noms/date/tournoi.
        closing=loadj('closing_lines.json')
        results_by_fixture=loadj('resultats_oddspapi.json')
        derived=loadj('resultats_derived.json').get('results',[])
        index=collections.defaultdict(list)
        for r in derived:
            h=r.get('home_team'); a=r.get('away_team')
            if h and a and r.get('winner'):
                index[pair(h,a)].append(r)
        closings_by_pair=collections.defaultdict(list)
        curves={}
        for uid,x in closing.items():
            if not isinstance(x,dict): continue
            a=x.get('home');b=x.get('away');d=fdate(x.get('commence_time') or x.get('date'))
            if not a or not b:continue
            p=pair(a,b)
            closings_by_pair[p].append((d,x))
            hist=x.get('history') or []
            points=[];seen=set()
            for s in hist:
                tm=str(s.get('t',''))[:19]; h=fnum(s.get('home')); aw=fnum(s.get('away'))
                if not tm or (h is None and aw is None):continue
                v=(tm,h,aw)
                if v not in seen:points.append(v);seen.add(v)
            if len(points)>64:
                points=[points[round(i*(len(points)-1)/63)] for i in range(64)]
            curves[uid]={'uid':uid,'home':a,'away':b,'tournament':x.get('tournament'), 'date':d,
                         'points':points,'fixture_id':x.get('fixture_id')}
        def find_resolution(a,b,date,tour=''):
            # Ne jamais attribuer de règlement à une rencontre future.
            if date > datetime.datetime.now(datetime.timezone.utc).date().isoformat():return None
            p=pair(a,b)
            if not a or not b:return None
            # Proposer le fixture si la rencontre est appariée de façon unique à <= 2 j.
            matches=[(dt_diff(date,d),x) for d,x in closings_by_pair.get(p,[]) if dt_diff(date,d)<=2]
            if matches:
                matches.sort(key=lambda v:v[0]); best=[x for dd,x in matches if dd==matches[0][0]]
                found=[(x,results_by_fixture.get(x.get('fixture_id'))) for x in best]
                found=[(x,r) for x,r in found if isinstance(r,dict) and r.get('winner_name')]
                if len(found)==1:
                    x,r=found[0]; win=r['winner_name']
                    if norm(win) in {norm(a),norm(b)}:
                        return {'winner':win,'source':'fixture_id','provisional':bool(r.get('provisional',False)),
                                'result_date':fdate(date),'match_uid': next((id for id,y in closing.items() if y is x),None)}
            # Settlement derived: date de règlement peut différer du match; paire exacte
            cands=[r for r in index.get(p,[]) if dt_diff(date,r.get('date'))<=8 and fdate(r.get('date')) >= fdate(date)]
            if not cands:return None
            if tour:
                same=[r for r in cands if norm(tour)==norm(r.get('tournament'))]
                if same:cands=same
            # Si plusieurs dates de règlement proches avec vainqueurs différents, aucune attribution.
            winners={norm(r.get('winner')) for r in cands}
            if len(winners)!=1 or len(cands)>3:return None
            rr=min(cands,key=lambda r:dt_diff(date,r.get('date')))
            w=rr.get('winner')
            if norm(w) not in {norm(a),norm(b)}:return None
            return {'winner':w,'source':'paired_names_date','provisional':bool(rr.get('provisional',True)),
                    'result_date':rr.get('date')}
        rows=[]; idn=0
        def append(r):
            nonlocal idn
            idn+=1;r['id']=idn
            r['circuit']=circuit(r.get('tournament'))
            r['date']=fdate(r.get('date'))
            r['search']=' '.join(str(r.get(k) or '') for k in ['player','opponent','tournament','book','uid']).lower()
            rows.append(r)
        for move_name in ['moves_detail_hist.csv','moves_detail.csv']:
          for m in loadcsv(move_name):
              a=m.get('steame','');b=m.get('opp','');v=m.get('steame_gagne','').strip().lower()
              settled=v in ('oui','non') and fnum(m.get('pnl')) is not None
              append({'source':'moves' if move_name=='moves_detail_hist.csv' else 'moveslive','group':'Mouvements' if move_name=='moves_detail_hist.csv' else 'Mouvements live','uid':m.get('uid'),'date':m.get('date'), 'player':a,'opponent':b,
                'tournament':m.get('tour'),'book':m.get('entry_book'),'odds':fnum(m.get('entry')),
                'amplitude':fnum(m.get('mag_cote_pct')),'lead':fnum(m.get('lead_min')),
                'clv':fnum(m.get('clv_book_pct')),'clv_pin':fnum(m.get('clv_vs_pin_pct')),
                'pinnacle_open':fnum(m.get('pin_open')),'pinnacle_close':fnum(m.get('pin_close')),
                'book_close':fnum(m.get('soft_close')),'settled':settled,'won':v=='oui' if settled else None,
                'pnl':fnum(m.get('pnl')) if settled else None,'status':'Réglé' if settled else 'Sans résultat',
                'origin':move_name})
        for m in loadl('paper_trades_canal.jsonl'):
            status=m.get('statut')
            settled=status=='REGLE' and fnum(m.get('pnl')) is not None
            t=m.get('alerte_t',''); com=m.get('commence','')
            lead=fnum(m.get('lead_min'))
            if lead is None:
                try:lead=round((datetime.datetime.fromisoformat(com)-datetime.datetime.fromisoformat(t)).total_seconds()/60,1)
                except:pass
            append({'source':'canal','group':'Canal public','uid':m.get('uid'),'date':fdate(m.get('commence') or t),
              'player':m.get('joueur'),'opponent':'','tournament':m.get('tournoi') or m.get('categorie') or '',
              'book':m.get('book'),'odds':fnum(m.get('cote')),'amplitude':fnum(m.get('ecart_pct')),'lead':lead,
              'clv':None,'clv_pin':None,'settled':settled,'won':m.get('gagne') if settled else None,
              'pnl':fnum(m.get('pnl')) if settled else None,'status':'Réglé' if settled else 'Sans résultat',
              'origin':'paper_trades_canal.jsonl'})
        # Associer le CLV uniquement via uid + book + prix de cote (tolérance faible).
        canal_clv=loadcsv('canal_clv_detail.csv')
        cc=collections.defaultdict(list)
        for c in canal_clv:cc[(c.get('uid'),norm(c.get('book')))].append(c)
        canal_joined=0
        for r in rows:
            if r['source']!='canal':continue
            cands=[c for c in cc.get((r['uid'],norm(r['book'])),[]) if fnum(c.get('prix_signale')) is not None and r['odds'] is not None and abs(fnum(c['prix_signale'])-r['odds'])<.002]
            if len(cands)==1:
                r['clv']=fnum(cands[0].get('clv'));r['book_close']=fnum(cands[0].get('cloture'));canal_joined+=1
        for m in loadl('paper_trades_match.jsonl'):
            settled=m.get('status')=='SETTLED' and fnum(m.get('pnl')) is not None
            date=''
            try:date=datetime.datetime.fromtimestamp(float(m.get('commence')),datetime.timezone.utc).date().isoformat()
            except:date=fdate(m.get('commence'))
            append({'source':'match','group':'Paper match','uid':m.get('uid'),'date':date,
             'player':m.get('home') if m.get('side')=='home' else m.get('away'),
             'opponent':m.get('away') if m.get('side')=='home' else m.get('home'),
             'tournament':'','book':m.get('book'),'odds':fnum(m.get('entry_odds')),
             'amplitude':fnum(m.get('palier')),'lead':None,'clv':fnum(m.get('clv_book')),
             'clv_pin':fnum(m.get('clv_pin')),'book_close':fnum(m.get('close_book')),
             'settled':settled,'won':m.get('won') if settled else None,'pnl':fnum(m.get('pnl')) if settled else None,
             'status':'Réglé' if settled else 'Sans résultat','origin':'paper_trades_match.jsonl'})
        signals={}; joins={}
        for h in ('h13','h15','h16','h16b','h17','h18'):
            signals[h]=[]
            for s in loadl(f'{h}_signal_log.jsonl'):
                sent=bool(s.get('envoye',False))
                a=s.get('joueur');b=s.get('adversaire');date=fdate(s.get('commence'))
                # Appariement résultat uniquement lorsqu'un identifiant ou une paire non ambiguë est disponible.
                res=find_resolution(a,b,date,s.get('tournoi'))
                settled=bool(res)
                odds=fnum(s.get('cote'))
                pnl=round(odds-1,5) if settled and odds and norm(res['winner'])==norm(a) else (-1 if settled else None)
                r={'source':h,'group':h.upper().replace('B','-B'),'uid':s.get('uid'),'date':date,
                  'player':a,'opponent':b,'tournament':s.get('tournoi'),'book':s.get('book'),'odds':odds,
                  'amplitude':fnum(s.get('ampleur_pts')),'lead':fnum(s.get('lead_min')),
                  'clv':None,'clv_pin':None,'sent':sent,'settled':settled,
                  'won':(pnl>0 if pnl is not None else None),'pnl':pnl,'status':('Résultat provisoire' if res.get('provisional') else 'Réglé') if settled else 'Sans résultat',
                  'result_source':res.get('source') if res else None,'provisional':res.get('provisional') if res else None,
                  'origin':f'{h}_signal_log.jsonl + '+(res.get('source') if res else 'résultat indisponible')}
                append(r);signals[h].append({'uid':s.get('uid'),'sent':sent,'won':r['won'],'pnl':pnl, 'result_source':r['result_source']})
        # Inclure CLV sans trade comme population distincte : aucune performance financière imputée.
        for c in canal_clv:
            append({'source':'clv','group':'Journal CLV','uid':c.get('uid'),'date':c.get('date'),'player':c.get('joueur'),
              'opponent':'','tournament':'','book':c.get('book'),'odds':fnum(c.get('prix_signale')),
              'amplitude':fnum(c.get('ecart_annonce')),'lead':None,'clv':fnum(c.get('clv')),'clv_pin':None,
              'book_close':fnum(c.get('cloture')),'settled':False,'won':None,'pnl':None,
              'status':'CLV seul','origin':'canal_clv_detail.csv'})
        # Compacter les courbes: préserver le référentiel séparément, ne pas créer de ROI depuis le cours.
        generated=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
        data={'meta':{'name':'Tennis Edge Lab','version':'2.0.0','snapshot':generated[:10],
             'generated_at':generated, 'repo_sha':os.environ.get('GITHUB_SHA',''),
             'archive':ARCHIVE.name,'source_file_count':len(z.infolist()),'rows':len(rows),
             'canal_clv_joins':canal_joined,
             'notes':['Données actualisées par GitHub Actions ; ne constitue pas un flux de ticks en temps réel.',
              'ROI calculé à mise constante à partir des lignes réglées seulement.',
              'Les hypothèses utilisent un appariement de résultat indicatif et sont marquées provisoires.',
              'Les populations ont des grains distincts : mouvement, ticket papier, signal, ligne CLV. Ne pas les mélanger pour mesurer le ROI.',
              'Amplitude H13–H18 en points de probabilité, amplitude Mouvements/Canal public en % de cote.',
              'Les mesures POSTHOC ne sont pas importées comme variables de filtrage.']},
              'rows':rows, 'curves':curves,'pipeline':loadj('pipeline_status.json'),
              'book_index':loadj('book_index.json'),
              'report':loadj('paper_canal_report.json')}
        # Validation de publication : échouer bruyamment plutôt que diffuser une base amputée.
        by_source=collections.Counter(r['source'] for r in rows)
        min_rows=int(os.environ.get('LAB_MIN_ROWS','200'))
        if len(rows)<min_rows or by_source['moves']<100 or len(curves)<100:
            raise RuntimeError(f'LAB_INCOMPLETE_DATASET: rows={len(rows)}, moves={by_source["moves"]}, curves={len(curves)}')
        payload=json.dumps(data,ensure_ascii=False,separators=(',',':'))
        previous_path=ROOT/'data.js'
        # Le volume peut évoluer à la baisse, mais une baisse brutale impose une vérification.
        if os.environ.get('LAB_CHECK_PREVIOUS')=='1' and previous_path.exists():
            previous=previous_path.read_text('utf8')
            try:
                old=json.loads(previous.split('=',1)[1].rsplit(';',1)[0])
                if len(rows)<0.6*len(old.get('rows',[])):
                    raise RuntimeError('LAB_DATA_DROP: plus de 40 % des observations ont disparu')
            except json.JSONDecodeError: pass
        def atomic_write(path,text):
            tmp=path.with_suffix(path.suffix+'.tmp')
            tmp.write_text(text,encoding='utf8')
            tmp.replace(path)
        atomic_write(OUTPUT,'window.LAB_DATA='+payload+';\n')
        atomic_write(ROOT/'data.json',payload+'\n')
        sources_present=sorted(n for n in z.namelist() if n.rsplit('/',1)[-1] in {
            'moves_detail_hist.csv','moves_detail.csv','paper_trades_canal.jsonl',
            'canal_clv_detail.csv','paper_trades_match.jsonl','pipeline_status.json',
            'book_index.json','paper_canal_report.json','closing_lines.json',
            'resultats_oddspapi.json','resultats_derived.json',
            'h13_signal_log.jsonl','h15_signal_log.jsonl','h16_signal_log.jsonl',
            'h16b_signal_log.jsonl','h17_signal_log.jsonl','h18_signal_log.jsonl'})
        manifest={'schema_version':1,'version':'2.0.0','generated_at':generated,
                  'snapshot_date':generated[:10],'repo_sha':os.environ.get('GITHUB_SHA',''),
                  'dataset_url':'data.json','dataset_sha256':hashlib.sha256((payload+'\n').encode('utf8')).hexdigest(),
                  'dataset_bytes':len((payload+'\n').encode('utf8')),
                  'row_count':len(rows),'curve_count':len(curves),'source_counts':dict(by_source),
                  'sources_found':[n.split('/')[-1] for n in sources_present]}
        atomic_write(ROOT/'manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        print('Sortie:',OUTPUT, OUTPUT.stat().st_size,'octets; ',len(rows),'lignes',len(curves),'courbes, CLV joins',canal_joined)
        print('Populations',collections.Counter(r['source'] for r in rows))
        for h in signals:
            sr=[r for r in rows if r['source']==h and r['sent']]
            ok=[r for r in sr if r['settled']]
            print(h,'sent',len(sr),'resolved',len(ok),'roi',round(100*sum(r['pnl'] for r in ok)/len(ok),2) if ok else None)

if __name__=='__main__':main()
