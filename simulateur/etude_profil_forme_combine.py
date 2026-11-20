#!/usr/bin/env python3
"""Backtest historique profil adverse + forme ajustée, sans modification production.
Usage: python simulateur/etude_profil_forme_combine.py /tmp/sackmann --sortie rapport.json
"""
import argparse, collections, datetime as dt, heapq, json, math, os, sys
sys.path.insert(0,os.path.dirname(__file__))
import donnees, elo as E, profils_service as PS, styles_descriptifs as SD

STYLES=set(SD.STYLES)-{'indetermine'}
def summary(rows):
    n=len(rows)
    if not n:return {'n':0}
    wins=sum(r['y'] for r in rows); exp=sum(r['p'] for r in rows)
    residual=[r['y']-r['p'] for r in rows]
    delta=sum(residual)/n
    se=(sum((x-delta)**2 for x in residual)/max(1,n-1)/n)**.5
    return {'n':n,'victoires':wins,'taux_reel_pct':round(100*wins/n,2),'taux_attendu_elo_pct':round(100*exp/n,2),'surperformance_pp':round(100*delta,2),'ic95_pp':[round(100*(delta-1.96*se),2),round(100*(delta+1.96*se),2)],'brier_elo':round(sum((r['p']-r['y'])**2 for r in rows)/n,5)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('archive');ap.add_argument('--sortie',default='rapport_profil_forme_combine.json');args=ap.parse_args()
    M=donnees.charger(args.archive,2015)
    M.sort(key=lambda m:(m['date'],m.get('tour',0),m.get('num',0)))
    profiles=PS.Profils(PS.DEMI_VIE,1.0);elo, depart_bas=E.de_production(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")));waiting=[];serial=0
    # Historique par joueur: (date, resultat, probabilite pre-match, style adverse, surface)
    hist=collections.defaultdict(list);pending=[];day=None;rows=[]
    def publish():
        for player,rec in pending:hist[player].append(rec)
        pending.clear()
    for m in M:
        date=m['date']
        if day is not None and date!=day:publish()
        day=date
        start=dt.datetime.combine(date,dt.time())
        while waiting and waiting[0][0]<start:
            _,_,old=heapq.heappop(waiting);profiles.ajouter(old,old['_g'],old['_p'])
        g,p=E.cle(m.get('nom_g') or ''),E.cle(m.get('nom_p') or '')
        if not g or not p or g==p:continue
        m['_g'],m['_p']=g,p
        circuit,surface=m['circuit'],m['surface']
        if depart_bas and circuit in ('CH','ITF'):elo.presenter(g,depart_bas);elo.presenter(p,depart_bas)
        pe=elo.proba(g,p,surface)
        avg=profiles.moyenne(circuit,surface)
        sg=SD.classifier(*profiles.profil(g,circuit,surface,date),avg)
        sp=SD.classifier(*profiles.profil(p,circuit,surface,date),avg)
        if m.get('complet') and not m.get('abandon') and circuit in ('ATP','WTA','CH') and sg in STYLES and sp in STYLES and date>=dt.date(2018,1,1):
            def signals(j,opstyle):
                h=hist[j]
                recent=h[-40:]
                f=sum(w-pr for _,w,pr,_,_ in recent)
                # 40-match adjusted excess; shrink toward zero with 12 pseudo-matches
                f=f*40/(len(recent)+12) if len(recent)>=20 else None
                same=[x for x in h if x[3]==opstyle and x[4]==surface]
                # Same surface, same opponent style; 15 pseudo-matches shrinkage
                ps=sum(w-pr for _,w,pr,_,_ in same)/(len(same)+15) if len(same)>=8 else None
                return f,ps,len(recent),len(same)
            fg,pg,nfg,npg=signals(g,sp);fp,pp,nfp,npp=signals(p,sg)
            if fg is not None and fp is not None and pg is not None and pp is not None:
                # Outcome and expected probability for the selected side, not winner-based selection.
                # Both directions are evaluated independently: a match can qualify for neither or one side.
                for j,fo,pr,pwin in ((g,fg,pg,pe),(p,fp,pp,1-pe)):
                    other_f,other_pr=(fp,pp) if j==g else (fg,pg)
                    df=fo-other_f;dp=pr-other_pr
                    # Baseline eligibility and thresholds fixed BEFORE looking at outcomes.
                    selected=(dp>=.05 and df>=4.0)
                    rows.append({'date':date.isoformat(),'circuit':circuit,'surface':surface,'player':j,'opponent':p if j==g else g,'p':pwin,'y':int(j==g),'profil_diff':dp,'forme_diff':df,'selected':selected})
        if m.get('complet') and not m.get('abandon'):
            pending.append((g,(date,1,pe,sp,surface)))
            pending.append((p,(date,0,1-pe,sg,surface)))
        heapq.heappush(waiting,(dt.datetime.combine(m['fin'],dt.time()),serial,m));serial+=1
        elo.maj(g,p,surface,m.get('niveau')=='G',E.part_jeux(m['sets']) if m.get('complet') else None)
    publish()
    out={'method':'styles service-retour reels figes avant match; surperformance contre style adverse sur meme surface (min 8, shrink 15); forme 40 matchs (min 20, shrink 12); comparaison relative des deux joueurs','seuils':{'profil_difference':0.05,'forme_difference_victoires_sur_40':4.0},'reference':'Elo pre-match avec reglages de production, non modele complet de production','circuits':{},'aucune_activation':True}
    for c in ('ATP','WTA','CH'):
        out['circuits'][c]={}
        for name,lo,hi in [('apprentissage_2018_2022','2018-01-01','2023-01-01'),('validation_2023_2026','2023-01-01','2026-07-01')]:
            rs=[r for r in rows if r['circuit']==c and lo<=r['date']<hi]
            out['circuits'][c][name]={'eligibles_joueurs':len(rs),'signal_combine':summary([r for r in rs if r['selected']]),'signal_profil_seul':summary([r for r in rs if r['profil_diff']>=.05]),'signal_forme_seule':summary([r for r in rs if r['forme_diff']>=4]),'autres':summary([r for r in rs if not r['selected']])}
    with open(args.sortie,'w',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
