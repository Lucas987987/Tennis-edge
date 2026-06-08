#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
discover_rapidapi_tournaments.py — Découvre automatiquement les tournois ATP/WTA
actifs (matchs dans les ~10 prochains jours) via l'API RapidAPI
'tennis-api-atp-wta-itf' et écrit tournois_ids.json au format {nom: {tour, id}}.

C'est la source d'IDs du flux rapide (fetch_results_fast.py). Lancé avant lui
(ou 1×/jour), il garde la liste à jour quand le calendrier change (terre -> gazon...).

Endpoint utilisé (doc officielle) :
  GET /tennis/v2/{tour}/fixtures/{startdate}/{enddate}?include=tournament&filter=PlayerGroup:singles
  -> renvoie {data:[{..., tournamentId, tournament:{id,name,...}}], hasNextPage}

Clé via env RAPIDAPI_KEY.
"""
import urllib.request, urllib.error, json, os, datetime

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
HOST = 'tennis-api-atp-wta-itf.p.rapidapi.com'
IDS_FILE = os.environ.get('TOURN_IDS_FILE', 'tournois_ids.json')
DAYS_AHEAD = int(os.environ.get('DISCOVER_DAYS', '10'))

HEADERS = {
    'x-rapidapi-host': HOST,
    'x-rapidapi-key': RAPIDAPI_KEY,
    'Accept': 'application/json',
    'User-Agent': 'tennis-edge/1.0',
}


def api_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read()), r.headers.get('x-ratelimit-requests-remaining', '?')
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:200]
        print(f"  ⚠️ HTTP {e.code}: {body}")
        return None, '?'
    except Exception as e:
        print(f"  ⚠️ Erreur réseau: {e}")
        return None, '?'


def discover():
    if not RAPIDAPI_KEY:
        print("❌ RAPIDAPI_KEY absente — abandon")
        return {}

    today = datetime.date.today()
    frm = today.isoformat()
    to = (today + datetime.timedelta(days=DAYS_AHEAD)).isoformat()
    active = {}
    remaining = '?'

    for tour in ('atp', 'wta'):
        page = 1
        while True:
            url = (f"https://{HOST}/tennis/v2/{tour}/fixtures/{frm}/{to}"
                   f"?include=tournament&filter=PlayerGroup:singles&pageSize=100&pageNo={page}")
            data, remaining = api_get(url)
            if data is None:
                break
            items = data.get('data', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            if not items:
                break
            for fx in items:
                if not isinstance(fx, dict):
                    continue
                t = fx.get('tournament') or {}
                tid = t.get('id') or fx.get('tournamentId')
                name = (t.get('name') or '').strip()
                if tid and name:
                    active[f"{tour.upper()} {name}"] = {'tour': tour, 'id': tid}
            has_next = data.get('hasNextPage') if isinstance(data, dict) else False
            if not has_next:
                break
            page += 1
            if page > 20:   # garde-fou anti-boucle
                break

    real = {k: v for k, v in active.items() if not k.startswith('_')}
    if not real:
        print("⚠️ Aucun tournoi actif découvert — on garde tournois_ids.json existant")
        return {}

    active['_discovered_at'] = datetime.datetime.utcnow().isoformat()
    with open(IDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(active, f, ensure_ascii=False, indent=2)
    print(f"✅ {len(real)} tournois actifs écrits dans {IDS_FILE} (quota restant: {remaining})")
    for k, v in real.items():
        print(f"   {str(v['id']):>7} | {k}")
    return active


if __name__ == '__main__':
    discover()
