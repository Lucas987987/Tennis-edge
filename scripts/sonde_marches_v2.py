#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sonde_marches_v2.py — quels marchés tennis sont cotés, et par qui ? (29/10/2026, lecture seule)

Question : peut-on comparer nos lignes figées (score en sets, total de jeux, handicap, tie-break, aces, points…)
aux cotes des bookmakers ? Aujourd'hui on ne relève que le vainqueur du match et des sets 1 et 2.

Ce que fait la sonde (≈ 3 requêtes OddsPapi + ≈ 4 requêtes TennisApi), rien d'autre :
  OddsPapi   1. /markets (sportId 12)             : la liste des marchés tennis (identifiant, nom)
             2. /fixtures/today                   : les matchs du jour (ATP, WTA, Challenger ; pas ITF ni simulés)
             3. /fixtures/odds/main (≤ 8 matchs)   : quels marchés chaque bookmaker cote vraiment sur ces matchs
  TennisApi  4. /api/tennis/event/{id}/odds/1/all  : les marchés du fournisseur de TennisApi, sur 3 matchs du jour
Rapport : sonde_marches_v2.json (artefact du run, pas de commit) et un résumé dans le journal. Complète la sonde du 21/10 (scripts/sonde_marches.py : l'historique d'UN match chez UN bookmaker) : ici
tous les bookmakers suivis sur les matchs du jour, et TennisApi. Aucune collecte : la
décision de collecter viendra après lecture, avec une règle fixée avant de comparer à nos lignes.
Les cotes ne servent qu'à comparer : elles n'entrent jamais dans l'algo.

Env : RAPIDAPI_KEY. Usage : python scripts/sonde_marches_v2.py
"""
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

INTERET = re.compile(r'total|set|ace|handicap|spread|point|tie|break|game|jeu|correct|score|over|under|double',
                     re.I)
BOOKS = os.environ.get('SONDE_BOOKS', 'pinnacle,bet365,winamax.fr,betclic.fr,unibet,bwin,betsson,1xbet,williamhill')
N_MATCHS = int(os.environ.get('SONDE_MATCHS', '8'))


def nom_marche(m):
    return str(m.get('marketName') or m.get('name') or m.get('marketNameEn') or '')


def sonde_oddspapi(rapport):
    import oddspapi_v5 as ov
    os.environ.setdefault('ODDS_RETRIES', '0')
    marches, st = ov.api_get('/markets', {'sportId': ov.TENNIS_SPORT_ID})
    L = marches if isinstance(marches, list) else (marches or {}).get('markets') or []
    noms = {}
    for m in L:
        mid = m.get('marketId') or m.get('id')
        if mid is not None:
            noms[str(mid)] = {'nom': nom_marche(m), 'issues': [str(o.get('outcomeName') or o.get('name') or '')
                                                              for o in (m.get('outcomes') or [])][:6]}
    rapport['oddspapi'] = {'marches_tennis': len(noms), 'statut_markets': st,
                           'marches_interessants': {k: v for k, v in noms.items() if INTERET.search(v['nom'])}}
    fx = [f for f in ov.fixtures_today() if not ov.is_srl(f)]
    garde = []
    for f in fx:
        me = ov.fixture_meta(f)
        t = me['tournamentName'].lower()
        if 'itf' in t or me['live']:
            continue
        garde.append(me)
        if len(garde) >= N_MATCHS:
            break
    rapport['oddspapi']['matchs_sondes'] = [f"{m['p1name']} – {m['p2name']} ({m['tournamentName']})" for m in garde]
    if not garde:
        return
    cotes = ov.odds_main_by_fixtures([m['fixtureId'] for m in garde], BOOKS)
    par_book = {}
    for f in cotes or []:
        for book, issues in (f.get('odds') or {}).items():
            for v in (issues or {}).values():
                if not isinstance(v, dict) or v.get('marketId') is None:
                    continue
                mid = str(v['marketId'])
                d = par_book.setdefault(book, {}).setdefault(mid, {'matchs': set(), 'lignes': set()})
                d['matchs'].add(f.get('fixtureId'))
                for k in ('handicap', 'line', 'points', 'specialBetValue', 'marketParameters'):
                    if v.get(k) not in (None, ''):
                        d['lignes'].add(str(v[k]))
    rapport['oddspapi']['par_bookmaker'] = {
        b: {mid: {'nom': (noms.get(mid) or {}).get('nom', '?'), 'matchs': len(x['matchs']),
                  'lignes': sorted(x['lignes'])[:8]} for mid, x in sorted(M.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0)}
        for b, M in par_book.items()}
    q = getattr(ov, 'QUOTA', None)
    rapport['oddspapi']['quota'] = q if isinstance(q, dict) else None


def sonde_tennisapi(rapport, cle):
    import feuilles_match as FM
    c = FM.Client(cle, budget=8, reserve=int(os.environ.get('FEUILLES_RESERVE', '1500')))
    auj = dt.datetime.now(dt.timezone.utc).date()
    code, idx = c.get(f"/api/tennis/calendar/{auj.day}/{auj.month}/{auj.year}/categories")
    ids = []
    for cat in FM.categories_du_jour(idx, ('atp', 'wta', 'challenger')) if code == 200 else []:
        code, doc = c.get(f"/api/tennis/category/{cat['id']}/events/{auj.day}/{auj.month}/{auj.year}")
        for e in (doc or {}).get('events') or []:
            if FM.est_simple(e) and (e.get('status') or {}).get('type') == 'notstarted':
                ids.append((e['id'], f"{(e.get('homeTeam') or {}).get('name')} – {(e.get('awayTeam') or {}).get('name')}",
                            cat['nom']))
        if len(ids) >= 3:
            break
    out = []
    for eid, nom, cat in ids[:3]:
        try:
            code, doc = c.get(f"/api/tennis/event/{eid}/odds/1/all")
        except FM.QuotaAtteint as e:
            out.append({'match': nom, 'erreur': str(e)})
            break
        marches = []
        for m in (doc or {}).get('markets') or []:
            marches.append({'nom': m.get('marketName'), 'groupe': m.get('marketGroup'), 'periode': m.get('marketPeriod'),
                            'ligne': m.get('choiceGroup'),
                            'issues': [f"{ch.get('name')} {ch.get('fractionalValue')}" for ch in (m.get('choices') or [])][:4]})
        out.append({'match': nom, 'categorie': cat, 'code': code, 'marches': marches})
    rapport['tennisapi'] = {'requetes': c.n, 'quota_restant': c.restant, 'matchs': out}


def resume(rapport):
    L = ['', '══ SONDE DES MARCHÉS ══']
    o = rapport.get('oddspapi') or {}
    L.append(f"OddsPapi : {o.get('marches_tennis', 0)} marchés tennis déclarés ; matchs sondés : {len(o.get('matchs_sondes') or [])}")
    for k, v in sorted((o.get('marches_interessants') or {}).items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0)[:60]:
        L.append(f"   marché {k} : {v['nom']}  {'/'.join(x for x in v['issues'] if x)[:60]}")
    for b, M in sorted((o.get('par_bookmaker') or {}).items()):
        L.append(f"  {b} : " + ' · '.join(f"{mid} {x['nom'][:28]} ({x['matchs']} m{', lignes ' + ','.join(x['lignes'][:4]) if x['lignes'] else ''})"
                                          for mid, x in M.items()))
    t = rapport.get('tennisapi') or {}
    L.append(f"TennisApi : {t.get('requetes', 0)} requêtes, quota restant {t.get('quota_restant')}")
    for m in t.get('matchs') or []:
        L.append(f"  {m.get('match')} [{m.get('categorie')}] : " + (m.get('erreur') or
                 ' · '.join(f"{x['nom']}{' ' + str(x['ligne']) if x.get('ligne') else ''}" for x in m.get('marches') or [])))
    return '\n'.join(L)


def main():
    cle = os.environ.get('RAPIDAPI_KEY', '').strip()
    if not cle:
        print('::error::RAPIDAPI_KEY absent')
        return 1
    rapport = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'books_demandes': BOOKS}
    for nom, f in (('oddspapi', lambda: sonde_oddspapi(rapport)), ('tennisapi', lambda: sonde_tennisapi(rapport, cle))):
        try:
            f()
        except Exception as e:  # noqa: BLE001 — une moitié de sonde ne doit pas empêcher l'autre
            rapport.setdefault('erreurs', {})[nom] = f"{type(e).__name__}: {e}"
            print(f"::warning::sonde {nom} : {type(e).__name__}: {e}")
    with open('sonde_marches_v2.json', 'w', encoding='utf-8') as f:
        json.dump(rapport, f, ensure_ascii=False, indent=1, default=list)
    print(resume(rapport))
    return 0


if __name__ == '__main__':
    sys.exit(main())
