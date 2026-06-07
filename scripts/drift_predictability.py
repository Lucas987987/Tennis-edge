#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
drift_predictability.py  (v2 : descriptif + test ex-ante)
---------------------------------------------------------
1. DESCRIPTIF : classe les matchs du favori qui raccourcit le plus a celui
   qui derive le plus (voir QUELS favoris bougent).
2. EX-ANTE : test walk-forward -> peut-on PREVOIR, a l'ouverture, lesquels
   vont raccourcir ? (fit sur le passe, validation hors-echantillon)
3. CLV : combien on capterait en misant le favori des l'ouverture.

Lecture seule : clv_history.jsonl (courbes Pinnacle). Aucune API.

A garder en tete :
- Ce sont des cotes PINNACLE (le book le plus sharp). Prevoir la derive de
  Pinnacle = battre la meilleure ouverture du marche : tres improbable.
- "open" = 1er point capture, pas forcement la vraie ouverture.
- CLV>0 ne profite que s'il bat la marge payee a l'entree ET sans limitation.
"""
import json, os, sys, math
from statistics import mean, median

HIST = os.environ.get('CLV_HISTORY', 'clv_history.jsonl')
OUT  = os.environ.get('DRIFT_REPORT', 'drift_report.json')

GRASS = ['wimbledon','queen','halle','eastbourne','newport','s-hertogenbosch','mallorca','birmingham','nottingham']
CLAY  = ['french open','roland','monte','madrid','rome','barcelona','hamburg','estoril','munich','bucharest',
         'gstaad','kitzbuhel','umag','bastad','geneva','lyon','rio','buenos aires','santiago','cordoba',
         'houston','charleston','strasbourg','rabat','parma','palermo']

def surface_of(t):
    tl=(t or '').lower()
    if any(k in tl for k in CLAY): return 'clay'
    if any(k in tl for k in GRASS): return 'grass'
    return 'hard'

def curve_open_close(curve):
    if not curve: return None
    pts=[]
    for p in curve:
        if not p or len(p)<2: continue
        try: pr=float(p[1])
        except (TypeError,ValueError): continue
        if pr and pr>1.0: pts.append((str(p[0]),pr))
    if len(pts)<2: return None
    pts.sort(key=lambda x:x[0])
    return pts[0][1], pts[-1][1], len(pts), pts[-1][0]

def load_rows():
    rows=[]
    if not os.path.exists(HIST): return rows
    for line in open(HIST,encoding='utf-8'):
        line=line.strip()
        if not line: continue
        try: rows.append(json.loads(line))
        except json.JSONDecodeError: pass
    return rows

def stats_block(xs):
    n=len(xs)
    if n==0: return {'n':0}
    m=mean(xs)
    if n>1:
        sd=math.sqrt(sum((x-m)**2 for x in xs)/(n-1)); se=sd/math.sqrt(n)
    else: sd=se=0.0
    return {'n':n,'moyenne':round(m,3),'mediane':round(median(xs),3),
            'ecart_type':round(sd,3),'ic95_bas':round(m-1.96*se,3),
            'ic95_haut':round(m+1.96*se,3),
            'pct_positifs':round(100*sum(1 for x in xs if x>0)/n,1)}

def linfit(xs,ys):
    n=len(xs); sx=sum(xs); sy=sum(ys); sxx=sum(x*x for x in xs); sxy=sum(x*y for x,y in zip(xs,ys))
    den=n*sxx-sx*sx
    if den==0: return (mean(ys),0.0)
    b1=(n*sxy-sx*sy)/den; b0=(sy-b1*sx)/n
    return (b0,b1)

def pearson(xs,ys):
    n=len(xs)
    if n<3: return 0.0
    mx,my=mean(xs),mean(ys)
    cov=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    vx=sum((x-mx)**2 for x in xs); vy=sum((y-my)**2 for y in ys)
    return cov/math.sqrt(vx*vy) if vx>0 and vy>0 else 0.0

def main():
    rows=load_rows()
    if not rows:
        print("DRIFT — 0 ligne dans",HIST,"-> declenche fetch_clv puis relance.")
        json.dump({'status':'empty','n_matchs':0},open(OUT,'w'),ensure_ascii=False,indent=2)
        return 0

    recs=[]; sans_courbe=0; trop_court=0
    for r in rows:
        hc=r.get('home_curve'); ac=r.get('away_curve')
        if not hc or not ac: sans_courbe+=1; continue
        ho=curve_open_close(hc); ao=curve_open_close(ac)
        if not ho or not ao: trop_court+=1; continue
        h_open,h_close,h_n,h_ts=ho; a_open,a_close,a_n,a_ts=ao
        if h_open<=a_open:
            fav_open,fav_close=h_open,h_close; dog_open,dog_close=a_open,a_close
            fav_name=r.get('home'); fav_side='home'
        else:
            fav_open,fav_close=a_open,a_close; dog_open,dog_close=h_open,h_close
            fav_name=r.get('away'); fav_side='away'
        ip_f,ip_d=1/fav_open,1/dog_open
        margin=ip_f+ip_d-1
        fav_prob=ip_f/(ip_f+ip_d)
        drift_fav=(fav_close/fav_open-1)*100
        clv_fav=(fav_open/fav_close-1)*100
        clv_dog=(dog_open/dog_close-1)*100
        recs.append({'uid':r.get('uid'),'tournoi':r.get('tournament'),
            'fav':fav_name or fav_side,'surface':surface_of(r.get('tournament','')),
            'fav_open':round(fav_open,3),'fav_close':round(fav_close,3),
            'fav_prob_open':round(fav_prob,4),'margin_pct':round(margin*100,2),
            'drift_fav_pct':round(drift_fav,3),'clv_fav_pct':round(clv_fav,3),
            'clv_dog_pct':round(clv_dog,3),'close_ts':max(h_ts,a_ts)})

    if not recs:
        print("DRIFT — aucun match analysable. Lignes:",len(rows),
              "| sans courbe:",sans_courbe,"| courbe<2pts:",trop_court)
        json.dump({'status':'no_curves','lignes':len(rows),
                   'sans_courbe':sans_courbe,'courbe_trop_courte':trop_court},
                  open(OUT,'w'),ensure_ascii=False,indent=2)
        return 0

    n=len(recs)
    clv_fav=[r['clv_fav_pct'] for r in recs]
    s_clv=stats_block(clv_fav); s_drift=stats_block([r['drift_fav_pct'] for r in recs])
    marge_moy=mean([r['margin_pct'] for r in recs]); seuil=marge_moy/2

    # ---- 1. DESCRIPTIF : classement ----
    ranked=sorted(recs,key=lambda r:r['drift_fav_pct'])   # plus raccourci -> plus derive
    top_short=ranked[:8]; top_drift=ranked[-8:][::-1]

    # ---- 2. EX-ANTE : walk-forward sur fav_prob_open ----
    by_time=sorted(recs,key=lambda r:r['close_ts'])
    exante={'testable':False}
    if n>=40:
        k=int(n*0.7); train=by_time[:k]; test=by_time[k:]
        b0,b1=linfit([r['fav_prob_open'] for r in train],[r['drift_fav_pct'] for r in train])
        pred=[b0+b1*r['fav_prob_open'] for r in test]
        actual=[r['drift_fav_pct'] for r in test]
        oos_corr=pearson(pred,actual)
        # sous-ensemble que le modele predit comme raccourcisseur (pred < -seuil)
        flagged=[r for r,p in zip(test,pred) if p < -seuil]
        clv_flag=stats_block([r['clv_fav_pct'] for r in flagged]) if flagged else {'n':0}
        exante={'testable':True,'n_train':len(train),'n_test':len(test),
                'pente_proba_vs_drift':round(b1,3),'oos_corr_pred_vs_reel':round(oos_corr,3),
                'clv_favoris_flagues':clv_flag}

    report={'status':'ok','n_matchs':n,'marge_open_moyenne_pct':round(marge_moy,2),
            'derive_favori_pct':s_drift,'clv_favori_open_pct':s_clv,
            'classement_complet':ranked,'ex_ante':exante}
    json.dump(report,open(OUT,'w'),ensure_ascii=False,indent=2)

    # ---- sortie ----
    print("="*66)
    print(f"DRIFT PREDICTABILITY v2 — {n} matchs | marge moy {marge_moy:.2f}% | seuil {seuil:.2f}%")
    print("="*66)
    print(f"Derive favori : moy {s_drift['moyenne']:+.2f}% | raccourcit dans "
          f"{100-s_drift['pct_positifs']:.0f}% des cas")
    print(f"CLV favori joue a l'open : {s_clv['moyenne']:+.2f}% "
          f"[IC95 {s_clv['ic95_bas']:+.2f};{s_clv['ic95_haut']:+.2f}] "
          f"| positif {s_clv['pct_positifs']:.0f}%")
    print()
    print("--- QUELS FAVORIS RACCOURCISSENT LE PLUS (descriptif) ---")
    for r in top_short:
        print(f"  {r['drift_fav_pct']:+6.1f}%  {str(r['fav'])[:22]:22s} "
              f"{r['fav_open']:.2f}->{r['fav_close']:.2f}  p{r['fav_prob_open']*100:.0f}% {r['surface']}")
    print("  ... (et les plus gros DERIVEURS, sens inverse) ...")
    for r in top_drift[:3]:
        print(f"  {r['drift_fav_pct']:+6.1f}%  {str(r['fav'])[:22]:22s} "
              f"{r['fav_open']:.2f}->{r['fav_close']:.2f}  p{r['fav_prob_open']*100:.0f}% {r['surface']}")
    print()
    print("--- PEUT-ON LES PREVOIR A L'AVANCE ? (walk-forward) ---")
    if not exante['testable']:
        print(f"  Pas assez de matchs (n={n}<40). Reviens avec quelques centaines.")
    else:
        oc=exante['oos_corr_pred_vs_reel']
        print(f"  Train {exante['n_train']} -> Test {exante['n_test']}")
        print(f"  Correlation hors-echantillon (predit vs reel) : {oc:+.3f}")
        cf=exante['clv_favoris_flagues']
        if cf.get('n',0):
            print(f"  CLV des favoris FLAGUES raccourcisseurs (test) : "
                  f"{cf['moyenne']:+.2f}% [IC95 {cf['ic95_bas']:+.2f};{cf['ic95_haut']:+.2f}] sur n={cf['n']}")
        if abs(oc)<0.10:
            print("  VERDICT : ~0 -> la derive Pinnacle est IMPREVISIBLE par ce critere.")
        elif cf.get('n',0) and cf['ic95_bas']>seuil:
            print("  VERDICT : SIGNAL hors-echantillon qui bat la marge. A creuser serieusement.")
        else:
            print("  VERDICT : correlation faible et/ou CLV sous le seuil de marge -> non exploitable.")
    print("="*66)
    if n<150: print(f"NB : {n} matchs, trop peu pour trancher. Vise quelques centaines.")
    return 0

if __name__=='__main__':
    sys.exit(main())
