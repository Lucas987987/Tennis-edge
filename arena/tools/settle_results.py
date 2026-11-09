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
SOURCE = Path('resultats_oddspapi.json')


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
    """Read existing OddsPapi settlement archive; only explicit finished market wins qualify."""
    if not SOURCE.exists():
        print('Archive OddsPapi absente : aucune attribution.'); return []
    data=json.loads(SOURCE.read_text(encoding='utf-8'))
    if not isinstance(data,dict):raise ValueError('Archive OddsPapi invalide')
    out=[]; reasons={}
    for fixture_id,x in data.items():
        if not isinstance(x,dict):continue
        # Older records are provisional and cannot be retroactively certified.
        if x.get('source')!='oddspapi_settlement' or x.get('provisional') is not False:continue
        if x.get('status_name')!='Finished' or x.get('winner_from_market') is not True:continue
        if x.get('winner') not in ('home','away'):continue
        # La date de résolution peut être des jours après le match : utiliser le coup d'envoi.
        try: day=iso_date(x.get('commence_time') or x.get('starts_at'))
        except (ValueError,KeyError):continue
        if not all(isinstance(x.get(k),str) and x[k].strip() for k in ('tournament','home','away')):continue
        out.append(({'tournament':x['tournament'],'player_a':x['home'],
                     'player_b':x['away'],'winner':'a' if x['winner']=='home' else 'b'},day))
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
    if SOURCE.exists():
        archive=json.loads(SOURCE.read_text(encoding='utf-8'))
        from collections import Counter
        counts=Counter()
        for x in archive.values():
            if not isinstance(x,dict):continue
            if x.get('provisional') is not False:counts['provisoire']+=1
            elif x.get('status_name')!='Finished':counts['statut_non_finished']+=1
            elif x.get('winner_from_market') is not True:counts['marche_non_confirme']+=1
            elif not (x.get('commence_time') or x.get('starts_at')):counts['date_debut_absente']+=1
            else:counts['eligible_apres_controles']+=1
        print('DIAGNOSTIC ARCHIVE :',dict(counts))
    print('Résultats confirmés acceptés :',len(results),'mode :','SIMULATION' if dry else 'RÉEL')
    cursor='';seen=set();checked=matched=settled=0;unmatched=[]
    while True:
        suffix='?cursor='+cursor if cursor else ''
        response=request('GET','/api/arena/admin/pending-settlements'+suffix,token)
        for ch in response.get('challenges',[]):
            checked+=1
            winner=candidate(ch,results)
            if not winner:
                if len(unmatched)<25:unmatched.append((ch.get('id'),ch.get('title'),ch.get('player_a'),ch.get('player_b'),ch.get('starts_at')))
                continue
            matched+=1
            print('MATCH CONFIRMÉ :',ch['id'],'vainqueur',winner)
            if not dry:
                request('POST','/api/arena/admin/settle',token,{'challenge_id':ch['id'],'winner':winner})
                settled+=1
        next_cursor=response.get('next_cursor')
        if not next_cursor:break
        if next_cursor in seen:raise RuntimeError('Pagination bloquée')
        seen.add(next_cursor);cursor=next_cursor
    for item in unmatched:print('SANS CORRESPONDANCE :',*item)
    print(f'Bilan : {checked} défis anciens, {matched} résultats concordants, {settled} validations D1.')

if __name__=='__main__':main()
