#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sonde_tennis_de_table.py — 26/11/2026 : a-t-on les données pour faire au tennis de table
ce qu'on fait au tennis ?

LECTURE SEULE. Rien n'est écrit dans le dépôt : tout est dans le journal du run, et le
journal ne montre que des codes HTTP, des comptes et des noms de ligues (jamais la clé,
jamais de cote).

Source testée : « AllSportsApi » de RapidAPI (allsportsapi2.p.rapidapi.com), même auteur
et même forme de réponses que TennisApi. Il faut s'être abonné à sa formule gratuite
(Basic) sur rapidapi.com avec le compte de RAPIDAPI_KEY ; sinon les réponses sont 403
et la sonde le dit. Le quota du tennis (tennisapi1) n'est PAS touché.

Quatre questions, AU PLUS 15 requêtes, jamais de nouvelle tentative :
  1. Le tennis de table répond-il, et sous quel nom (« table-tennis » ou « tabletennis ») ?
  2. Combien de matchs par jour et dans quelles ligues (Setka Cup, Czech Liga Pro, TT Elite
     Series, WTT…) ? Un seul appel par jour grâce à l'index du calendrier.
  3. L'historique : y a-t-il des matchs il y a 1, 2, 3, 4 et 5 ans ?
  4. Le détail d'un match terminé, récent puis ancien : score de chaque manche (donc les
     points gagnés par chacun), service, et déroulé point par point ?
"""
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

HOTE = 'allsportsapi2.p.rapidapi.com'
NOMS_SPORT = ('table-tennis', 'tabletennis')
MAX_REQ = 15
ANNEES = (1, 2, 3, 4, 5)
MOTS_LIGUES = ('setka', 'czech', 'liga pro', 'elite', 'tt cup', 'wtt', 'ittf', 'champions', 'pro league')


class Client:
    def __init__(self, cle, ouvrir=None, max_req=MAX_REQ):
        self.cle, self.n, self.max = cle, 0, max_req
        self.ouvrir = ouvrir or urllib.request.urlopen
        self.codes, self.reste = [], None

    def get(self, chemin):
        """Une requête, jamais répétée. Renvoie (code, json ou None)."""
        if self.n >= self.max:
            return None, None
        self.n += 1
        req = urllib.request.Request(f"https://{HOTE}{chemin}", headers={
            'X-RapidAPI-Key': self.cle, 'X-RapidAPI-Host': HOTE, 'Accept': 'application/json'})
        brut, ent = b'', {}
        try:
            with self.ouvrir(req, timeout=25) as r:
                code = r.status
                ent = {k.lower(): v for k, v in dict(r.headers).items()}
                brut = r.read()
        except urllib.error.HTTPError as e:
            code = e.code
            ent = {k.lower(): v for k, v in dict(e.headers or {}).items()}
        except Exception as e:  # noqa: BLE001
            code = type(e).__name__
        self.codes.append(code)
        r = ent.get('x-ratelimit-requests-remaining')
        if r is not None:
            self.reste = r
        try:
            return code, (json.loads(brut.decode('utf-8', 'replace')) if brut else None)
        except ValueError:
            return code, None


def ligues(doc):
    """[(nom, id, matchs)] de l'index du calendrier, du plus fourni au moins fourni."""
    out = []
    for c in (doc or {}).get('categories') or []:
        cat = c.get('category') or {}
        out.append((str(cat.get('name')), cat.get('id'), int(c.get('totalEvents') or 0)))
    return sorted(out, key=lambda x: -x[2])


def total(L):
    return sum(x[2] for x in L)


def choisir_ligue(L):
    for nom, i, n in L:
        if n and any(m in nom.lower() for m in MOTS_LIGUES):
            return nom, i, n
    return next(((nom, i, n) for nom, i, n in L if n), None)


def termines(doc):
    return [e for e in (doc or {}).get('events') or []
            if (e.get('status') or {}).get('type') == 'finished' and e.get('id')]


def manches(e):
    """Scores des manches d'un match terminé : [(11, 7), (9, 11), …]."""
    h, a = e.get('homeScore') or {}, e.get('awayScore') or {}
    out = []
    for k in range(1, 8):
        p = f'period{k}'
        if isinstance(h.get(p), int) and isinstance(a.get(p), int):
            out.append((h[p], a[p]))
    return out


def compter(doc, cles=('homePoint', 'awayPoint', 'point')):
    """Nombre de points détaillés trouvés dans un déroulé, quelle que soit sa forme."""
    n = 0
    if isinstance(doc, dict):
        if any(k in doc for k in cles):
            n += 1
        for v in doc.values():
            n += compter(v, cles)
    elif isinstance(doc, list):
        for v in doc:
            n += compter(v, cles)
    return n


def detail(c, sport, e, etiquette, journal):
    m = manches(e)
    pts = [sum(x[0] for x in m), sum(x[1] for x in m)]
    journal(f"  {etiquette} : {len(m)} manches lues dans le score, {pts[0] + pts[1]} points au total, "
            f"service connu {'oui' if e.get('firstToServe') in (1, 2) else 'non'}")
    code, pbp = c.get(f"/api/{sport}/event/{e['id']}/point-by-point")
    n = compter(pbp) if code == 200 else 0
    cles = list(pbp.keys())[:6] if isinstance(pbp, dict) else []
    journal(f"  {etiquette} : déroulé point par point HTTP {code}, {n} points détaillés, clés {cles}")
    return {'manches': len(m), 'points': pts[0] + pts[1], 'pbp_code': code, 'pbp_points': n}


def sonder(cle, aujourdhui=None, ouvrir=None, journal=print, noms=NOMS_SPORT):
    """noms : les noms possibles du sport (26/11 : réutilisé pour le badminton)."""
    c = Client(cle, ouvrir)
    hier = (aujourdhui or dt.date.today()) - dt.timedelta(days=1)
    res = {'sport': None}

    # 1. le nom du sport
    idx = None
    for s in noms:
        code, doc = c.get(f"/api/{s}/calendar/{hier.day}/{hier.month}/{hier.year}/categories")
        journal(f"1. « {s} » : HTTP {code}")
        if code == 200 and ligues(doc):
            res['sport'], idx = s, doc
            break
        if code in (401, 403):
            journal("   403 = pas abonné à AllSportsApi (formule Basic gratuite sur rapidapi.com) : arrêt")
            res['abonnement'] = False
            break
    if not res['sport']:
        journal(f"Bilan : {noms[0]} introuvable — {c.n} requêtes, codes {c.codes}, quota restant {c.reste}")
        return res
    sport = res['sport']

    # 2. un jour de matchs
    L = ligues(idx)
    res['hier'] = {'matchs': total(L), 'ligues': len(L)}
    journal(f"2. {hier} : {total(L)} matchs dans {len(L)} ligues")
    for nom, _, n in L[:12]:
        journal(f"   {n:5d}  {nom}")

    # 4a. un match récent en détail
    ch = choisir_ligue(L)
    if ch:
        code, doc = c.get(f"/api/{sport}/category/{ch[1]}/events/{hier.day}/{hier.month}/{hier.year}")
        T = termines(doc)
        journal(f"4. {ch[0]} le {hier} : HTTP {code}, {len(T)} matchs terminés")
        if T:
            res['recent'] = detail(c, sport, T[0], 'match récent', journal)

    # 3. l'historique
    res['historique'] = {}
    ancien = None
    for k in ANNEES:
        d = hier.replace(year=hier.year - k)
        code, doc = c.get(f"/api/{sport}/calendar/{d.day}/{d.month}/{d.year}/categories")
        Lk = ligues(doc) if code == 200 else []
        res['historique'][str(d)] = total(Lk)
        principales = ', '.join(f"{nom} {n}" for nom, _, n in Lk[:3])
        journal(f"3. {d} : HTTP {code}, {total(Lk)} matchs dans {len(Lk)} ligues ({principales})")
        if k == 3 and Lk:
            ancien = (d, choisir_ligue(Lk))

    # 4b. un match ancien en détail
    if ancien and ancien[1]:
        d, (nom, i, _) = ancien
        code, doc = c.get(f"/api/{sport}/category/{i}/events/{d.day}/{d.month}/{d.year}")
        T = termines(doc)
        journal(f"4. {nom} le {d} : HTTP {code}, {len(T)} matchs terminés")
        if T:
            res['ancien'] = detail(c, sport, T[0], 'match ancien', journal)

    journal(f"Bilan : {c.n} requêtes, codes {c.codes}, quota restant {c.reste}")
    return res


def main():
    cle = os.environ.get('RAPIDAPI_KEY')
    if not cle:
        print('sonde_tennis_de_table : RAPIDAPI_KEY absente')
        return 0
    sonder(cle)
    return 0


if __name__ == '__main__':
    sys.exit(main())
