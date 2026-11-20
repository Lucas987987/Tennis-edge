#!/usr/bin/env python3
"""sonde_classements.py — 30/10/2026 : TennisApi peut-il donner les points ATP/WTA AU-DELÀ du top 500 ?

LECTURE SEULE, 12 requêtes au plus, rien n'est écrit. Les classements du jour (classements_tennisapi.py) s'arrêtent à
500 joueurs par circuit ; les points des joueurs Challenger plus loin datent de juin (archive Sackmann). On essaie :
  1. les chemins de classement connus et quelques variantes (page, limite) : nombre de lignes, dernier rang lu ;
  2. la fiche de 2 joueurs Challenger classés au-delà de 500 (identifiants pris dans les feuilles d'hier) :
     /api/tennis/player/{id} et /api/tennis/team/{id} — champs dont le nom contient rank, point, ranking.
"""
import datetime as dt
import glob
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feuilles_match as FM  # noqa: E402
import classements_tennisapi as CT  # noqa: E402

MOTS = ('rank', 'point')


def champs(x, chemin='', out=None):
    out = [] if out is None else out
    if isinstance(x, dict):
        for k, v in x.items():
            p = f'{chemin}.{k}' if chemin else k
            if any(m in k.lower() for m in MOTS) and not isinstance(v, (dict, list)):
                out.append((p, v))
            champs(v, p, out)
    elif isinstance(x, list):
        for i, v in enumerate(x[:2]):
            champs(v, f'{chemin}[{i}]', out)
    return out


def main():
    c = FM.Client(os.environ['RAPIDAPI_KEY'], budget=12, reserve=500, pause=0.5)
    connus = set()
    for p in ('/api/tennis/rankings/atp', '/api/tennis/rankings/atp?page=1', '/api/tennis/rankings/atp/1',
              '/api/tennis/rankings/atp?limit=2000', '/api/tennis/rankings/wta', '/api/tennis/rankings/atp/live'):
        code, doc = c.get(p)
        cl = CT.lire_classement(doc) if code == 200 else {}
        connus |= set(cl)
        print(f"{code} {p} : {len(cl)} joueurs, dernier rang {max((v[0] for v in cl.values()), default=None)}, "
              f"clés {list((doc or {}).keys())[:8]}")
    # 2 joueurs Challenger d'hier absents du top 500
    hier = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
    ids = []
    for chemin in sorted(glob.glob(os.path.join('feuilles', hier + '.jsonl.gz'))):
        for l in gzip.open(chemin, 'rt', encoding='utf-8'):
            r = json.loads(l)
            if 'challenger' not in str(r.get('categorie') or '').lower():
                continue
            for cote in ('home', 'away'):
                j = r.get(cote) or {}
                import elo as E
                if j.get('id') and E.cle(j.get('nom') or '') not in connus:
                    ids.append((j['id'], j.get('nom')))
    for pid, nom in ids[:2]:
        for p in (f'/api/tennis/player/{pid}', f'/api/tennis/team/{pid}'):
            code, doc = c.get(p)
            print(f"{code} {p} ({nom}) :", champs(doc)[:20] or (list((doc or {}).keys())[:10]))
    print('requêtes', c.n, 'quota restant', c.restant)
    return 0


if __name__ == '__main__':
    sys.exit(main())
