#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scenarios_match.py — les SCÉNARIOS du match et leur CONTRÔLE sur nos matchs réels (11/11/2026, paquets 221–222).

1. scenarios(distribution) : les 6 issues regroupées (chaque joueur gagne en 2 sets « sans trembler » = chaque set à
   6-2 ou mieux, en 2 sets « accrochés » = au moins un set à 6-3, 6-4, 7-5 ou 7-6, ou en 3 sets — dont « remontée » après
   avoir perdu le 1er set), tie-break, set à 6-0 / 6-1, jeux (médiane, 10e et 90e centiles), et pour chaque joueur
   la chance de gagner s'il gagne / perd le 1er set. Calculé sur la distribution COMPLÈTE des scores exacts.

2. controle(racine) : le dernier pronostic affiché avant chaque match (fiches figées d'apres_match.py) contre le
   score réel (Tennis_Edge_Lab/live/pronostics_resultats.json). Matchs en 2 sets gagnants, terminés.
   — Prévu : les scénarios figés quand la fiche les a (depuis le paquet 222) ; sinon RECONSTITUÉS depuis la fiche :
     le score en sets figé (exact) donne le poids de chaque issue en sets, et les scores exacts gardés (≥ 0,1 %) donnent
     le partage à l'intérieur (« sans trembler » / « accrochés » ; « remontée » parmi les 3 sets).
   — RÈGLE (fixée avant de regarder les résultats) : pour chaque scénario, par circuit et en tout, à partir de 30
     matchs : « juste » si l'écart réel − prévu reste dans ± 1,96 erreur type (√Σp(1−p) / n), sinon « trop haut » ou
     « trop bas ». Même règle pour « gagne après avoir gagné le 1er set » (matchs où ce joueur a gagné le 1er set).
   Descriptif : rien n'entre dans le %. Aucune cote.
"""
import datetime as dt
import json
import math
import os

GROUPES = ('net', 'accroche', 'long')
# 13/11/2026 (paquet 267, remarque d'un abonné relevée par Lucas) : un 6-3 peut ne compter qu'UN break, comme un 6-4
# (6-3 quand le vainqueur sert en premier : il garde ses 5 services, l'autre perd 1 de ses 4). Le score seul ne dit pas
# qui servait en premier ; seul un 6-2 ou mieux garantit au moins deux breaks d'avance. Donc « sans trembler » = chaque
# set à 6-2 ou mieux (au moins 2 breaks d'avance à coup sûr), « accrochés » = au moins un set à 6-3, 6-4, 7-5 ou 7-6
# (un seul break a pu suffire). DEFINITION = 2 ; les scénarios figés avant (sans ce numéro) sont reconstitués depuis
# les scores exacts de la fiche, pour que prévu et réel suivent la même définition.
DEFINITION = 2
ECART_NET = 4                                                       # 6-2 : écart de 4 jeux
CIRCUITS = ('ATP', 'WTA', 'CH')
N_MIN, Z = 30, 1.96


def scenarios(D_):
    tot = sum(float(r['probabilite']) for r in D_ or [])
    if not tot:
        return None
    J = [{'net': 0.0, 'accroche': 0.0, 'long': 0.0, 'remontee': 0.0} for _ in (0, 1)]
    tb = sec = 0.0
    jeux = {}
    s1 = [[0.0, 0.0], [0.0, 0.0]]
    for r in D_:
        q, sc, v = float(r['probabilite']) / tot, [tuple(x) for x in r['score']], r.get('vainqueur')
        if v not in (0, 1) or not sc:
            continue
        if any(max(h) == 7 and min(h) == 6 for h in sc):
            tb += q
        if any(max(h) == 6 and min(h) <= 1 for h in sc):
            sec += q
        n = sum(a + b for a, b in sc)
        jeux[n] = jeux.get(n, 0.0) + q
        w1 = 0 if sc[0][0] > sc[0][1] else 1
        s1[w1][0] += q
        s1[w1][1] += q if v == w1 else 0.0
        g, rem = issue(sc, v)
        J[v][g] += q
        if rem:
            J[v]['remontee'] += q

    def centile(c):
        acc = 0.0
        for k in sorted(jeux):
            acc += jeux[k]
            if acc >= c - 1e-9:
                return k
        return max(jeux) if jeux else None
    for j in (0, 1):
        o = 1 - j
        J[j]['si_set1_gagne'] = s1[j][1] / s1[j][0] if s1[j][0] > 0 else None
        J[j]['si_set1_perdu'] = (s1[o][0] - s1[o][1]) / s1[o][0] if s1[o][0] > 0 else None
    r4 = lambda x: round(x, 4) if x is not None else None  # noqa: E731
    return {'definition': DEFINITION, 'j': [{k: r4(v) for k, v in o.items()} for o in J], 'tiebreak': r4(tb), 'set_sec': r4(sec),
            'jeux': {'p10': centile(0.10), 'mediane': centile(0.50), 'p90': centile(0.90)}}


def issue(sc, v):
    """(groupe, remontée) du vainqueur v (0 = home) pour un score [(jeux home, jeux away), ...]."""
    perdus = sum(h[v] < h[1 - v] for h in sc)
    if perdus == 0:
        return ('net' if all(h[v] - h[1 - v] >= ECART_NET for h in sc) else 'accroche'), False
    return 'long', sc[0][v] < sc[0][1 - v]


def _sets_txt(t):
    try:
        out = [tuple(int(x) for x in s.split('-')[:2]) for s in str(t).split()]
        return out if out and all(len(s) == 2 for s in out) else None
    except ValueError:
        return None


def reconstituer(d):
    """Scénarios (6 issues + remontée + 1er set) depuis une fiche figée : sets exacts × partage des scores gardés."""
    sets, scores = d.get('sets') or {}, d.get('scores') or []
    if set(sets) != {'2-0', '2-1', '1-2', '0-2'} or not scores:
        return None
    part = {k: {'net': 0.0, 'accroche': 0.0, 'long': 0.0, 'remontee': 0.0, 's1': 0.0} for k in sets}
    for t, p in scores:
        sc = _sets_txt(t)
        if not sc or len(sc) not in (2, 3):
            continue
        v = 0 if sum(a > b for a, b in sc) > len(sc) / 2 else 1
        cle = f"{sum(a > b for a, b in sc)}-{sum(a < b for a, b in sc)}"
        if cle not in part:
            continue
        g, rem = issue(sc, v)
        part[cle][g] += p
        part[cle]['remontee'] += p if rem else 0.0
        part[cle]['s1'] += p if sc[0][0] > sc[0][1] else 0.0      # masse où home gagne le 1er set
    J = [{'net': 0.0, 'accroche': 0.0, 'long': 0.0, 'remontee': 0.0} for _ in (0, 1)]
    s1h = 0.0
    s1h_gagne = 0.0
    for cle, v in (('2-0', 0), ('2-1', 0), ('1-2', 1), ('0-2', 1)):
        P, m = float(sets[cle]), part[cle]
        tot = m['net'] + m['accroche'] + m['long']
        if tot <= 0:
            if P > 0.02:
                return None
            continue
        for g in GROUPES:
            J[v][g] += P * m[g] / tot
        J[v]['remontee'] += P * m['remontee'] / tot
        s1h += P * m['s1'] / tot
        if v == 0:
            s1h_gagne += P * m['s1'] / tot
    ph = J[0]['net'] + J[0]['accroche'] + J[0]['long']
    J[0]['si_set1_gagne'] = s1h_gagne / s1h if s1h > 0 else None
    J[1]['si_set1_gagne'] = ((1 - ph) - (s1h - s1h_gagne)) / (1 - s1h) if s1h < 1 else None
    return {'j': J}


def _score_reel(m):
    r = m.get('reel') or {}
    if r.get('interrompu') or r.get('score_invalide') or r.get('gagnant') not in ('home', 'away'):
        return None
    sc = _sets_txt(r.get('score'))
    if not sc or len(sc) not in (2, 3):
        return None
    return sc, 0 if r['gagnant'] == 'home' else 1


def cas(racine):
    """[{circuit, prevu (6 issues …), reel (j, groupe, remontée, set1)}] — matchs en 2 sets gagnants."""
    import apres_match as AM
    F = AM.toutes_les_fiches(racine)
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            R = {m['uid']: m for m in json.load(f).get('matchs') or []}
    except (OSError, ValueError):
        R = {}
    out = []
    for uid, e in F.items():
        d = e.get('dernier') or {}
        if e.get('meilleur_des') != 3 or uid not in R:
            continue
        sr = _score_reel(R[uid])
        if not sr:
            continue
        sc, v = sr
        prev = d.get('scenarios')
        if prev and prev.get('definition') != DEFINITION:      # figé avec l'ancienne définition (6-3 « net »)
            prev = None
        source = 'fige' if prev else 'reconstitue'
        prev = prev or reconstituer(d)
        if not prev:
            continue
        g, rem = issue(sc, v)
        out.append({'uid': uid, 'circuit': e.get('circuit'), 'source': source, 'prevu': prev,
                    'reel': {'j': v, 'groupe': g, 'remontee': rem, 'set1': 0 if sc[0][0] > sc[0][1] else 1}})
    return out


def _verdict(ps, ys):
    n = len(ps)
    if n < N_MIN:
        return {'n': n, 'prevu_pct': round(100 * sum(ps) / n, 1) if n else None,
                'reel_pct': round(100 * sum(ys) / n, 1) if n else None, 'verdict': 'trop tot'}
    pm, ym = sum(ps) / n, sum(ys) / n
    et = math.sqrt(sum(p * (1 - p) for p in ps)) / n
    ecart = ym - pm
    v = 'juste' if abs(ecart) <= Z * et else ('trop bas' if ecart > 0 else 'trop haut')   # le prévu est trop bas/haut
    return {'n': n, 'prevu_pct': round(100 * pm, 1), 'reel_pct': round(100 * ym, 1),
            'marge_pts': round(100 * Z * et, 1), 'verdict': v}


def controle(racine):
    C = cas(racine)
    out = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'matchs': len(C),
           'figes': sum(x['source'] == 'fige' for x in C), 'regle': __doc__.split('— RÈGLE')[1].split('Descriptif')[0]
           .replace('\n', ' ').strip(' :'), 'groupes': {}}
    for c in CIRCUITS + ('tous',):
        X = [x for x in C if c == 'tous' or x['circuit'] == c]
        if not X:
            continue
        r = {}
        for g in GROUPES:
            ps, ys = [], []
            for x in X:          # les deux joueurs : « le favori de l'algo » n'est pas imposé, chaque camp compte
                for j in (0, 1):
                    ps.append(float(x['prevu']['j'][j][g]))
                    ys.append(1.0 if (x['reel']['j'] == j and x['reel']['groupe'] == g) else 0.0)
            r[g] = _verdict(ps, ys)
        ps, ys = [], []
        for x in X:
            for j in (0, 1):
                ps.append(float(x['prevu']['j'][j]['remontee']))
                ys.append(1.0 if (x['reel']['j'] == j and x['reel']['remontee']) else 0.0)
        r['remontee'] = _verdict(ps, ys)
        ps, ys = [], []
        for x in X:
            j = x['reel']['set1']
            p = x['prevu']['j'][j].get('si_set1_gagne')
            if p is not None:
                ps.append(float(p))
                ys.append(1.0 if x['reel']['j'] == j else 0.0)
        r['gagne_apres_set1'] = _verdict(ps, ys)
        out['groupes'][c] = r
    return out


if __name__ == '__main__':
    import sys
    racine = sys.argv[1] if len(sys.argv) > 1 else '.'
    print(json.dumps(controle(racine), ensure_ascii=False, indent=1))
