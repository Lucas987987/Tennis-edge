#!/usr/bin/env python3
"""Importateur Arena V1.7. Source JSON explicitement configurée, sans cotes."""
import datetime as dt, json, os, sys, urllib.request, urllib.error
from pathlib import Path
from urllib.parse import urlparse

API='https://tennis-edge-arena.tennis-edge.workers.dev/api/arena/admin/challenge'
MAX_MATCHES=30

def main():
    dry=os.environ.get('DRY_RUN','').lower() in ('true','1','yes')
    now=dt.datetime.now(dt.timezone.utc)
    source=Path('matches_oddspapi.json')
    meta_path=Path('matches_oddspapi_meta.json')
    if not source.is_file() or not meta_path.is_file():
        raise SystemExit('Fichiers Tennis Edge absents : import arrêté sans écriture.')
    meta=json.loads(meta_path.read_text(encoding='utf-8'))
    written=str(meta.get('last_write','')).strip()
    try:
        snapshot=dt.datetime.fromisoformat(written.replace('Z','+00:00'))
        if snapshot.tzinfo is None:snapshot=snapshot.replace(tzinfo=dt.timezone.utc)
        snapshot=snapshot.astimezone(dt.timezone.utc)
    except (ValueError,TypeError):
        raise SystemExit('Horodatage du snapshot invalide : import arrêté.')
    age=(now-snapshot).total_seconds()/60
    if not (-3 <= age <= 240):
        print(f'Snapshot trop ancien ou futur ({age:.0f} minutes). Import ignoré pour sécurité.')
        return
    matches=json.loads(source.read_text(encoding='utf-8'))
    if not isinstance(matches,list):raise SystemExit('Source tennis : liste JSON attendue.')
    print(f'Source Tennis Edge locale : {len(matches)} matchs, snapshot âgé de {age:.0f} minutes.')
    # On extrait seulement les champs sportifs : aucune cote, aucun bookmaker.
    normalized=[]
    for m in matches:
        if not isinstance(m,dict):continue
        tournament=str(m.get('sport_title') or '').strip()
        upper=tournament.upper()
        if 'CHALLENGER' in upper:circuit='CHALLENGER'
        elif upper.startswith('WTA ') or upper=='WTA':circuit='WTA'
        elif upper.startswith('ATP ') or upper=='ATP':circuit='ATP'
        else:continue
        start=str(m.get('commence_time') or '').strip()
        a=str(m.get('home_team') or '').strip()
        b=str(m.get('away_team') or '').strip()
        if not m.get('id') or not a or not b:continue
        status=str(m.get('status') or m.get('fixture_status') or '').lower()
        if status in ('live','inplay','in_play','started','finished','ended','cancelled','canceled','postponed','abandoned','retired','walkover'):continue
        normalized.append({'circuit':circuit,'title':tournament,'player_a':a,'player_b':b,'starts_at':start})
    matches=normalized
    selected=[];seen=set()
    for m in matches:
        if not isinstance(m,dict):continue
        circuit=str(m.get('circuit','')).upper().strip()
        title=str(m.get('title','')).strip()
        a=str(m.get('player_a','')).strip();b=str(m.get('player_b','')).strip()
        stamp=str(m.get('starts_at','')).strip()
        try: start=dt.datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(dt.timezone.utc)
        except (ValueError,TypeError):continue
        stamp=start.strftime('%Y-%m-%dT%H:%M:%SZ')
        if circuit not in ('ATP','WTA','CHALLENGER') or not 5<=len(title)<=100 or not 2<=len(a)<=80 or not 2<=len(b)<=80 or a==b:continue
        if not now+dt.timedelta(minutes=20)<start<now+dt.timedelta(days=7):continue
        payload=dict(circuit=circuit,title=title,player_a=a,player_b=b,starts_at=stamp)
        key=(circuit,title.casefold(),a.casefold(),b.casefold(),stamp)
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
