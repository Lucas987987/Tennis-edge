#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_criteres_matchs.py — six nouveaux critères pour repérer nos matchs les moins (ou les plus) réussis
(05/11/2026, demande de Lucas). Descriptif ; aucune cote utilisée.

Pronostics REJOUÉS (pronostics_hors_echantillon.jsonl.gz) reliés aux fiches de match :
  1. tour du tableau (qualifications ; premiers tours ; huitièmes ; quarts et au-delà) ;
  2. niveau du tournoi (Grand Chelem, 1000, 500, 250 ; Challenger 125 / 100 / 75 / 50) ;
  3. salle ou plein air.
Pronostics EN DIRECT (pronostics_resultats.json) :
  4. pronostic qui a bougé de 5 points ou plus entre le premier et le dernier passage avant le match ;
  5. matchs similaires (150 voisins) qui disent autre chose que nous (réel − prévu des voisins hors ± 3 points) ;
  6. documentation des profils : NON TESTABLE, le nombre de balles connues n'est pas gardé dans nos fiches jugées.
Mesure d'un groupe : pente d'étalonnage (1 = nos % se réalisent), réussite du favori contre réussite annoncée.
RÈGLE FIXÉE AVANT DE REGARDER (même que la vérification hebdomadaire) : un groupe est FRAGILE si sa pente est
inférieure d'au moins 0,10 à celle du reste sur les DEUX périodes (rejoué : août–sept / oct–nov, au moins 100 matchs
par période ; direct : avant / après le 1er novembre, au moins 60 par période, verdict provisoire) ; FAVORI
SOUS-ESTIMÉ si le favori y gagne au moins 3 points de plus qu'annoncé sur les deux périodes (mêmes effectifs).
Usage : python simulateur/etude_criteres_matchs.py [racine_donnees] [racine_feuilles]
"""
import collections
import datetime as dt
import gzip
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
SORTIE = os.path.join(ICI, 'rapport_criteres_matchs.json')


def _c(p):
    return min(max(float(p), 1e-6), 1 - 1e-6)


def _lg(p):
    p = _c(p)
    return math.log(p / (1 - p))


def pente(G):
    a = 1.0
    for _ in range(60):
        g = h = 0.0
        for r in G:
            z = _lg(r['p']) if r['y'] else -_lg(r['p'])
            q = 1 / (1 + math.exp(-a * z))
            g += (q - 1) * z
            h += q * (1 - q) * z * z
        if h <= 0:
            break
        d = g / h
        a -= d
        if abs(d) < 1e-9:
            break
    return a


def mes(G):
    n = len(G)
    return {'matchs': n, 'pente': round(pente(G), 2) if n >= 30 else None,
            'reussite_pct': round(100 * sum((r['p'] >= .5) == (r['y'] == 1) for r in G) / n, 1) if n else None,
            'annoncee_pct': round(100 * sum(max(r['p'], 1 - r['p']) for r in G) / n, 1) if n else None}


def tour(t):
    t = str(t or '').lower()
    if 'qualif' in t:
        return 'qualifications'
    if 'quarter' in t or 'semi' in t or t == 'final':
        return 'quarts et au-delà'
    if 'round of 16' in t:
        return 'huitièmes'
    if 'round of' in t:
        return 'premiers tours'
    return None


def niveau(f):
    cat, pts = str(f.get('categorie') or ''), f.get('points_tournoi')
    if cat in ('ATP', 'WTA'):
        return {2000: 'Grand Chelem', 1000: '1000', 500: '500', 250: '250'}.get(pts)
    if cat == 'Challenger':
        return f'Challenger {pts}' if pts else 'Challenger ?'
    return None


def juger(R, cle, periodes, min_per):
    out = {}
    vals = sorted({r[cle] for r in R if r[cle] is not None})
    for v in vals:
        res = {}
        for nom, f in periodes:
            A = [r for r in R if f(r) and r[cle] == v]
            B = [r for r in R if f(r) and r[cle] is not None and r[cle] != v]
            res[nom] = {'groupe': mes(A), 'reste': mes(B)}
        assez = all(x['groupe']['matchs'] >= min_per for x in res.values())
        fragile = assez and all(x['groupe']['pente'] is not None and x['reste']['pente'] is not None
                                and x['groupe']['pente'] <= x['reste']['pente'] - 0.10 for x in res.values())
        sous = assez and all(x['groupe']['reussite_pct'] - x['groupe']['annoncee_pct'] >= 3 for x in res.values())
        out[str(v)] = {'periodes': res, 'assez': assez, 'fragile': bool(fragile), 'favori_sous_estime': bool(sous)}
    return out


def main(argv):
    donnees = argv[1] if len(argv) > 1 else os.path.join(ICI, '..')
    feuilles_racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    import feuilles as FE
    fiches = {r.get('id'): r for r in FE.lire(feuilles_racine)}
    R1 = []
    for l in gzip.open(os.path.join(donnees, 'simulateur', 'pronostics_hors_echantillon.jsonl.gz'), 'rt'):
        x = json.loads(l)
        f = fiches.get(x.get('id'))
        if not f or x.get('gagnant') not in ('home', 'away') or x.get('p_algo') is None:
            continue
        surf = str(f.get('surface') or '').lower()
        R1.append({'jour': x['jour'], 'p': x['p_algo'], 'y': int(x['gagnant'] == 'home'), 'c': x.get('circuit'),
                   'tour': tour(f.get('tour')), 'niveau': niveau(f),
                   'salle': ('salle' if 'indoor' in surf else 'plein air') if surf and surf != 'none' else None})
    with open(os.path.join(donnees, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as fh:
        doc = json.load(fh)
    R2 = []
    for m in doc.get('matchs') or []:
        reel = m.get('reel') or {}
        p = m.get('p_affiche')
        if p is None or reel.get('gagnant') not in ('home', 'away') or reel.get('interrompu'):
            continue
        pr = ((m.get('premier') or {}).get('combinaison') or {}).get('p_home')
        de = ((m.get('dernier') or {}).get('combinaison') or {}).get('p_home')
        vo = ((m.get('fiabilite') or {}).get('matchs_similaires') or {}).get('ecart_reel_moins_prevu')
        fav_home = p >= .5
        R2.append({'jour': str(m.get('debut'))[:10], 'p': p, 'y': int(reel['gagnant'] == 'home'),
                   'bouge': (None if pr is None or de is None else ('a bougé de 5 pts ou plus' if abs(de - pr) >= .05 else 'stable')),
                   'voisins': (None if vo is None else ('voisins contre notre favori' if (vo < -0.03) == fav_home and abs(vo) > 0.03
                                                        else 'voisins pour notre favori' if abs(vo) > 0.03 else 'voisins neutres'))})
    P1 = (('août–sept', lambda r: r['jour'] < '2026-09-29'), ('oct–nov', lambda r: r['jour'] >= '2026-09-29'))
    P2 = (('avant le 01/11', lambda r: r['jour'] < '2026-11-01'), ('depuis le 01/11', lambda r: r['jour'] >= '2026-11-01'))
    out = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("fragile : pente ≤ reste − 0,10 sur les deux périodes ; favori sous-estimé : réel ≥ annoncé + 3 points "
                     "sur les deux ; rejoué ≥ 100 matchs par période, direct ≥ 60 (provisoire)"),
           'rejoue': {'matchs': len(R1), 'tour du tableau': juger(R1, 'tour', P1, 100),
                      'niveau du tournoi': juger(R1, 'niveau', P1, 100), 'salle ou plein air': juger(R1, 'salle', P1, 100)},
           'direct': {'matchs': len(R2), 'pronostic qui bouge': juger(R2, 'bouge', P2, 60),
                      'matchs similaires': juger(R2, 'voisins', P2, 60)},
           'documentation des profils': 'non testable : le nombre de balles connues n’est pas gardé dans les fiches jugées'}
    with open(SORTIE, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    for pop in ('rejoue', 'direct'):
        print(f"\n### {pop} ({out[pop]['matchs']} matchs)")
        for crit, V in out[pop].items():
            if crit == 'matchs':
                continue
            print(' ', crit)
            for v, x in V.items():
                per = ' | '.join(f"{k}: n{y['groupe']['matchs']} pente {y['groupe']['pente']} (reste {y['reste']['pente']}) "
                                 f"{y['groupe']['reussite_pct']} % / {y['groupe']['annoncee_pct']} %" for k, y in x['periodes'].items())
                tag = '🔴 FRAGILE' if x['fragile'] else '🟢 SOUS-ESTIMÉ' if x['favori_sous_estime'] else ('' if x['assez'] else '(trop peu)')
                print(f"    {v:28} {tag:14} {per}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
