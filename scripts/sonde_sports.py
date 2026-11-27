#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sonde_sports.py — QUEL AUTRE SPORT APRÈS LE TENNIS DE TABLE ? (27/11/2026, paquet 505, Lucas : « fais le », « on peut
partir sur la NBA… d'autres championnats de basket ? d'autres sports ? »).

LECTURE SEULE. Rien n'est écrit dans le dépôt : tout est dans le journal du run, qui ne montre que des codes HTTP, des
comptes, des tailles et des noms de compétitions (jamais la clé, jamais de cote, jamais un nom de joueur).

Source : AllSportsApi (formule Pro jusqu'au ~26/12/2026 : c'est pendant ce mois qu'un historique peut être collecté).
Pour chaque sport (badminton, volley-ball, beach-volley, fléchettes, snooker, basket-ball), AU PLUS une douzaine de
requêtes :
  1. hier : combien de matchs, dans quelles catégories (pays / circuits) ;
  2. l'historique : y a-t-il des matchs il y a 1, 2, 3, 4 et 5 ans (et combien) ?
  3. la plus grosse catégorie d'hier (pour le basket : aussi « USA » et l'Europe) : les compétitions, les matchs
     terminés, la forme du score (nombre de périodes / sets, valeurs typiques), le format annoncé, la taille de la
     réponse (bande passante) ;
  4. un match terminé : statistiques du match ? compositions (et, pour le basket, minutes par joueur) ?
Usage : python scripts/sonde_sports.py
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import allsports as AS  # noqa: E402

SPORTS = (('badminton', ('badminton',)), ('volley-ball', ('volleyball',)), ('beach-volley', ('beach-volley', 'beachvolley')),
          ('fléchettes', ('darts',)), ('snooker', ('snooker',)), ('basket-ball', ('basketball',)))
ANNEES = (1, 2, 3, 4, 5)
BASKET_EN_PLUS = ('usa', 'europe', 'international', 'france', 'spain')


def categories(doc):
    """[(nom, id, matchs)] triées par matchs décroissants."""
    out = []
    for x in (doc or {}).get('categories') or []:
        cat = x.get('category') or {}
        if cat.get('id') and x.get('totalEvents'):
            out.append((str(cat.get('name') or '?'), cat['id'], int(x['totalEvents'])))
    return sorted(out, key=lambda c: -c[2])


def periodes(e):
    h, a = e.get('homeScore') or {}, e.get('awayScore') or {}
    out = []
    for k in range(1, 12):
        p = f'period{k}'
        if isinstance(h.get(p), int) and isinstance(a.get(p), int):
            out.append((h[p], a[p]))
    return out


def termines(doc):
    return [e for e in (doc or {}).get('events') or [] if (e.get('status') or {}).get('type') == 'finished']


def _jour(c, slug, d):
    return c.get(f'/api/{slug}/calendar/{d.day}/{d.month}/{d.year}/categories')


def categorie(c, slug, nom_cat, cat_id, d, journal):
    avant = c.octets
    code, doc = c.get(f'/api/{slug}/category/{cat_id}/events/{d.day}/{d.month}/{d.year}')
    ko = (c.octets - avant) // 1024
    T = termines(doc)
    comp = {}
    for e in (doc or {}).get('events') or []:
        t = (e.get('tournament') or {})
        n = (t.get('uniqueTournament') or {}).get('name') or t.get('name') or '?'
        comp[n] = comp.get(n, 0) + 1
    P = [periodes(e) for e in T]
    nper = {}
    for p in P:
        nper[len(p)] = nper.get(len(p), 0) + 1
    formats = {}
    for e in T:
        f = e.get('defaultPeriodCount') or e.get('bestOf')
        formats[f] = formats.get(f, 0) + 1
    tours = sum(1 for e in T if (e.get('roundInfo') or {}).get('name') or (e.get('roundInfo') or {}).get('round'))
    exemple = P[0] if P else []
    journal(f"   {nom_cat} (hier) : HTTP {code}, {len((doc or {}).get('events') or [])} matchs dont {len(T)} terminés, "
            f"réponse {ko} Ko")
    journal(f"     compétitions : {', '.join(f'{k} {v}' for k, v in sorted(comp.items(), key=lambda x: -x[1])[:8])}")
    journal(f"     périodes par match terminé : {dict(sorted(nper.items()))} ; exemple de score par période {exemple} ; "
            f"format annoncé {formats} ; tour connu {tours}/{len(T)}")
    return T


def detail(c, slug, e, basket, journal):
    code, st = c.get(f"/api/{slug}/event/{e['id']}/statistics")
    groupes = sum(len(p.get('groups') or []) for p in (st or {}).get('statistics') or []) if code == 200 else 0
    journal(f"   un match terminé : statistiques HTTP {code} ({groupes} groupes)")
    code, lu = c.get(f"/api/{slug}/event/{e['id']}/lineups")
    joueurs = minutes = 0
    if code == 200 and isinstance(lu, dict):
        for cote in ('home', 'away'):
            for j in (lu.get(cote) or {}).get('players') or []:
                joueurs += 1
                s = j.get('statistics') or {}
                if s.get('secondsPlayed') or s.get('minutesPlayed'):
                    minutes += 1
    journal(f"   un match terminé : compositions HTTP {code} ({joueurs} joueurs"
            + (f", temps de jeu connu pour {minutes}" if basket else '') + ')')


def sonder_sport(c, nom, slugs, hier, journal):
    journal(f"== {nom}")
    slug, idx = None, None
    for s in slugs:
        code, doc = _jour(c, s, hier)
        if code == 200 and categories(doc):
            slug, idx = s, doc
            break
        journal(f"   « {s} » : HTTP {code}, rien")
    if not slug:
        return {'sport': nom, 'trouve': False}
    L = categories(idx)
    total = sum(x[2] for x in L)
    journal(f"   « {slug} » hier ({hier}) : {total} matchs dans {len(L)} catégories : "
            + ', '.join(f'{n} {k}' for n, _, k in L[:12]))
    hist = {}
    for k in ANNEES:
        d = hier.replace(year=hier.year - k)
        code, doc = _jour(c, slug, d)
        Lk = categories(doc) if code == 200 else []
        hist[k] = sum(x[2] for x in Lk)
        journal(f"   il y a {k} an(s) ({d}) : HTTP {code}, {hist[k]} matchs dans {len(Lk)} catégories")
    basket = slug == 'basketball'
    choix = [L[0]] if L else []
    if basket:
        choix += [x for x in L[1:] if any(m in x[0].lower() for m in BASKET_EN_PLUS)][:3]
    T = []
    for n, i, _ in choix:
        T = categorie(c, slug, n, i, hier, journal) or T
    if T:
        detail(c, slug, T[0], basket, journal)
    return {'sport': nom, 'trouve': True, 'hier': total, 'historique': hist}


def sonder(c, aujourdhui=None, journal=print):
    hier = (aujourdhui or dt.date.today()) - dt.timedelta(days=1)
    res = []
    for nom, slugs in SPORTS:
        try:
            res.append(sonder_sport(c, nom, slugs, hier, journal))
        except AS.Arret as e:
            journal(f"   arrêt du client : {e}")
            break
    journal('== bilan : ' + ' ; '.join(f"{r['sport']} {r.get('hier', 0)} matchs hier, il y a 5 ans "
                                         f"{(r.get('historique') or {}).get(5, 0)}" for r in res))
    if hasattr(c, 'bilan'):
        journal(f'   {c.bilan()}')
    return res


def main():
    cle = os.environ.get('RAPIDAPI_KEY')
    if not cle:
        print('sonde_sports : RAPIDAPI_KEY absente')
        return 0
    sonder(AS.Client(cle, minutes=15))
    return 0


if __name__ == '__main__':
    sys.exit(main())
