#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lieux_tournois.py — où se joue chaque tournoi, et quel temps il y fait (22/10/2026, point 5).

Pour chaque tournoi des feuilles de match (feuilles/*.jsonl.gz) :
  — LIEU, une seule fois : ville et pays tirés du nom TennisApi (« Genoa, Italy »,
    « US Open, New York, USA »), puis géocodage Open-Meteo (gratuit, sans clé, données
    GeoNames) → latitude, longitude, ALTITUDE, fuseau, code pays (ISO alpha-2) ;
  — MÉTÉO de chaque jour de matchs : température maximale et vent maximal du jour
    (archive Open-Meteo pour les jours passés de plus de 6 jours ; prévision Open-Meteo,
    avec les 7 derniers jours, pour les tournois en cours — remplacée par l'archive
    ensuite). Salle (« indoor ») : la météo ne compte pas, mais elle est gardée.
Sorties : feuilles/tournois.json {id: {nom, ville, pays, code, lat, lon, altitude, fuseau}}
          feuilles/meteo.json    {id: {jour: [t_max °C, vent_max km/h, source]}}
Une requête de géocodage par tournoi nouveau, une requête météo par tournoi et par
semaine ; budget par passage (défaut 400 requêtes).
Usage : python scripts/lieux_tournois.py [budget]
"""
import datetime as dt
import glob
import gzip
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
DOSSIER = os.path.join(ICI, '..', 'feuilles')
F_TOURNOIS = os.path.join(DOSSIER, 'tournois.json')
F_METEO = os.path.join(DOSSIER, 'meteo.json')
GEO = 'https://geocoding-api.open-meteo.com/v1/search'
ARCHIVE = 'https://archive-api.open-meteo.com/v1/archive'
PREVISION = 'https://api.open-meteo.com/v1/forecast'
DAILY = 'temperature_2m_max,wind_speed_10m_max'
DELAI_ARCHIVE_J = 6

# Noms de pays TennisApi → nom GeoNames (anglais) quand ils diffèrent.
ALIAS_PAYS = {'usa': 'united states', 'uk': 'united kingdom', 'great britain': 'united kingdom', 'england': 'united kingdom',
              'turkiye': 'turkey', 'türkiye': 'turkey', 'czechia': 'czech republic', 'korea': 'south korea',
              'korea republic': 'south korea', 'chinese taipei': 'taiwan', 'uae': 'united arab emirates',
              'russia': 'russia', 'the netherlands': 'netherlands', 'holland': 'netherlands', 'bosnia': 'bosnia and herzegovina',
              'ivory coast': "côte d'ivoire", 'hong kong': 'hong kong', 'macau': 'macao'}


def lire(chemin, defaut):
    try:
        with open(chemin, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def ecrire(chemin, doc):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    os.replace(chemin + '.tmp', chemin)


def ville_pays(nom):
    """(ville, pays) depuis « Genoa, Italy », « US Open, New York, USA », « Phan Thiet 3, Vietnam »."""
    parts = [p.strip() for p in str(nom or '').split(',') if p.strip()]
    if not parts:
        return None, None
    pays = parts[-1] if len(parts) >= 2 else None
    ville = parts[-2] if len(parts) >= 2 else parts[0]
    ville = re.sub(r'\s+\d+$', '', ville).strip()                 # « Phan Thiet 3 » → « Phan Thiet »
    ville = re.sub(r'\b(WTA|ATP|ITF|Challenger|Open|Men|Women|Singles|Doubles)\b', '', ville, flags=re.I).strip(' -')
    return ville or None, pays


def choisir_resultat(resultats, pays):
    """Résultat du géocodage dont le pays correspond ; sinon le plus peuplé."""
    if not resultats:
        return None
    if pays:
        p = ALIAS_PAYS.get(pays.lower(), pays.lower())
        bons = [r for r in resultats if str(r.get('country', '')).lower() == p or str(r.get('country_code', '')).lower() == p]
        if bons:
            return max(bons, key=lambda r: r.get('population') or 0)
    return max(resultats, key=lambda r: r.get('population') or 0)


class Client:
    def __init__(self, budget):
        self.budget, self.n = budget, 0

    def get(self, url, params):
        if self.n >= self.budget:
            raise RuntimeError('budget atteint')
        self.n += 1
        q = url + '?' + urllib.parse.urlencode(params)
        for essai in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(q, headers={'User-Agent': 'tennis-edge/1.0'}), timeout=30) as r:
                    return json.loads(r.read().decode('utf-8'))
            except Exception as e:  # noqa: BLE001
                if essai == 2:
                    print(f"  échec {url.split('/')[2]} : {type(e).__name__}")
                    return None
                time.sleep(2 * (essai + 1))
        return None


def tournois_des_feuilles():
    """{id: {'nom': nom complet, 'jours': set, 'interieur': bool}}."""
    out = {}
    for p in sorted(glob.glob(os.path.join(DOSSIER, '*.jsonl.gz'))):
        try:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                for l in f:
                    r = json.loads(l)
                    i = str(r.get('tournoi_id') or r.get('tournoi') or '')
                    if not i or not r.get('jour'):
                        continue
                    e = out.setdefault(i, {'nom': r.get('tournoi') or r.get('tournoi_unique'), 'jours': set(), 'interieur': False})
                    e['jours'].add(r['jour'])
                    e['interieur'] |= 'indoor' in str(r.get('surface') or '').lower()
        except (OSError, ValueError):
            continue
    return out


def semaines(jours):
    """Jours regroupés en plages consécutives (écart ≤ 3 jours) : une requête météo par plage."""
    js = sorted(dt.date.fromisoformat(j) for j in jours)
    out, cur = [], []
    for d in js:
        if cur and (d - cur[-1]).days > 3:
            out.append(cur)
            cur = []
        cur.append(d)
    if cur:
        out.append(cur)
    return [(c[0], c[-1]) for c in out]


def main(argv):
    budget = int(argv[1]) if len(argv) > 1 and argv[1] else 400
    T, MET = lire(F_TOURNOIS, {}), lire(F_METEO, {})
    vus = tournois_des_feuilles()
    c = Client(budget)
    aujourd = dt.datetime.now(dt.timezone.utc).date()
    n_geo = n_met = 0
    try:
        for i, e in vus.items():
            if i in T and T[i].get('lat') is not None:
                T[i]['interieur'] = e['interieur']
                continue
            ville, pays = ville_pays(e['nom'])
            if not ville or (T.get(i) or {}).get('essais', 0) >= 2:
                continue
            doc = c.get(GEO, {'name': ville, 'count': 10, 'language': 'en', 'format': 'json'})
            r = choisir_resultat((doc or {}).get('results') or [], pays)
            n_geo += 1
            if r:
                T[i] = {'nom': e['nom'], 'ville': ville, 'pays': r.get('country'), 'code': r.get('country_code'),
                        'lat': r.get('latitude'), 'lon': r.get('longitude'), 'altitude': r.get('elevation'),
                        'fuseau': r.get('timezone'), 'interieur': e['interieur']}
            else:
                T[i] = dict(T.get(i) or {}, nom=e['nom'], ville=ville, essais=(T.get(i) or {}).get('essais', 0) + 1)
        for i, e in vus.items():
            t = T.get(i) or {}
            if t.get('lat') is None:
                continue
            M = MET.setdefault(i, {})
            for d0, d1 in semaines(e['jours']):
                manque = [d for d in (d0 + dt.timedelta(days=k) for k in range((d1 - d0).days + 1))
                          if d.isoformat() in e['jours'] and (d.isoformat() not in M or M[d.isoformat()][2] == 'prevision')]
                if not manque:
                    continue
                ancien = all((aujourd - d).days > DELAI_ARCHIVE_J for d in manque)
                if ancien:
                    doc = c.get(ARCHIVE, {'latitude': t['lat'], 'longitude': t['lon'], 'start_date': min(manque).isoformat(),
                                          'end_date': max(manque).isoformat(), 'daily': DAILY, 'timezone': 'auto'})
                    src = 'archive'
                elif (aujourd - max(manque)).days <= DELAI_ARCHIVE_J:
                    doc = c.get(PREVISION, {'latitude': t['lat'], 'longitude': t['lon'], 'daily': DAILY, 'timezone': 'auto',
                                            'past_days': 7, 'forecast_days': 3})
                    src = 'prevision'
                else:
                    continue
                n_met += 1
                dd = (doc or {}).get('daily') or {}
                for j, tx, vx in zip(dd.get('time') or [], dd.get('temperature_2m_max') or [], dd.get('wind_speed_10m_max') or []):
                    if tx is not None and (j in e['jours'] or src == 'prevision'):
                        if src == 'archive' or j not in M or M[j][2] == 'prevision':
                            M[j] = [round(tx, 1), round(vx or 0.0, 1), src]
    except RuntimeError as e:
        print(f"::warning::Arrêt : {e}")
    ecrire(F_TOURNOIS, T)
    ecrire(F_METEO, MET)
    alt = sorted(((v.get('altitude') or 0, v.get('ville')) for v in T.values() if v.get('lat') is not None), reverse=True)[:5]
    print(f"Tournois : {len(vus)} dans les feuilles · {sum(1 for v in T.values() if v.get('lat') is not None)} situés · "
          f"géocodages {n_geo} · requêtes météo {n_met} · total {c.n} requêtes · plus hauts : {alt}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
