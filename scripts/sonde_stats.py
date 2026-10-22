#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sonde_stats.py — quelle API donne les FEUILLES DE MATCH (aces, doubles fautes,
1re balle, points gagnés derrière la 1re et la 2e balle, balles de break) ? (22/10/2026)

Deux API gratuites de RapidAPI (même clé RAPIDAPI_KEY que OddsPapi, après
abonnement à leur formule gratuite sur rapidapi.com) :
  matchstat : « Tennis API - ATP WTA ITF »  (tennis-api-atp-wta-itf.p.rapidapi.com)
  tennisapi : « TennisApi »                 (tennisapi1.p.rapidapi.com)

Pour chacune, AU PLUS 3 requêtes, jamais de nouvelle tentative :
  1. la liste des matchs d'un jour terminé (hier par défaut) ;
  2-3. le détail ou les statistiques d'un match ATP (ou WTA) et d'un Challenger,
       si la liste ne les contient pas déjà. Les chemins des statistiques ne sont
       pas tous documentés : la sonde suit les liens fournis par l'API elle-même,
       puis essaie le chemin habituel, et s'arrête à 3 requêtes.

Le rapport ne contient JAMAIS la clé. Il décrit : code HTTP (403 = pas abonné),
quota restant (en-têtes RapidAPI), structure des réponses, circuits présents
(Challenger ?), et chaque statistique de service trouvée (nom, chemin, valeur,
comptes « gagnés / total » si présents). Les données elles-mêmes ne sont pas
gardées : seulement des extraits courts dans le journal du run.

Usage : python scripts/sonde_stats.py [AAAA-MM-JJ] [matchstat,tennisapi]
Sortie : sonde_stats.json (non commité).
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

SORTIE = 'sonde_stats.json'
MAX_REQ = 3
MOTS_STATS = re.compile(r'ace|double|fault|first.?serve|1st|second.?serve|2nd|break.?point|bp_?|serve|service|'
                        r'service.?points|return', re.I)
MOTS_CH = re.compile(r'challenger', re.I)


# ------------------------------------------------------------------ réseau
class Client:
    def __init__(self, hote, cle, ouvrir=None, max_req=MAX_REQ):
        self.hote, self.cle, self.n, self.max = hote, cle, 0, max_req
        self.ouvrir = ouvrir or urllib.request.urlopen
        self.journal = []

    def get(self, chemin):
        """Une requête, jamais répétée. Renvoie (code, json ou None)."""
        if self.n >= self.max:
            return None, None
        self.n += 1
        req = urllib.request.Request(f"https://{self.hote}{chemin}", headers={
            'X-RapidAPI-Key': self.cle, 'X-RapidAPI-Host': self.hote, 'Accept': 'application/json'})
        code, doc, ent = None, None, {}
        try:
            with self.ouvrir(req, timeout=25) as r:
                code = r.status
                ent = {k.lower(): v for k, v in r.headers.items()}
                brut = r.read()
        except urllib.error.HTTPError as e:
            code = e.code
            ent = {k.lower(): v for k, v in (e.headers or {}).items()}
            brut = e.read() if hasattr(e, 'read') else b''
        except Exception as e:  # noqa: BLE001
            self.journal.append({'chemin': chemin, 'erreur': type(e).__name__})
            return None, None
        try:
            doc = json.loads(brut.decode('utf-8', 'replace')) if brut else None
        except ValueError:
            doc = {'_texte': brut[:300].decode('utf-8', 'replace')}
        quota = {k: v for k, v in ent.items() if 'ratelimit' in k}
        self.journal.append({'chemin': chemin, 'code': code, 'octets': len(brut or b''), 'quota': quota,
                             'structure': structure(doc), 'message': message(doc) if code != 200 else None})
        return code, doc


def message(doc):
    if isinstance(doc, dict):
        for k in ('message', 'error', 'errors', '_texte'):
            if doc.get(k):
                return str(doc[k])[:300]
    return None


# ------------------------------------------------------------------ lecture des réponses
def structure(doc, prof=0, max_prof=4):
    """Squelette d'un JSON : types, clés, longueur des listes (premier élément seulement)."""
    if prof >= max_prof:
        return type(doc).__name__
    if isinstance(doc, dict):
        return {k: structure(v, prof + 1, max_prof) for k, v in list(doc.items())[:40]}
    if isinstance(doc, list):
        return [f"liste de {len(doc)}", structure(doc[0], prof + 1, max_prof)] if doc else ['liste vide']
    if isinstance(doc, str):
        return f"str({doc[:40]})"
    return type(doc).__name__


def parcourir(doc, chemin=''):
    """(chemin, valeur) de toutes les feuilles."""
    if isinstance(doc, dict):
        for k, v in doc.items():
            yield from parcourir(v, f"{chemin}.{k}" if chemin else str(k))
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            yield from parcourir(v, f"{chemin}[{i}]")
    else:
        yield chemin, doc


def stats_trouvees(doc, limite=60):
    """Statistiques de service repérées : soit une clé parlante, soit un objet {name: 'Aces', value…}."""
    out, vus = [], set()
    for ch, v in parcourir(doc):
        cle = ch.rsplit('.', 1)[-1]
        if isinstance(v, str) and MOTS_STATS.search(v) and re.search(r'name|type|title|label|key', cle, re.I):
            # objet nommé : on garde ses voisins (valeurs home/away, gagnés/total)
            parent = ch.rsplit('.', 1)[0]
            voisins = {c.rsplit('.', 1)[-1]: w for c, w in parcourir(_a(doc, parent)) if '.' not in c and '[' not in c}
            k = (v, tuple(sorted(voisins)))
            if k not in vus:
                vus.add(k)
                out.append({'stat': v, 'chemin': parent, 'valeurs': {a: b for a, b in voisins.items() if a != cle}})
        elif MOTS_STATS.search(cle) and isinstance(v, (int, float, str)) and not isinstance(v, bool):
            k = (cle, ch)
            if cle not in vus:
                vus.add(cle)
                out.append({'stat': cle, 'chemin': ch, 'valeurs': {'valeur': v}})
        if len(out) >= limite:
            break
    return out


def _a(doc, chemin):
    """Valeur au chemin « a.b[2].c »."""
    cur = doc
    for p in re.findall(r'[^.\[\]]+|\[\d+\]', chemin):
        if p.startswith('['):
            i = int(p[1:-1])
            cur = cur[i] if isinstance(cur, list) and i < len(cur) else None
        else:
            cur = cur.get(p) if isinstance(cur, dict) else None
        if cur is None:
            return None
    return cur


def matchs_de(doc):
    """La liste de matchs la plus probable dans une réponse (la plus longue liste de dicts)."""
    best = []

    def voir(x):
        nonlocal best
        if isinstance(x, list) and x and all(isinstance(e, dict) for e in x[:5]) and len(x) > len(best):
            best = x
        if isinstance(x, dict):
            for v in x.values():
                voir(v)
        elif isinstance(x, list):
            for v in x[:3]:
                voir(v)
    voir(doc)
    return best


def texte(m):
    return ' '.join(str(v) for _, v in parcourir(m) if isinstance(v, str))


def choisir(matchs):
    """Un match du grand circuit et un Challenger, terminés si l'information existe."""
    fini = [m for m in matchs if re.search(r'finished|ended|complete|"?status"?.*(100|ft)', texte(m), re.I)] or matchs
    ch = next((m for m in fini if MOTS_CH.search(texte(m))), None)
    tour = next((m for m in fini if not MOTS_CH.search(texte(m)) and not re.search(r'\bitf\b|double', texte(m), re.I)), None)
    return [x for x in (tour, ch) if x is not None]


def ident(m):
    for k in ('id', 'matchId', 'match_id', 'eventId', 'event_id', 'event_key', 'fixture_id'):
        if isinstance(m, dict) and m.get(k) not in (None, ''):
            return m[k]
    return None


def liens(m):
    """Chemins d'API fournis par l'API elle-même dans un match (champ links…)."""
    out = []
    for ch, v in parcourir(m):
        if isinstance(v, str) and v.startswith('/') and re.search(r'stat|live|match|detail|event', v, re.I):
            out.append(v)
    return out


def resume_match(m):
    return {'id': ident(m), 'extrait': texte(m)[:200]}


# ------------------------------------------------------------------ les deux API
def sonder_matchstat(cle, jour, ouvrir=None):
    c = Client('tennis-api-atp-wta-itf.p.rapidapi.com', cle, ouvrir)
    rep = {'api': 'Matchstat — Tennis API ATP WTA ITF', 'jour': jour}
    code, doc = c.get(f"/tennis/v2/atp/results/{jour}")
    rep['liste_code'] = code
    M = matchs_de(doc) if code == 200 else []
    rep['matchs_dans_la_liste'] = len(M)
    rep['challenger_present'] = any(MOTS_CH.search(texte(m)) for m in M)
    rep['stats_dans_la_liste'] = stats_trouvees(M[:5])
    rep['matchs_testes'] = []
    for m in choisir(M):
        if c.n >= c.max:
            break
        essais = liens(m) or ([f"/tennis/v2/matches/{ident(m)}/live?type=atp"] if ident(m) else [])
        for ch in essais[:1]:
            code2, d2 = c.get(ch)
            rep['matchs_testes'].append({'match': resume_match(m), 'chemin': ch, 'code': code2,
                                         'stats': stats_trouvees(d2) if code2 == 200 else []})
    rep['requetes'] = c.journal
    return rep


def sonder_tennisapi(cle, jour, ouvrir=None):
    c = Client('tennisapi1.p.rapidapi.com', cle, ouvrir)
    rep = {'api': 'TennisApi (RapidAPI, fluis.lacasse)', 'jour': jour}
    d = dt.date.fromisoformat(jour)
    code, doc = c.get(f"/api/tennis/events/{d.day}/{d.month}/{d.year}")
    if code in (204, 404):
        # 22/10/2026 : 204 (vide) sur la liste du jour -> on essaie les matchs en cours.
        code, doc = c.get("/api/tennis/events/live")
    rep['liste_code'] = code
    M = matchs_de(doc) if code == 200 else []
    rep['matchs_dans_la_liste'] = len(M)
    rep['challenger_present'] = any(MOTS_CH.search(texte(m)) for m in M)
    rep['stats_dans_la_liste'] = stats_trouvees(M[:5])
    rep['matchs_testes'] = []
    for m in choisir(M):
        if c.n >= c.max or ident(m) is None:
            continue
        ch = f"/api/tennis/event/{ident(m)}/statistics"
        code2, d2 = c.get(ch)
        rep['matchs_testes'].append({'match': resume_match(m), 'chemin': ch, 'code': code2,
                                     'stats': stats_trouvees(d2) if code2 == 200 else []})
    rep['requetes'] = c.journal
    return rep


HOTES = {'matchstat': 'tennis-api-atp-wta-itf.p.rapidapi.com', 'tennisapi': 'tennisapi1.p.rapidapi.com'}


def explorer(cle, api, chemins, ouvrir=None):
    """Chemins choisis à la main (copiés depuis la page « Endpoints » de RapidAPI), 3 au plus :
    structure de la réponse, statistiques repérées et un court extrait."""
    c = Client(HOTES[api], cle, ouvrir)
    out = []
    for ch in chemins[:MAX_REQ]:
        code, doc = c.get(ch)
        out.append({'chemin': ch, 'code': code, 'stats': stats_trouvees(doc) if code == 200 else [],
                    'matchs': len(matchs_de(doc)) if code == 200 else 0,
                    'extrait': json.dumps(doc, ensure_ascii=False)[:1500] if code == 200 else None})
    return {'api': api, 'exploration': out, 'requetes': c.journal}


SONDES = {'matchstat': sonder_matchstat, 'tennisapi': sonder_tennisapi}
ESSENTIEL = ('ace', 'double', 'first serve|1st serve', 'second serve|2nd serve', 'break point')


def verdict(rep):
    """Ce qu'on retient pour une API : abonnement, liste, Challenger, stats essentielles trouvées."""
    if rep.get('liste_code') in (401, 403):
        return "pas abonné (s'abonner à la formule gratuite sur rapidapi.com, puis relancer)"
    if rep.get('liste_code') == 429:
        return 'quota dépassé'
    if rep.get('liste_code') != 200:
        return f"liste des matchs indisponible (HTTP {rep.get('liste_code')})"
    tout = rep['stats_dans_la_liste'] + [s for t in rep['matchs_testes'] for s in t['stats']]
    noms = ' '.join(str(s['stat']) for s in tout)
    manque = [e for e in ESSENTIEL if not re.search(e, noms, re.I)]
    comptes = any(any(re.search(r'won|total|count|home|away|value', k, re.I) for k in s['valeurs']) for s in tout)
    if not tout:
        return 'aucune statistique de service trouvée'
    return (f"statistiques trouvées ({len(tout)}) ; manquantes : {', '.join(manque) or 'aucune'} ; "
            f"comptes bruts : {'oui' if comptes else 'à vérifier'} ; Challenger dans la liste : "
            f"{'oui' if rep['challenger_present'] else 'non'}")


def main(argv):
    cle = os.environ.get('RAPIDAPI_KEY', '').strip()
    if not cle:
        print('::error::RAPIDAPI_KEY absent')
        return 1
    jour = argv[1] if len(argv) > 1 and argv[1] else (dt.date.today() - dt.timedelta(days=1)).isoformat()
    quelles = (argv[2] if len(argv) > 2 and argv[2] else 'matchstat,tennisapi').split(',')
    out = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'jour': jour, 'api': {}}
    chemins = [x.strip() for x in (argv[3] if len(argv) > 3 else '').split(',') if x.strip().startswith('/')]
    if chemins:
        api = quelles[0].strip()
        if api not in HOTES:
            print(f"::error::API inconnue : {api}")
            return 1
        rep = explorer(cle, api, chemins)
        out['api'][api] = rep
        print(f"\n===== Exploration {api} =====")
        for r, e in zip(rep['requetes'], rep['exploration']):
            print(f"  GET {r['chemin']} -> {r.get('code')} ({r.get('octets', 0)} octets) quota restant "
                  f"{r.get('quota', {}).get('x-ratelimit-requests-remaining')}" + (f" · {r['message']}" if r.get('message') else ''))
            print(f"    matchs : {e['matchs']} · structure : {json.dumps(r.get('structure'), ensure_ascii=False)[:800]}")
            for s in e['stats'][:30]:
                print(f"    - {s['stat']} : {json.dumps(s['valeurs'], ensure_ascii=False)[:160]}")
            if e['extrait']:
                print(f"    extrait : {e['extrait'][:1200]}")
        with open(SORTIE, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return 0
    for q in quelles:
        q = q.strip()
        if q not in SONDES:
            continue
        rep = SONDES[q](cle, jour)
        rep['verdict'] = verdict(rep)
        out['api'][q] = rep
        print(f"\n===== {rep['api']} =====")
        print(f"Verdict : {rep['verdict']}")
        for r in rep['requetes']:
            print(f"  GET {r['chemin']} -> {r.get('code')} ({r.get('octets', 0)} octets) quota {r.get('quota')}"
                  + (f" · {r['message']}" if r.get('message') else ''))
        print(f"  matchs dans la liste : {rep['matchs_dans_la_liste']} · Challenger : {rep['challenger_present']}")
        for t in rep['matchs_testes']:
            print(f"  match testé : {t['match']['extrait'][:120]}")
            for s in t['stats'][:25]:
                print(f"    - {s['stat']} : {json.dumps(s['valeurs'], ensure_ascii=False)[:160]}")
        for s in rep['stats_dans_la_liste'][:25]:
            print(f"    (liste) {s['stat']} : {json.dumps(s['valeurs'], ensure_ascii=False)[:160]}")
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\nRapport : {SORTIE} (aucune clé dedans)")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
