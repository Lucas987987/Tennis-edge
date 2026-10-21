#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nos_resultats.py — nos matchs joués depuis juin 2026 (21/10/2026).

Noms et tournoi : clv_history (avec la clôture Pinnacle) et closing_lines ;
résultat : set_results.json (vainqueur du match, set 1, set 2), retrouvé par
date et paire de joueurs (identifiant exact, ou date ± 1 jour, dans les deux
ordres). Surface : déduite du nom du tournoi grâce aux tournois de l'archive
Sackmann (table construite par surfaces_tournois), « Hard » à défaut.
"""
import datetime as dt
import glob
import importlib.util
import json
import os
import re
import sys
import unicodedata

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.abspath(os.path.join(ICI, '..'))
_sp = importlib.util.spec_from_file_location('tennis_edge_nr_books', os.path.join(RACINE, 'Tennis_Edge_Lab', 'books.py'))
books = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(books)

MOTS_VIDES = {'atp', 'wta', 'itf', 'challenger', 'men', 'women', 'singles', 'masters', 'open', 'ch', 'qualifying',
              'qualifiers', 'qualification', 'the', 'de', 'cup', 'championships', 'international', 'grand', 'prix',
              'tennis', 'classic', 'trophy', 'w', 'm', 'h', 'ladies'}


def slug(s):
    s = unicodedata.normalize('NFD', str(s or '').lower().strip())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')


def mots_tournoi(t):
    return [m for m in re.split(r'[^a-z]+', slug(t).replace('_', ' ')) if len(m) > 2 and m not in MOTS_VIDES]


def surfaces_tournois(matchs_sackmann, depuis=dt.date(2023, 1, 1)):
    """{mot du tournoi: surface la plus fréquente} depuis l'archive Sackmann."""
    c = {}
    for m in matchs_sackmann:
        if m['date'] < depuis:
            continue
        for w in mots_tournoi(m.get('tournoi')):
            d = c.setdefault(w, {})
            d[m['surface']] = d.get(m['surface'], 0) + 1
    return {w: max(d, key=d.get) for w, d in c.items()}


def surface_de(tournoi, table):
    votes = {}
    for w in mots_tournoi(tournoi):
        if w in table:
            votes[table[w]] = votes.get(table[w], 0) + 1
    return max(votes, key=votes.get) if votes else 'Hard'


def cinq_sets(t):
    t = str(t or '')
    return bool(re.search(r'(wimbledon|us open|french open|roland|australian open)', t, re.I)) and \
        bool(re.search(r'\bmen', t, re.I)) and not re.search(r'women', t, re.I)


def _jsonl(path):
    try:
        with open(path, encoding='utf-8') as f:
            for l in f:
                try:
                    yield json.loads(l)
                except ValueError:
                    continue
    except OSError:
        return


def charger(racine=RACINE, table_surfaces=None):
    """[{date, debut, home, away, tournoi, surface, bo, gagnant ('home'/'away'), sets ('2-0'… du point de vue home),
    set1, pin (cote juste home, ou None)}] triés par heure de début."""
    try:
        sr = json.load(open(os.path.join(racine, 'set_results.json'), encoding='utf-8'))
    except (OSError, ValueError):
        sr = {}
    cand = {}
    for f in sorted(glob.glob(os.path.join(racine, 'clv_history', '*.jsonl'))) + [os.path.join(racine, 'clv_history.jsonl')]:
        for r in _jsonl(f):
            if r.get('home') and r.get('away') and r.get('commence_time'):
                k = (str(r['commence_time'])[:10], frozenset((slug(r['home']), slug(r['away']))))
                cand[k] = r
    try:
        sys.path.insert(0, os.path.join(racine, 'scripts'))
        import closing_store
        cwd = os.getcwd()
        os.chdir(racine)
        try:
            cl = closing_store.load_all('closing_lines.json', max_age_days=None)
        finally:
            os.chdir(cwd)
        for m in cl.values():
            if m.get('home') and m.get('away') and m.get('commence_time'):
                k = (str(m['commence_time'])[:10], frozenset((slug(m['home']), slug(m['away']))))
                cand.setdefault(k, m)
    except Exception as e:  # noqa: BLE001
        print(f"  closing_lines non lu ({type(e).__name__}) : clv_history seul")
    out = []
    for (jour, _), r in cand.items():
        try:
            d0 = dt.date.fromisoformat(jour)
            debut = dt.datetime.fromisoformat(str(r['commence_time']).replace('Z', '').split('+')[0])
        except ValueError:
            continue
        h, a = r['home'], r['away']
        res, sens = None, 1
        for d in (d0, d0 - dt.timedelta(days=1), d0 + dt.timedelta(days=1)):
            k1, k2 = f"{d}_{slug(h)}_{slug(a)}", f"{d}_{slug(a)}_{slug(h)}"
            if sr.get(k1, {}).get('match') in ('home', 'away'):
                res, sens = sr[k1], 1
                break
            if sr.get(k2, {}).get('match') in ('home', 'away'):
                res, sens = sr[k2], -1
                break
        if not res:
            continue
        o = (lambda v: v) if sens == 1 else (lambda v: {'home': 'away', 'away': 'home'}.get(v))
        g, s1, s2 = o(res.get('match')), o(res.get('set1')), o(res.get('set2'))
        bo = 5 if cinq_sets(r.get('tournament')) else 3
        sets = None
        if bo == 3 and s1 in ('home', 'away') and s2 in ('home', 'away') and not (s1 == s2 and g != s1):
            sets = ('2-0' if g == 'home' else '0-2') if s1 == s2 else ('2-1' if g == 'home' else '1-2')
        pin = None
        try:
            ch, ca = float(r['home_metrics']['close']), float(r['away_metrics']['close'])
            if ch > 1 and ca > 1:
                k = books.power_exponent(ch, ca)
                pin = (1 / ch) ** k if k else (1 / ch) / (1 / ch + 1 / ca)
        except (KeyError, TypeError, ValueError):
            pass
        out.append({'date': d0, 'debut': debut, 'home': h, 'away': a, 'tournoi': r.get('tournament') or '',
                    'surface': surface_de(r.get('tournament'), table_surfaces or {}), 'bo': bo, 'gagnant': g,
                    'sets': sets, 'set1': s1 if s1 in ('home', 'away') else None, 'pin': pin})
    out.sort(key=lambda x: x['debut'])
    return out
