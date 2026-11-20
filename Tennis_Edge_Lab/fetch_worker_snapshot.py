#!/usr/bin/env python3
"""Capture publique en lecture seule de l'API /api/hypotheses du Worker D1.
Aucun jeton. Le résultat est un snapshot non critique : une panne D1 n'interrompt
jamais la publication de Tennis Edge et n'est jamais présentée comme synchronisée.
"""
import datetime as dt
import json
import os
from pathlib import Path
import sys
import urllib.request

URL = 'https://tennis-edge-db.tennis-edge.workers.dev/api/hypotheses'
DEST = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / 'worker_hypotheses.json'
now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
payload = {'schema_version': 1, 'status': 'unavailable', 'fetched_at': now, 'source_url': URL, 'hypotheses': []}
try:
    req = urllib.request.Request(URL, headers={'User-Agent': 'TennisEdgeLab-ReadOnly-Audit/2.1', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status != 200: raise ValueError(f'HTTP {resp.status}')
        data_bytes = resp.read(200001)
    if len(data_bytes) > 200000: raise ValueError('Réponse trop volumineuse')
    data = json.loads(data_bytes)
    if not isinstance(data, dict) or not isinstance(data.get('hypotheses'), list):
        raise ValueError('API ne fournit pas hypotheses[]')
    if not isinstance(data.get('genere_le'), str): raise ValueError('genere_le absent')
    seen = set()
    for h in data['hypotheses']:
        if not isinstance(h, dict) or not isinstance(h.get('code'), str) or not isinstance(h.get('out_of_sample'), dict):
            raise ValueError('Structure d\'hypothèse invalide')
        code = h['code'].upper()
        if code in seen: raise ValueError('Code hypothèse dupliqué')
        seen.add(code)
        oos = h['out_of_sample']
        if not isinstance(oos.get('n'), int) or oos['n'] < 0:
            raise ValueError('Effectif invalide')
    payload.update({'status': 'ok', 'worker_generated_at': data['genere_le'], 'hypotheses': data['hypotheses']})
except Exception as exc:
    payload['error'] = f'{type(exc).__name__}: {str(exc)[:150]}'
    print('⚠ Worker D1 indisponible :', payload['error'])
DEST.parent.mkdir(parents=True, exist_ok=True)
DEST.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
print(f'Worker snapshot: {payload["status"]}, {len(payload["hypotheses"])} hypothèses -> {DEST}')
