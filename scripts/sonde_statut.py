#!/usr/bin/env python3
"""sonde_statut.py — 29/10/2026 : TennisApi donne-t-il le statut d'entrée (« WC » invité, « Q » qualifié) AVANT le
match ? Nos feuilles n'en contiennent aucun alors que feuilles_match.py lit homeTeamSeed depuis le 23/10.
LECTURE SEULE, 3 requêtes au plus (index du jour, liste Challenger du jour, détail d'un match à venir) ; rien n'est
écrit. Le journal montre chaque champ dont le nom contient « seed », « rank » ou « entry », et où il se trouve."""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feuilles_match as FM  # noqa: E402

MOTS = ('seed', 'rank', 'entry', 'wildcard', 'qualif')


def champs(x, chemin='', out=None):
    out = [] if out is None else out
    if isinstance(x, dict):
        for k, v in x.items():
            p = f'{chemin}.{k}' if chemin else k
            if any(m in k.lower() for m in MOTS):
                out.append((p, v if not isinstance(v, (dict, list)) else type(v).__name__))
            champs(v, p, out)
    elif isinstance(x, list):
        for i, v in enumerate(x[:3]):
            champs(v, f'{chemin}[{i}]', out)
    return out


def main():
    c = FM.Client(os.environ['RAPIDAPI_KEY'], budget=3, reserve=500, pause=0.5)
    d = dt.datetime.now(dt.timezone.utc).date()
    code, idx = c.get(f"/api/tennis/calendar/{d.day}/{d.month}/{d.year}/categories")
    print('index', code)
    cats = FM.categories_du_jour(idx, ('challenger', 'atp')) if code == 200 else []
    print('catégories', [(k['id'], k['nom'], k['matchs']) for k in cats][:5])
    cid = cats[0]['id'] if cats else None
    if not cid:
        print('pas de catégorie Challenger aujourd’hui'); return 0
    code, doc = c.get(f"/api/tennis/category/{cid}/events/{d.day}/{d.month}/{d.year}")
    ev = (doc or {}).get('events') or []
    print('liste', code, len(ev), 'matchs')
    vus = {}
    for e in ev:
        for p, v in champs(e):
            vus.setdefault(p.split('.')[0] + '.' + p.split('.')[-1] if '.' in p else p, set()).add(str(v)[:20])
    print('CHAMPS DANS LA LISTE :')
    for k, v in sorted(vus.items()):
        print(f'  {k} : {sorted(v)[:15]}')
    print('clés d’un match de la liste :', sorted(ev[0].keys()) if ev else None)
    print('clés de homeTeam :', sorted((ev[0].get('homeTeam') or {}).keys()) if ev else None)
    venir = [e for e in ev if (e.get('status') or {}).get('type') == 'notstarted'] or ev
    if venir:
        code, det = c.get(f"/api/tennis/event/{venir[0]['id']}")
        print('détail', code, venir[0].get('homeTeam', {}).get('name'), '–', venir[0].get('awayTeam', {}).get('name'))
        print('CHAMPS DANS LE DÉTAIL :')
        for p, v in champs(det):
            print(f'  {p} : {v}')
    print('requêtes', c.n, 'quota restant', c.restant)
    return 0


if __name__ == '__main__':
    sys.exit(main())
