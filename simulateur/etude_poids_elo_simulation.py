#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""etude_poids_elo_simulation.py — 05/11/2026, demande de Lucas : la part de l Elo est-elle trop grande ?
1) part fixe de la simulation sur 5 979 pronostics rejoués hors échantillon (juil.–nov. 2026), par circuit et période :
   la part en place (23 %) est la bonne ; l indice WTA « 70 % » vu sur 190 matchs ne tient pas sur 1 193 (50 % : pire).
2) part selon l expérience des joueurs (règle ci-dessous) : non retenue sur aucun circuit (ATP −0,0021, WTA −0,0011, CH +0,0006).
Usage : python simulateur/etude_poids_elo_simulation.py (depuis la racine, archive Sackmann dans /tmp/sackmann)
"""
# Règle fixée avant : poids de la simulation par tranche d'expérience (min des matchs des deux joueurs : <60, 60–200, ≥200),
# appris sur août–sept, jugé sur oct–nov ; retenu sur un circuit si gain ≥ 0,001 sur ≥ 300 matchs jugés.
import gzip,json,math,collections,sys,glob
sys.path.insert(0,'simulateur')
import donnees as DN, elo as E, feuilles as FE
L=[json.loads(l) for l in gzip.open('simulateur/pronostics_hors_echantillon.jsonl.gz','rt')]
ids={x['id'] for x in L}
fe={}
for f in glob.glob('feuilles/*.jsonl.gz'):
  for l in gzip.open(f,'rt'):
    e=json.loads(l)
    if e['id'] in ids: fe[e['id']]=(E.cle(e['home']['nom']),E.cle(e['away']['nom']))
# compte de matchs par joueur avant chaque date
ev=[]
for m in DN.charger('/tmp/sackmann',2012): ev.append((m['date'].isoformat(),E.cle(m['nom_g']),E.cle(m['nom_p'])))
for m in FE.charger('.'):
  if m['date'].isoformat()>'2026-06-30': ev.append((m['date'].isoformat(),E.cle(m.get('nom_g')),E.cle(m.get('nom_p'))))
ev.sort()
q=sorted([(x['jour'],x['id']) for x in L if x['id'] in fe])
cnt=collections.Counter(); xp={}; i=0
for j,idx in q:
  while i<len(ev) and ev[i][0]<j:
    cnt[ev[i][1]]+=1; cnt[ev[i][2]]+=1; i+=1
  h,a=fe[idx]; xp[idx]=min(cnt[h],cnt[a])
lg=lambda p:math.log(max(min(p,1-1e-6),1e-6)/(1-max(min(p,1-1e-6),1e-6))); sg=lambda z:1/(1+math.exp(-z))
T=lambda n: '<60' if n<60 else '60–200' if n<200 else '≥200'
W=[i/20 for i in range(0,17)]
S=1.0193
def ll(R,w): return sum(-math.log(sg(S*((1-w)*lg(x['p_elo'])+w*lg(x['p_sim']))) if x['gagnant']=='home' else 1-sg(S*((1-w)*lg(x['p_elo'])+w*lg(x['p_sim'])))) for x in R)
for c in ('ATP','WTA','CH'):
  R=[x for x in L if x['circuit']==c and x['id'] in xp and None not in (x.get('p_sim'),x.get('p_elo')) and x['gagnant'] in ('home','away')]
  A=[x for x in R if x['jour']<'2026-09-29']; J=[x for x in R if x['jour']>='2026-09-29']
  wt={}
  for t in ('<60','60–200','≥200'):
    a=[x for x in A if T(xp[x['id']])==t]
    wt[t]=min(W,key=lambda w:ll(a,w)) if len(a)>=50 else .233
  l0=ll(J,.233)/len(J); l1=sum(ll([x],wt[T(xp[x['id']])]) for x in J)/len(J)
  rep=collections.Counter(T(xp[x['id']]) for x in J)
  print(c,'appris',len(A),'jugés',len(J),'poids sim par tranche',wt,'répartition',dict(rep),'| fixe',round(l0,4),'par tranche',round(l1,4),'gain',round(l0-l1,4),'RETENU' if len(J)>=300 and l0-l1>=0.001 else 'non')
