#!/usr/bin/env python3
"""sonde_statut.py — 29/10/2026 : TennisApi donne-t-il le statut d'entrée (« WC » invité, « Q » qualifié) AVANT le
match ? Nos feuilles n'en contiennent aucun alors que feuilles_match.py lit homeTeamSeed depuis le 23/10.
LECTURE SEULE, 14 requêtes au plus (index du jour, liste Challenger du jour, détail de 12 matchs du jour) ; rien n'est
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
    c = FM.Client(os.environ['RAPIDAPI_KEY'], budget=14, reserve=500, pause=0.5)
    d = dt.datetime.now(dt.timezone.utc).date()
    code, idx = c.get(f"/api/tennis/calendar/{d.day}/{d.month}/{d.year}/categories")
    print('index', code)
    cats = FM.categories_du_jour(idx, ('challenger',)) if code == 200 else []
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
    # 29/10/2026 (v2) : le 1er essai n'a lu qu'un match ATP sans statut ; ici 12 matchs Challenger du tableau final
    # (les invités et qualifiés n'y sont que là), au plus 12 requêtes
    tab = [e for e in ev if not ((e.get('tournament') or {}).get('qualificationOrPreliminary'))][:12]
    print(len(tab), 'matchs du tableau final interrogés')
    tous = {}
    for e in tab:
        code, det = c.get(f"/api/tennis/event/{e['id']}")
        ch = champs(det)
        print(f"  {code} {e.get('homeTeam', {}).get('name')} – {e.get('awayTeam', {}).get('name')} :",
              {p: v for p, v in ch if 'seed' in p.lower() or 'entry' in p.lower()} or 'aucun statut')
        for p, v in ch:
            tous.setdefault(p, set()).add(str(v)[:15])
    print('TOUS LES CHAMPS VUS DANS LES DÉTAILS :')
    for k, v in sorted(tous.items()):
        print(f'  {k} : {sorted(v)[:12]}')
    print('requêtes', c.n, 'quota restant', c.restant)
    return 0


if __name__ == '__main__':
    sys.exit(main())
