#!/usr/bin/env python3
"""Importateur Arena V1.7. Source JSON explicitement configurée, sans cotes."""
import datetime as dt, json, os, sys, urllib.request, urllib.error
from urllib.parse import urlparse

API='https://tennis-edge-arena.tennis-edge.workers.dev/api/arena/admin/challenge'
MAX_MATCHES=30

def main():
    url=os.environ.get('ARENA_MATCH_FEED_URL','').strip()
    dry=os.environ.get('DRY_RUN','').lower() in ('true','1','yes')
    if not url:
        print('Import désactivé : configurer la variable GitHub ARENA_MATCH_FEED_URL (URL HTTPS du calendrier JSON).')
        return
    parsed=urlparse(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
        raise SystemExit('Flux invalide : URL HTTPS publique requise.')
    req=urllib.request.Request(url,headers={'User-Agent':'TennisEdgeArena/1.7','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=20) as r:
        if int(r.headers.get('content-length','0'))>500_000: raise SystemExit('Flux trop volumineux')
        data=r.read(500_001)
    if len(data)>500_000: raise SystemExit('Flux trop volumineux')
    feed=json.loads(data)
    matches=feed.get('matches',[]) if isinstance(feed,dict) else feed
    if not isinstance(matches,list):raise SystemExit('Format JSON attendu: {"matches":[...]}')
    now=dt.datetime.now(dt.timezone.utc)
    selected=[];seen=set()
    for m in matches:
        if not isinstance(m,dict):continue
        circuit=str(m.get('circuit','')).upper().strip()
        title=str(m.get('title','')).strip()
        a=str(m.get('player_a','')).strip();b=str(m.get('player_b','')).strip()
        stamp=str(m.get('starts_at','')).strip()
        try: start=dt.datetime.strptime(stamp,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc)
        except ValueError:continue
        if circuit not in ('ATP','WTA','CHALLENGER') or not 5<=len(title)<=100 or not 2<=len(a)<=80 or not 2<=len(b)<=80 or a==b:continue
        if not now+dt.timedelta(minutes=20)<start<now+dt.timedelta(days=7):continue
        payload=dict(circuit=circuit,title=title,player_a=a,player_b=b,starts_at=stamp)
        key=tuple(payload.values())
        if key in seen:continue
        seen.add(key);selected.append(payload)
    selected.sort(key=lambda x:x['starts_at']);selected=selected[:MAX_MATCHES]
    print(f'Flux lu: {len(matches)} entrées, {len(selected)} matchs éligibles (maximum {MAX_MATCHES} par exécution).')
    if dry:
        for m in selected:print('SIMULATION',m['circuit'],m['title'],m['player_a'],'vs',m['player_b'],m['starts_at'])
        return
    token=os.environ.get('ARENA_ADMIN_TOKEN','')
    if not token:raise SystemExit('Secret ARENA_ADMIN_TOKEN manquant')
    created=existing=0
    for m in selected:
        req=urllib.request.Request(API,data=json.dumps(m,ensure_ascii=False).encode(),headers={'Content-Type':'application/json','x-arena-admin-token':token},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=20) as r: result=json.load(r)
        except urllib.error.HTTPError as e:
            print('Erreur import HTTP',e.code,e.read(200).decode('utf-8','replace'))
            raise SystemExit(1)
        created+=bool(result.get('created',True));existing+=not result.get('created',True)
    print(f'Import terminé : {created} créés, {existing} déjà présents.')
if __name__=='__main__':main()
