#!/usr/bin/env python3
"""Importateur Arena V1.7. Source JSON explicitement configurée, sans cotes."""
import datetime as dt, json, os, sys, urllib.request, urllib.error
from pathlib import Path
from urllib.parse import urlparse
import collections, re, unicodedata, subprocess, tempfile

API='https://tennis-edge-arena.tennis-edge.workers.dev/api/arena/admin/challenge'
MAX_MATCHES=30
# Par défaut : un seul défi lors du premier import réel.
try:
    REQUESTED_LIMIT=int(os.environ.get("ARENA_IMPORT_LIMIT", "1"))
except ValueError:
    raise SystemExit("ARENA_IMPORT_LIMIT doit être un entier")
if not 1 <= REQUESTED_LIMIT <= MAX_MATCHES:
    raise SystemExit("ARENA_IMPORT_LIMIT doit être entre 1 et 30")


def is_placeholder(name):
    """Refuse les têtes de série non renseignées et les codes de tableau."""
    n=unicodedata.normalize('NFKC',name).strip().casefold()
    compact=re.sub(r'[\s._-]+','',n)
    if re.fullmatch(r'(?:r\d{1,3}p\d{1,3}|q\d{1,3}|qualifier\d*|tbd|bye|unknown|player\d+|joueur\d+|seed\d+)',compact):return True
    if re.search(r'\b(?:tbd|to be determined|winner of|vainqueur de|qualifier|qualifié à déterminer)\b',n):return True
    return False

def auth_diagnostic(token):
    """Le Worker valide le jeton avant de valider le JSON. {} => 400 sans D1 si auth OK."""
    url=API
    req=urllib.request.Request(url,data=b'{}',headers={
        'Content-Type':'application/json','Accept':'application/json',
        'x-arena-admin-token':token,'User-Agent':'TennisEdgeArenaAuthCheck/1.7.3'
    },method='POST')
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            status=r.status; content=r.read(500).decode('utf-8','replace');ctype=r.headers.get('content-type','')
    except urllib.error.HTTPError as e:
        status=e.code;content=e.read(500).decode('utf-8','replace');ctype=e.headers.get('content-type','')
        print('AUTH diagnostic HTTP',status,'type:',ctype,'cf-ray:',e.headers.get('cf-ray','?'))
    if status==400 and 'Invalid challenge' in content:
        print('AUTH OK : jeton accepté par le Worker, JSON volontairement invalide. AUCUNE écriture D1.')
        return
    if status==403 and 'Forbidden' in content and 'application/json' in ctype:
        raise SystemExit('AUTH REFUSÉE PAR WORKER : vérifier ARENA_ADMIN_TOKEN dans GitHub ET Cloudflare (sans divulguer le secret).')
    if status==403 and ('1010' in content or 'text/html' in ctype):
        raise SystemExit('BLOCAGE CLOUDFLARE AVANT WORKER : HTTP 403, possiblement code 1010. Inspecter événements sécurité/Access/Bot.')
    raise SystemExit(f'Réponse inattendue à la sonde auth : HTTP {status}, type {ctype}. Aucune écriture demandée.')

def main():
    dry=os.environ.get('DRY_RUN','').lower() in ('true','1','yes')
    if os.environ.get('ARENA_DIAGNOSTIC','').lower() in ('true','1','yes') and not dry:
        token=os.environ.get('ARENA_ADMIN_TOKEN','')
        if not token:raise SystemExit('Secret ARENA_ADMIN_TOKEN manquant dans GitHub Actions')
        auth_diagnostic(token)
        return
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
        if is_placeholder(a) or is_placeholder(b):continue
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
    # Bloquer les rencontres contradictoires : même joueur dans deux matchs
    # programmés au même instant ou à moins de 2 h (même circuit).
    selected.sort(key=lambda x:x['starts_at'])
    blocked=set()
    by_player=collections.defaultdict(list)
    def player_key(name):
        return re.sub(r'\s+',' ',name.casefold().strip())
    for idx,m in enumerate(selected):
        when=dt.datetime.fromisoformat(m['starts_at'].replace('Z','+00:00'))
        for player in (m['player_a'],m['player_b']):
            by_player[(m['circuit'],player_key(player))].append((idx,when))
    for (_,player),entries in by_player.items():
        for pos,(idx,when) in enumerate(entries):
            for jdx,other in entries[pos+1:]:
                if abs((when-other).total_seconds())<7200:
                    blocked.update((idx,jdx))
                    print('CONFLIT :',player,selected[idx]['title'],selected[idx]['starts_at'], '/',selected[jdx]['title'],selected[jdx]['starts_at'])
    if blocked:print(f'Sécurité : {len(blocked)} défis contradictoires exclus.')
    selected=[m for i,m in enumerate(selected) if i not in blocked][:REQUESTED_LIMIT]
    print(f'Flux lu: {len(matches)} entrées, {len(selected)} matchs éligibles (limite demandée {REQUESTED_LIMIT} par exécution).')
    if dry:
        for m in selected:print('SIMULATION',m['circuit'],m['title'],m['player_a'],'vs',m['player_b'],m['starts_at'])
        return
    token=os.environ.get('ARENA_ADMIN_TOKEN','')
    if not token:raise SystemExit('Secret ARENA_ADMIN_TOKEN manquant')
    # Utilise curl (pile TLS/HTTP différente d'urllib) pour tester le blocage
    # Cloudflare 1010 sans modifier les protections Cloudflare.
    # Le secret ne figure jamais dans les arguments du processus ni dans les logs.
    created=existing=0
    for m in selected:
        print('IMPORT CIBLE :',m['circuit'],m['title'],m['player_a'],'vs',m['player_b'],m['starts_at'],flush=True)
        payload=json.dumps(m,ensure_ascii=False,separators=(',',':'))
        with tempfile.TemporaryDirectory(prefix='arena-import-') as tmp:
            body_file=Path(tmp)/'payload.json'
            response_file=Path(tmp)/'response.json'
            header_file=Path(tmp)/'headers.txt'
            body_file.write_text(payload,encoding='utf-8')
            # curl lit la configuration sensible sur stdin; jamais sur la ligne de commande.
            config='\n'.join([
                'url = '+json.dumps(API),
                'request = "POST"',
                'header = "Content-Type: application/json"',
                'header = "Accept: application/json"',
                'header = '+json.dumps('x-arena-admin-token: '+token),
                'user-agent = "TennisEdgeArena/1.7.5"',
                'connect-timeout = 10',
                'max-time = 25',
                'retry = 0',
                'silent',
                'show-error',
            ])+'\n'
            cmd=['curl','--config','-','--data-binary','@'+str(body_file),
                 '--output',str(response_file),'--dump-header',str(header_file),
                 '--write-out','%{http_code}']
            try:
                res=subprocess.run(cmd,input=config,text=True,capture_output=True,timeout=35,check=False)
            except (subprocess.TimeoutExpired,OSError) as e:
                raise SystemExit('Transport curl indisponible ou expiré : import arrêté.') from e
            if res.returncode:
                raise SystemExit('Erreur réseau curl (code '+str(res.returncode)+'). Aucun nouvel essai automatique.')
            status=int(res.stdout.strip() or '0')
            response=response_file.read_text(encoding='utf-8',errors='replace')[:600]
            if status not in (200,201):
                ray=re.search(r'(?im)^cf-ray:\s*([^\r\n]+)',header_file.read_text(errors='replace'))
                print('ÉCHEC IMPORT HTTP',status,'cf-ray:',ray.group(1) if ray else 'absent',
                      'réponse:',response[:200],flush=True)
                if status==403 and '1010' in response:
                    raise SystemExit('Blocage Cloudflare 1010 persistant avec curl. Ne pas désactiver la sécurité : inspecter la règle Cloudflare ou prévoir un canal interne authentifié.')
                if status==403:
                    raise SystemExit('403 Worker/Cloudflare : vérifier le corps et les événements de sécurité.')
                raise SystemExit('Import refusé : HTTP '+str(status))
            try:result=json.loads(response_file.read_text(encoding='utf-8'))
            except ValueError:raise SystemExit('Réponse Worker non JSON : import arrêté.')
            if result.get('ok') is not True or not result.get('id'):
                raise SystemExit('Réponse Worker inattendue : import arrêté.')
            created+=bool(result.get('created',status==201))
            existing+=not bool(result.get('created',status==201))
            print('WORKER OK : défi',result['id'],'créé' if result.get('created',status==201) else 'déjà présent')
    print(f'Import terminé : {created} créés, {existing} déjà présents.')
if __name__=='__main__':main()
