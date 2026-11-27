#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sonde_sports.py — QUEL AUTRE SPORT APRÈS LE TENNIS DE TABLE ? (27/11/2026, paquet 505, Lucas : « fais le », « on peut
partir sur la NBA… d'autres championnats de basket ? d'autres sports ? »).

LECTURE SEULE. Rien n'est écrit dans le dépôt : tout est dans le journal du run, qui ne montre que des codes HTTP, des
comptes, des tailles et des noms de compétitions (jamais la clé, jamais de cote, jamais un nom de joueur).

Source : AllSportsApi (formule Pro jusqu'au ~26/12/2026 : c'est pendant ce mois qu'un historique peut être collecté).
Pour chaque sport (badminton, volley-ball, beach-volley, fléchettes, snooker, basket-ball), AU PLUS une vingtaine de
requêtes (deuxième version, 27/11 : le premier passage interrogeait l'index du calendrier, qui n'existe que pour le tennis
et le tennis de table — 404 partout) :
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

SPORTS = (('badminton', ('badminton',)), ('volley-ball', ('volleyball',)), ('beach-volley', ('beach-volley', 'beach-volleyball')),
          ('fléchettes', ('darts',)), ('snooker', ('snooker',)), ('basket-ball', ('basketball',)))
ANNEES = (1, 2, 3, 4, 5)
# 505bis : l'index du calendrier par catégories n'existe que pour le tennis et le tennis de table (premier passage : 404
# partout). Pour les autres sports, la doc d'AllSportsApi donne les matchs d'un jour par sport
# (/api/{sport}/matches/{j}/{m}/{a} ou /api/{sport}/events/{j}/{m}/{a}) et la liste des catégories
# (/api/{sport}/tournament/categories), puis les matchs d'un jour par catégorie.
JOUR = ('matches', 'events')
CATEGORIES_VISEES = ('international', 'europe', 'usa', 'world', 'france', 'spain', 'italy', 'poland', 'england', 'germany')


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


def matchs_du_jour(c, slug, d, chemins=JOUR):
    """(chemin qui marche, [événements]) — None si aucun chemin ne répond."""
    for ch in chemins:
        code, doc = c.get(f'/api/{slug}/{ch}/{d.day}/{d.month}/{d.year}')
        if code == 200 and isinstance(doc, dict):
            return ch, (doc.get('events') or [])
    return None, []


def par_categorie(E):
    out = {}
    for e in E:
        cat = ((e.get('tournament') or {}).get('category') or {}).get('name') or '?'
        out[cat] = out.get(cat, 0) + 1
    return sorted(out.items(), key=lambda x: -x[1])


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
    for slug in slugs:
        code, doc = c.get(f'/api/{slug}/tournament/categories')
        cats = [(str((x or {}).get('name') or '?'), (x or {}).get('id')) for x in (doc or {}).get('categories') or []] \
            if code == 200 and isinstance(doc, dict) else []
        journal(f"   « {slug} » : catégories HTTP {code}, {len(cats)} catégories")
        if code == 200:
            break
    else:
        return {'sport': nom, 'trouve': False}
    ch, E = matchs_du_jour(c, slug, hier)
    T = [e for e in E if (e.get('status') or {}).get('type') == 'finished']
    hist = {}
    if ch:
        journal(f"   hier ({hier}, /{ch}/) : {len(E)} matchs dont {len(T)} terminés : "
                + ', '.join(f'{k} {v}' for k, v in par_categorie(E)[:12]))
        for k in ANNEES:
            d = hier.replace(year=hier.year - k)
            _, Ek = matchs_du_jour(c, slug, d, (ch,))
            hist[k] = len(Ek)
            journal(f"   il y a {k} an(s) ({d}) : {len(Ek)} matchs ; " + ', '.join(f'{a} {b}' for a, b in par_categorie(Ek)[:4]))
    else:
        journal("   pas de liste des matchs du jour : par catégorie")
    visees = [x for x in cats if x[1] and any(m in x[0].lower() for m in CATEGORIES_VISEES)][:4]
    for n, i in visees:
        Tc = categorie(c, slug, n, i, hier, journal)
        T = T or Tc
        if not ch:
            d = hier.replace(year=hier.year - 3)
            code, doc = c.get(f'/api/{slug}/category/{i}/events/{d.day}/{d.month}/{d.year}')
            journal(f"     {n} il y a 3 ans : HTTP {code}, {len((doc or {}).get('events') or [])} matchs")
    if T:
        detail(c, slug, T[0], slug == 'basketball', journal)
    return {'sport': nom, 'trouve': True, 'hier': len(E), 'historique': hist}


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
