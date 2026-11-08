#!/usr/bin/env python3
"""Arena V2.0: settle ONLY independently confirmed results, never provisional feeds.
No odds, no player PII, no direct D1 access. Fail closed on ambiguity.
"""
import datetime as dt
import json
import os
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path

API = 'https://tennis-edge-arena.tennis-edge.workers.dev'
SOURCE = Path('arena/data/results_confirmed.json')


def norm(s):
    s = unicodedata.normalize('NFKD', str(s)).casefold()
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in s if not unicodedata.combining(c))).strip()


def iso_date(s):
    return dt.date.fromisoformat(str(s)[:10])


def request(method, path, token, payload=None):
    with tempfile.TemporaryDirectory(prefix='arena-settle-') as tmp:
        output=Path(tmp)/'response.json'
        data=Path(tmp)/'request.json'
        config='\n'.join([
            'url = '+json.dumps(API+path), 'request = '+json.dumps(method),
            'header = "Accept: application/json"',
            'header = '+json.dumps('x-arena-admin-token: '+token),
            'user-agent = "TennisEdgeArena/2.0"',
            'connect-timeout = 10','max-time = 30','retry = 0','silent','show-error',
        ])+'\n'
        cmd=['curl','--config','-','--output',str(output),'--write-out','%{http_code}']
        if payload is not None:
            data.write_text(json.dumps(payload),encoding='utf-8')
            config+='header = "Content-Type: application/json"\n'
            cmd+=['--data-binary','@'+str(data)]
        r=subprocess.run(cmd,input=config,text=True,capture_output=True,timeout=40)
        if r.returncode:raise RuntimeError('Transport curl échoué (code '+str(r.returncode)+')')
        code=int(r.stdout.strip())
        try: body=json.loads(output.read_text(encoding='utf-8'))
        except ValueError:raise RuntimeError('Réponse Worker non JSON (HTTP '+str(code)+')')
        if code not in (200,201):raise RuntimeError('Worker HTTP '+str(code)+' : '+str(body.get('error','réponse refusée')))
        return body


def verified_results():
    if not SOURCE.exists():
        print('Aucune source de résultats confirmés : zéro attribution.');return []
    d=json.loads(SOURCE.read_text(encoding='utf-8'))
    if not isinstance(d,dict) or d.get('schema_version')!=1 or not isinstance(d.get('results'),list):
        raise ValueError('Format des résultats confirmés invalide')
    out=[]
    for x in d['results']:
        if not isinstance(x,dict):continue
        # Explicit independent verification; imported odds-derived provisional files NEVER qualify.
        if x.get('verified') is not True or x.get('provisional') is not False:continue
        if x.get('source') not in ('official', 'manual_verified'):continue
        if x.get('status')!='completed' or x.get('winner') not in ('a','b'):continue
        try: day=iso_date(x['date'])
        except (ValueError,KeyError):continue
        if not all(isinstance(x.get(k),str) and x[k].strip() for k in ('tournament','player_a','player_b')):continue
        out.append((x,day))
    return out


def candidate(challenge,results):
    try:
        title=norm(challenge['title'].split(' · ',1)[-1]);a=norm(challenge['player_a']);b=norm(challenge['player_b'])
        day=iso_date(challenge['starts_at'])
    except (ValueError,KeyError):return None
    found=[]
    for x,d in results:
        if abs((day-d).days)>1 or norm(x['tournament'])!=title:continue
        xa=norm(x['player_a']);xb=norm(x['player_b'])
        if a==xa and b==xb:found.append(x['winner'])
        elif a==xb and b==xa:found.append('b' if x['winner']=='a' else 'a')
    return found[0] if len(found)==1 else None


def main():
    dry=os.environ.get('DRY_RUN','true').lower()!='false'
    token=os.environ.get('ARENA_ADMIN_TOKEN','')
    if not token:raise SystemExit('ARENA_ADMIN_TOKEN manquant')
    results=verified_results()
    print('Résultats confirmés acceptés :',len(results),'mode :','SIMULATION' if dry else 'RÉEL')
    cursor='';seen=set();checked=matched=settled=0
    while True:
        suffix='?cursor='+cursor if cursor else ''
        response=request('GET','/api/arena/admin/pending-settlements'+suffix,token)
        for ch in response.get('challenges',[]):
            checked+=1
            winner=candidate(ch,results)
            if not winner:continue
            matched+=1
            print('MATCH CONFIRMÉ :',ch['id'],'vainqueur',winner)
            if not dry:
                request('POST','/api/arena/admin/settle',token,{'challenge_id':ch['id'],'winner':winner})
                settled+=1
        next_cursor=response.get('next_cursor')
        if not next_cursor:break
        if next_cursor in seen:raise RuntimeError('Pagination bloquée')
        seen.add(next_cursor);cursor=next_cursor
    print(f'Bilan : {checked} défis anciens, {matched} résultats concordants, {settled} validations D1.')

if __name__=='__main__':main()
