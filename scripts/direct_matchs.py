#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
direct_matchs.py — petit instantané des matchs à venir / en cours pour l'onglet
« Matchs en direct » du Lab (lu côté navigateur sur raw.githubusercontent.com).

Lancé par courbes_alertes.yml APRÈS les signaux, sur les MÊMES courbes live
(book_curves_live.jsonl, reconstruites depuis parts/live_*) : rien n'est
recalculé ailleurs, aucune requête API.

Contenu (direct_matchs.json, quelques dizaines de Ko, réécrit seulement si le
contenu change) :
  * matchs dont le début est entre maintenant − 3 h et maintenant + 24 h ;
  * Pinnacle : PREMIER point (ouverture) et dernier point AVANT le début, deux côtés — ce que
    live_odds.json ne donne pas (il n'a que le prix courant) ;
  * dernier prix de chaque book, avec son heure ;
  * circuit et surface (mêmes fonctions que l'Explorateur) ;
  * alertes déjà parties sur le match : H13…H18/H14 (journaux en direct),
    PUBLIC (canal_public_log), MOUVEMENT (odds_alerts_log, par paire + début) ;
  * drapeaux des books (jouable, agréé ANJ, commission de bourse).

Env : CURVES (défaut book_curves_live.jsonl), OUT (défaut direct_matchs.json).
"""
import collections
import datetime as dt
import glob
import importlib.util
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
LAB = ROOT / 'Tennis_Edge_Lab'
sys.path.insert(0, str(HERE))

AVANT_H, APRES_H = 3, 24
CODES = ('h13', 'h14', 'h15', 'h16', 'h16b', 'h17', 'h18')


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    return module


books = _load(LAB / 'books.py', 'tennis_edge_dm_books')
meta = _load(LAB / 'tennis_meta.py', 'tennis_edge_dm_meta')


def _dt(s):
    try:
        d = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return (d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)


def _iso(t):
    return t.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ') if t else None


def nk(x):
    return meta.norm_text(x).replace(' ', '')


def lignes(path):
    """Courbes live : fichier plat, sinon reconstruction depuis parts/ (oddspapi_v5.open_curves)."""
    try:
        import oddspapi_v5 as ov
        yield from ov.open_curves(path, verbose=False)
    except (ImportError, FileNotFoundError) as exc:
        print(f"  courbes indisponibles : {exc}")


def matchs(curves, now):
    out = {}
    for line in lignes(curves):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        start = _dt(r.get('commence_time'))
        if start is None or not r.get('book') or not r.get('uid'):
            continue
        if not (now - dt.timedelta(hours=AVANT_H) <= start <= now + dt.timedelta(hours=APRES_H)):
            continue
        tour = r.get('tournament') or ''
        if 'double' in tour.lower():
            continue
        # Cotes PRÉ-MATCH uniquement : un match en cours garde ses dernières cotes d'avant le début
        # (les cotes en jeu n'ont rien à voir avec un prix juste d'avant-match).
        limite = min(now, start)
        h = sorted((t, o) for t, o in ((_dt(p[0]), p[1]) for p in r.get('home_curve') or []) if t and o and t <= limite)
        a = sorted((t, o) for t, o in ((_dt(p[0]), p[1]) for p in r.get('away_curve') or []) if t and o and t <= limite)
        if not h or not a:
            continue
        m = out.setdefault(r['uid'], {'uid': r['uid'], 'home': r.get('home'), 'away': r.get('away'),
                                      'tournoi': tour, 'commence': _iso(start), 'cotes': {}})
        book = books.normalize(r['book'])
        if book == 'pinnacle':
            m['pin'] = {'ouverture': {'h': h[0][1], 'a': a[0][1], 't': _iso(max(h[0][0], a[0][0]))},
                        'courant': {'h': h[-1][1], 'a': a[-1][1], 't': _iso(max(h[-1][0], a[-1][0]))}}
        else:
            m['cotes'][book] = [h[-1][1], a[-1][1], _iso(max(h[-1][0], a[-1][0]))]
    return out


def alertes(root, by_uid, by_pair):
    root = pathlib.Path(root)
    for code in CODES:
        p = root / f'{code}_signal_log.jsonl'
        if not p.is_file():
            continue
        for line in p.read_text(encoding='utf-8').splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            m = by_uid.get(r.get('uid'))
            if m is None:
                continue
            m['alertes'].append({'type': code.upper(), 'joueur': r.get('joueur'), 't': r.get('signale_le'),
                                 'cote': r.get('cote'), 'book': r.get('book'),
                                 'envoye': bool(r.get('envoye')) and not r.get('doublon')})
    p = root / 'canal_public_log.jsonl'
    if p.is_file():
        for line in p.read_text(encoding='utf-8').splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            m = by_uid.get(r.get('uid'))
            if m is not None:
                m['alertes'].append({'type': 'PUBLIC', 'joueur': r.get('joueur'), 't': r.get('t'),
                                     'cote': r.get('cote_ref_apres'), 'book': None, 'envoye': True})
    mois = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m')
    for path in [root / 'odds_alerts_log.jsonl'] + sorted(glob.glob(str(root / f'odds_alerts_log/*{mois}*.jsonl'))):
        path = pathlib.Path(path)
        if not path.is_file():
            continue
        vus = set()
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            start = _dt(r.get('commence_time'))
            pair = frozenset((nk(r.get('home')), nk(r.get('away'))))
            for m in by_pair.get(pair, []):
                if start and abs((_dt(m['commence']) - start).total_seconds()) <= 6 * 3600:
                    mh, ma = r.get('mv_home_pct'), r.get('mv_away_pct')
                    if mh is None or ma is None:
                        continue
                    joueur = r.get('home') if mh < ma else r.get('away')
                    key = (m['uid'], nk(joueur))
                    if key in vus:
                        continue
                    vus.add(key)
                    m['alertes'].append({'type': 'MOUVEMENT', 'joueur': joueur, 't': r.get('logged_at'),
                                         'cote': r.get('o_home_last') if mh < ma else r.get('o_away_last'),
                                         'book': None, 'envoye': False})


def build(root=ROOT, curves='book_curves_live.jsonl', now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    root = pathlib.Path(root)
    cur = os.getcwd()
    os.chdir(root)
    try:
        ms = matchs(curves, now)
    finally:
        os.chdir(cur)
    surfaces = meta.SurfaceMap(root / 'historique/tennis_data.csv.gz')
    by_pair = collections.defaultdict(list)
    kept = []
    for m in ms.values():
        if 'pin' not in m:
            continue                      # sans Pinnacle : ni prix juste, ni profil
        m['circuit'] = meta.circuit_of(m['tournoi'])
        m['surface'] = surfaces.lookup(m['tournoi'])[0]
        m['alertes'] = []
        by_pair[frozenset((nk(m['home']), nk(m['away'])))].append(m)
        kept.append(m)
    alertes(root, {m['uid']: m for m in kept}, by_pair)
    for m in kept:
        m['alertes'].sort(key=lambda x: str(x['t']))
    kept.sort(key=lambda m: (m['commence'], m['uid']))
    tous = sorted({b for m in kept for b in m['cotes']} | {'pinnacle'})
    flags = {b: {'jouable': books.flags(b)['jouable'] and b != 'pinnacle', 'fr': books.flags(b)['jouable_fr'],
                 'commission': books.flags(b)['commission']} for b in tous}
    return {'schema_version': 1, 'genere_le': _iso(now), 'source': 'courbes live (book_curves_live.jsonl)',
            'fenetre': f'début entre −{AVANT_H} h et +{APRES_H} h', 'books': flags, 'matchs': kept}


def ecrire_si_change(path, doc):
    path = pathlib.Path(path)
    new = json.dumps(doc, ensure_ascii=False, separators=(',', ':'))
    if path.is_file():
        try:
            old = json.loads(path.read_text(encoding='utf-8'))
            if {k: v for k, v in old.items() if k != 'genere_le'} == {k: v for k, v in json.loads(new).items() if k != 'genere_le'}:
                return False
        except ValueError:
            pass
    path.write_text(new + '\n', encoding='utf-8')
    return True


def main():
    root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path.cwd()
    doc = build(root, os.environ.get('CURVES', 'book_curves_live.jsonl'))
    out = root / os.environ.get('OUT', 'direct_matchs.json')
    w = ecrire_si_change(out, doc)
    taille = out.stat().st_size if out.is_file() else 0
    print(f"direct_matchs : {len(doc['matchs'])} matchs, {taille // 1024} Ko, {'écrit' if w else 'inchangé'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
