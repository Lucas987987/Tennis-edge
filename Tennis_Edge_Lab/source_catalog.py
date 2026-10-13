#!/usr/bin/env python3
"""Inventaire exhaustif des FICHIERS sources; ne prétend pas que tout est utilisable en prédiction.

Les partitions peuvent représenter des millions d'horodatages. L'indexation et
la réduction hors navigateur sont effectuées par source_features.py en tâche
nightly; ce tableau distingue les sources indexées, cataloguées et bloquées.
"""
import argparse, collections, datetime as dt, json, os, pathlib, subprocess

ROOT=pathlib.Path(__file__).resolve().parents[1]
LAB=ROOT/'Tennis_Edge_Lab'

KNOWN={
'moves_detail_hist.csv':'transactions historiques avec P&L vérifiable',
'moves_detail.csv':'mouvements live',
'closing_lines.json':'historique de clôture',
'book_index.json':'méta bookmakers',
'paper_trades_canal.jsonl':'tickets simulés canal',
'paper_trades_match.jsonl':'tickets simulés match',
'canal_clv_detail.csv':'CLV du canal',
'resultats_oddspapi.json':'résultats OddsPapi',
'resultats_derived.json':'résultats consolidés',
'resultats.json':'résultats généraux',
'resultats_fast.json':'résultats rapides',
'set_results.json':'résultats sets',
'matches_oddspapi.json':'fixtures et offres récentes',
'pipeline_status.json':'santé pipeline',
'players_data.json':'profils joueurs',
'elo_ratings_atp.json':'ratings Elo ATP',
'elo_ratings_wta.json':'ratings Elo WTA',
'polymarket_ticks.jsonl':'marchés Polymarket live',
'kalshi_ticks.jsonl':'marchés Kalshi live',
}

def family(path):
    p=path.lower();b=p.split('/')[-1]
    if p.startswith('parts/'):
        if p.startswith('parts/v64/bookmakers/'):
            market=p.split('/')[3]
            return {'match':'historique bookmakers',
                    'set1':'historique vainqueur set 1',
                    'set2':'historique vainqueur set 2'}.get(market,'partition autre')
        if p.startswith('parts/v64/closing/'):return 'historique closing V6.4'
        if b.startswith('hist_book_'):return 'historique bookmakers'
        if b.startswith('hist_set1_'):return 'historique vainqueur set 1'
        if b.startswith('hist_set2_'):return 'historique vainqueur set 2'
        if b.startswith(('pm_ticks','polymarket_')):return 'ticks Polymarket'
        if b.startswith(('kx_ticks','kalshi_')):return 'ticks Kalshi'
        return 'partition autre'
    if p.startswith('historique/') and b.endswith('.csv.gz'):return 'résultats sportifs historiques'
    if b.startswith(('h13_signal','h14_signal','h15_signal','h16_signal','h16b_signal','h17_signal','h18_signal')):return 'journaux hypothèses gelées'
    if 'curve' in b or 'courbe' in b:return 'courbes de cote'
    if b.startswith(('resultats','set_results')):return 'résultats de matchs'
    if 'tick' in b:return 'ticks autres'
    if b.startswith(('paper','canal')):return 'journaux de tickets'
    if b in KNOWN:return KNOWN[b]
    return 'données additionnelles'

def main(root=ROOT,output=None):
    root=pathlib.Path(root)
    indexed=json.loads((root/'Tennis_Edge_Lab/cache/parts_features.json').read_text()) if (root/'Tennis_Edge_Lab/cache/parts_features.json').exists() else {}
    indexed_files={p for p,v in indexed.get('files',{}).items()
                   if v.get('category') in ('book','set1','set2','polymarket','kalshi')}
    # Tout fichier de données versionné, y compris les partitions et historique.
    paths=[]
    try:
        p=subprocess.run(['git','ls-files','-z'],cwd=root,capture_output=True,check=True)
        paths=[x.decode('utf8','replace') for x in p.stdout.split(b'\0') if x]
    except Exception:
        paths=[str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()]
    rows=[];size=collections.Counter();counts=collections.Counter()
    for filename in sorted(paths):
        if filename.startswith(('scripts/','.github/','.vscode/','tests/','workers/','Tennis_Edge_Lab/')):continue
        if not filename.lower().endswith(('.json','.jsonl','.jsonl.gz','.csv','.csv.gz')):continue
        f=root/filename
        if not f.is_file():continue
        fam=family(filename);count=counts[fam]+1;counts[fam]=count;size[fam]+=f.stat().st_size
        if filename.startswith('parts/'):
            state='agrégé avant décision' if filename in indexed_files else 'catalogué, indexation attendue'
        elif filename in ('moves_detail_hist.csv','resultats_derived.json','resultats_oddspapi.json','matches_oddspapi.json','closing_lines.json'):
            state='exploité par index principal'
        elif filename.startswith('historique/'):
            state='résultats indexés (base historique)'
        else:state='catalogué : jointure et temporalité à contrôler'
        rows.append({'file':filename,'family':fam,'bytes':f.stat().st_size,'status':state,
                     'eligible_predictor':state=='agrégé avant décision'})
    totals=collections.Counter(r['status'] for r in rows)
    payload={'schema_version':1,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),
             'total_data_files':len(rows),'total_bytes':sum(x['bytes'] for x in rows),
             'indexed_partition_files':len(indexed_files),'by_status':dict(totals),
             'families':[{'family':k,'files':counts[k],'bytes':size[k]} for k in sorted(counts)],
             'files':rows,'warning':'Inventorié ne signifie PAS analysé ni compatible avec le temps de décision. Aucune sélection sur un tick postérieur au signal.'}
    if output:
        dest=pathlib.Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    return payload
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',nargs='?',default=str(ROOT));ap.add_argument('--output',default=None)
    args=ap.parse_args();x=main(args.root,args.output or str(pathlib.Path(args.root)/'Tennis_Edge_Lab/live/source_catalog.json'))
    print('Sources:',x['total_data_files'],'fichiers,',sum(t['files'] for t in x['families'] if 'ticks' in t['family']),'partitions ticks,',x['indexed_partition_files'],'partitions indexées')
