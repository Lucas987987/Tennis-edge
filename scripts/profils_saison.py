#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
profils_saison.py — PROFIL DE LA SAISON DES JOUEURS (26/11/2026, paquet 487, Lucas : « lance » le profil de la saison).

INFORMATION DESCRIPTIVE : elle ne change pas le % de l'algo (aucun script de l'algo ne lit ce fichier ni sa source).
Source : historique/stats_annee/ (collecte_stats_annee.py, fournisseur de TennisApi via AllSportsApi) — statistiques
de l'année de chaque joueur par surface, et ses classements.

Pour chaque joueur : l'année en cours, ou la précédente si l'année en cours a moins de 5 matchs (début de saison) ;
un bloc « toutes surfaces » et un bloc par surface du site (Clay, Hard, Grass, Carpet) :
  m  matchs, v victoires,
  p1 % de points gagnés derrière la 1re balle, p2 derrière la 2e, ps % de points gagnés au service,
  pr % de 1res balles (points joués derrière la 1re / points de service),
  ac aces par match, df doubles fautes par match,
  bs % de balles de break sauvées, bc % de balles de break converties,
  tb jeux décisifs [gagnés, perdus].
Classements (si connus) : rang et meilleur rang ATP/WTA, rang UTR.
Les coups gagnants et fautes directes ne sont pas montrés : présents pour trop peu de matchs (vérifié le 26/11).

Sorties :
  python scripts/profils_saison.py donnees.json sortie.json   → les joueurs des matchs du site, par nom du site
  profils(racine) / profil_de(nom) sont aussi utilisés par scripts/pages_seo.py (pages joueur).
"""
import gzip
import json
import os
import re
import sys
import unicodedata

DOSSIER = os.path.join('historique', 'stats_annee')
MIN_MATCHS_ANNEE = 5


def cle(nom):
    n = unicodedata.normalize('NFD', str(nom or '')).encode('ascii', 'ignore').decode().lower()
    return ' '.join(re.findall(r'[a-z]+', n))


def surface_site(g):
    g = str(g or '').lower()
    return 'Clay' if 'clay' in g else 'Hard' if 'hard' in g else 'Grass' if 'grass' in g else 'Carpet' if 'carpet' in g else None


def _lire(p):
    try:
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            return [json.loads(l) for l in f if l.strip()]
    except (OSError, ValueError):
        return []


def _pct(a, b):
    return round(100 * a / b, 1) if b else None


def bloc(L):
    """Somme de blocs de statistiques (une surface ou toutes) → indicateurs arrondis."""
    s = {}
    for x in L:
        for k, v in x.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                s[k] = s.get(k, 0) + v
    m = s.get('matches', 0)
    if not m:
        return None
    f1, f2 = s.get('firstServePointsTotal', 0), s.get('secondServePointsTotal', 0)
    out = {'m': m, 'v': s.get('wins', 0),
           'p1': _pct(s.get('firstServePointsScored', 0), f1), 'p2': _pct(s.get('secondServePointsScored', 0), f2),
           'ps': _pct(s.get('firstServePointsScored', 0) + s.get('secondServePointsScored', 0), f1 + f2),
           'pr': _pct(f1, f1 + f2),
           'ac': round(s.get('aces', 0) / m, 1), 'df': round(s.get('doubleFaults', 0) / m, 1),
           'bs': _pct(s.get('opponentBreakPointsTotal', 0) - s.get('opponentBreakPointsScored', 0), s.get('opponentBreakPointsTotal', 0)),
           'bc': _pct(s.get('breakPointsScored', 0), s.get('breakPointsTotal', 0)),
           'tb': [s.get('tiebreaksWon', 0), s.get('tiebreakLosses', 0)]}
    return {k: v for k, v in out.items() if v is not None}


def classements(L):
    out = {}
    for c in L or []:
        k = c.get('rankingClass')
        if k == 'team' and c.get('ranking'):
            out['rang'], out['meilleur'] = c.get('ranking'), c.get('bestRanking')
        elif k == 'utr' and c.get('ranking'):
            out['utr'] = c.get('ranking')
    return out


def profil(recs_annee, cls):
    """recs_annee : [(an, enregistrement)] du plus récent au plus ancien."""
    for an, r in recs_annee:
        S = r.get('stats') or []
        if sum(x.get('matches', 0) for x in S) < MIN_MATCHS_ANNEE:
            continue
        p = {'an': an, 'tout': bloc(S)}
        par = {}
        for x in S:
            k = surface_site(x.get('groundType'))
            if k:
                par.setdefault(k, []).append(x)
        for k, L in par.items():
            b = bloc(L)
            if b:
                p[k] = b
        c = classements(cls)
        if c:
            p['cl'] = c
        return p
    return None


def profils(racine='.', annees=None):
    """{clé du nom: profil} pour tous les joueurs collectés (un nom porté par deux joueurs : écarté)."""
    d = os.path.join(racine, DOSSIER)
    fichiers = sorted((int(f[:4]) for f in os.listdir(d) if re.fullmatch(r'\d{4}\.jsonl\.gz', f)), reverse=True) if os.path.isdir(d) else []
    annees = annees or fichiers[:2]
    par_id = {}
    for an in annees:
        for r in _lire(os.path.join(d, f'{an}.jsonl.gz')):
            par_id.setdefault(r['id'], {'nom': r.get('nom'), 'ans': []})['ans'].append((an, r))
    cls = {r['id']: r.get('classements') for r in _lire(os.path.join(d, 'classements.jsonl.gz'))}
    out, vus = {}, {}
    for i, x in par_id.items():
        k = cle(x['nom'])
        if not k:
            continue
        vus[k] = vus.get(k, 0) + 1
        p = profil(sorted(x['ans'], key=lambda y: -y[0]), cls.get(i))
        if p:
            out[k] = p
    return {k: v for k, v in out.items() if vus.get(k) == 1}


def pour_le_site(donnees, P):
    """{nom du site: profil} pour les joueurs des matchs du site."""
    out = {}
    for m in (donnees or {}).get('matchs') or []:
        for n in (m.get('home'), m.get('away')):
            p = P.get(cle(n))
            if n and p:
                out[n] = p
    return out


def main(argv):
    if len(argv) < 3:
        print('usage : profils_saison.py donnees.json sortie.json [racine]')
        return 1
    racine = argv[3] if len(argv) > 3 else '.'
    try:
        with open(argv[1], encoding='utf-8') as f:
            D = json.load(f)
    except (OSError, ValueError):
        D = {}
    P = profils(racine)
    S = pour_le_site(D, P)
    with open(argv[2], 'w', encoding='utf-8') as f:
        json.dump({'descriptif_seulement': True, 'joueurs': S}, f, ensure_ascii=False, separators=(',', ':'))
    print(f'profils de la saison : {len(S)} joueurs du site sur {len(P)} profils')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
