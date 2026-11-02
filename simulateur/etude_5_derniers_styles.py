#!/usr/bin/env python3
"""Backtest chronologique des 5/10 derniers matchs contre le style adverse.
Aucun changement des prédictions; les modèles sont calibrés sur 2018-2023 et jugés sur 2024+.
Référence = Elo pré-match du dépôt (pas la combinaison complète du site).
"""
import argparse, collections, datetime as dt, heapq, json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import donnees, elo as E, profils_service as PS, styles_descriptifs as SD

STYLES=set(SD.STYLES)-{'indetermine'}
def logit(p):
    p=max(1e-5,min(1-1e-5,float(p)))
    return math.log(p/(1-p))
def sigmoid(z):
    return 1/(1+math.exp(-max(-30,min(30,z))))
def score(rows, name, coef):
    if not rows: return None
    p=np.array([sigmoid(logit(r['p'])+coef*r[name]) for r in rows])
    y=np.array([r['y'] for r in rows]); p=np.clip(p,1e-6,1-1e-6)
    return {'n':len(rows),'log_loss':round(float(np.mean(-y*np.log(p)-(1-y)*np.log(1-p))),6),'brier':round(float(np.mean((p-y)**2)),6),'accuracy':round(float(np.mean((p>=.5)==y)),4)}
def main():
    a=argparse.ArgumentParser(); a.add_argument('archive');a.add_argument('--sortie',default='simulateur/rapport_5_derniers_styles.json');a.add_argument('--debut-test',default='2024-01-01');a.add_argument('--maximum',type=int,default=0);args=a.parse_args()
    M=donnees.charger(args.archive,2015)
    M.sort(key=lambda m:(m['date'],m.get('tour',0),m.get('num',0)))
    if args.maximum: M=M[-args.maximum:]
    profiles=PS.Profils(PS.DEMI_VIE,1.0);elo=E.Elo();waiting=[];serial=0
    # Résultats des joueurs contre le style de leur adversaire : (date, victoire, probabilité Elo avant match)
    history=collections.defaultdict(list); pending=[];day=None;rows=[]
    def publish():
        for player,style,date,win,prob in pending:
            history[(player,style)].append((date,win,prob))
        pending.clear()
    for m in M:
        date=m['date']
        if day is not None and date!=day: publish()
        day=date
        start=dt.datetime.combine(date,dt.time())
        while waiting and waiting[0][0]<start:
            _,_,old=heapq.heappop(waiting);profiles.ajouter(old,old['_g'],old['_p'])
        g,p=E.cle(m.get('nom_g') or ''),E.cle(m.get('nom_p') or '')
        if not g or not p or g==p:continue
        m['_g'],m['_p']=g,p
        circuit,surface=m['circuit'],m['surface']
        if circuit in ('CH','ITF'):
            elo.presenter(g,1200.0);elo.presenter(p,1200.0)
        pe=elo.proba(g,p,surface)
        avg=profiles.moyenne(circuit,surface)
        sg=SD.classifier(*profiles.profil(g,circuit,surface,date),avg)
        sp=SD.classifier(*profiles.profil(p,circuit,surface,date),avg)
        if m.get('complet') and not m.get('abandon') and circuit in ('ATP','WTA','CH') and sg in STYLES and sp in STYLES:
            def signal(player,style,k,weighted=False):
                recent=history[(player,style)][-k:]
                if not recent:return 0.
                vals=[(w-pr) for _,w,pr in recent]
                if weighted:
                    ws=[.75**(len(vals)-i-1) for i in range(len(vals))]
                    return sum(v*w for v,w in zip(vals,ws))/sum(ws)*len(vals)/(len(vals)+5)
                return sum(vals)/(len(vals)+5) # shrinkage against small samples
            feats={}
            for k in (5,10):
                feats[f'last{k}']=signal(g,sp,k)-signal(p,sg,k)
            feats['last5_weighted']=signal(g,sp,5,True)-signal(p,sg,5,True)
            rows.append(dict(date=date.isoformat(),circuit=circuit,p=pe,y=1,**feats))
            # Symmetric representation avoids learning a winner-only ordering bias
            rows.append(dict(date=date.isoformat(),circuit=circuit,p=1-pe,y=0,**{k:-v for k,v in feats.items()}))
        if m.get('complet') and not m.get('abandon'):
            if sp in STYLES:pending.append((g,sp,date,1,pe))
            if sg in STYLES:pending.append((p,sg,date,0,1-pe))
        heapq.heappush(waiting,(dt.datetime.combine(m['fin'],dt.time()),serial,m));serial+=1
        elo.maj(g,p,surface,m.get('niveau')=='G',E.part_jeux(m['sets']) if m.get('complet') else None)
    publish()
    train=[r for r in rows if r['date']<args.debut_test];test=[r for r in rows if r['date']>=args.debut_test]
    variants=['last5','last10','last5_weighted'];coefs={};results={}
    # Fixed coefficient grid selected ONLY on training, never on test
    for v in variants:
        choices=[-2,-1,-.5,0,.5,1,2]
        coefs[v]=min(choices,key=lambda c:score(train,v,c)['log_loss'] if train else float('inf'))
    for circuit in ('TOUS','ATP','WTA','CH'):
        sub=[r for r in test if circuit=='TOUS' or r['circuit']==circuit]
        ref=score(sub,'last5',0)
        results[circuit]={'reference_elo':ref,'variantes':{v:dict(coefficient_appris=coefs[v],mesures=score(sub,v,coefs[v]),gain_log_loss=round(ref['log_loss']-score(sub,v,coefs[v])['log_loss'],6) if ref else None) for v in variants}}
    out={'description':'Test hors échantillon des résultats récents contre style adverse, sans modifier la production','reference':'Elo historique pré-match, PAS algorithme complet','periode_apprentissage':'2015 à '+args.debut_test,'debut_test':args.debut_test,'matchs_apprentissage':len(train)//2,'matchs_test':len(test)//2,'note':'Deux lignes symétriques par match ; n des métriques est le nombre de lignes, soit 2 par match. Résultats du même jour indisponibles. Coefficients choisis sur apprentissage.','resultats':results}
    os.makedirs(os.path.dirname(args.sortie) or '.',exist_ok=True)
    with open(args.sortie,'w',encoding='utf8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
