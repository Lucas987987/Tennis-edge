#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_meilleurs_matchs.py — dans quels matchs nos pronostics sont-ils les plus justes ? (05/11/2026, demande de Lucas)

Population : nos pronostics hors échantillon FIGÉS (pronostics_hors_echantillon.jsonl.gz), reliés aux fiches de match
pour connaître surface, expérience, âge, absence, changement de surface. Mesure d'un segment :
  maîtrise = 1 − log loss / ln 2   (0 = pile ou face ; plus c'est haut, mieux nos % prévoient le vainqueur)
  + réussite (favori annoncé gagnant), réussite annoncée, pente d'étalonnage (1 = nos % sont la réalité).
RÈGLE FIXÉE AVANT DE REGARDER : un segment est « parmi nos meilleurs » si, avec au moins 150 matchs au total et 60 sur
CHAQUE période (août–septembre, octobre–novembre), sa maîtrise dépasse celle de l'ensemble sur les DEUX périodes et
que sa pente reste entre 0,8 et 1,25 sur les deux (des % justes, pas seulement des gagnants faciles).
Descriptif : aucun conseil de pari ; la CLV reste la seule mesure d'un avantage.
Usage : python simulateur/etude_meilleurs_matchs.py /tmp/sackmann .
"""
import collections
import datetime as dt
import gzip
import itertools
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
COUPURE = '2026-09-29'
MIN_N, MIN_PER = 150, 60
SORTIE = os.path.join(ICI, 'rapport_meilleurs_matchs.json')


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


def mesures(G):
    n = len(G)
    ll = sum(-math.log(_c(r['p']) if r['y'] else 1 - _c(r['p'])) for r in G) / n
    return {'matchs': n, 'maitrise': round(1 - ll / math.log(2), 3), 'log_loss': round(ll, 4),
            'reussite_pct': round(100 * sum((r['p'] >= .5) == (r['y'] == 1) for r in G) / n, 1),
            'annoncee_pct': round(100 * sum(max(r['p'], 1 - r['p']) for r in G) / n, 1), 'pente': round(pente(G), 2)}


def lignes(archive, racine):
    import donnees as DN
    import elo as E
    import etude_age as EA
    import etude_retour_absence as ERA
    import feuilles as FE
    L = [json.loads(l) for l in gzip.open(os.path.join(racine, 'simulateur', 'pronostics_hors_echantillon.jsonl.gz'), 'rt')]
    al = dict(E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json')))).get('alias') or {})
    k = lambda n: al.get(E.cle(n), E.cle(n)) if n else None
    fiches = {r.get('id'): r for r in FE.lire(racine)}
    D = ERA.dates_matchs(archive, racine)
    naiss = EA.naissances(archive, k)
    surf = collections.defaultdict(list)
    for m in DN.charger(archive, 2024):
        for n in (m['nom_g'], m['nom_p']):
            surf[k(n)].append((m['date'], m['surface']))
    for r in fiches.values():
        if r.get('jour'):
            for c_ in ('home', 'away'):
                surf[k((r.get(c_) or {}).get('nom'))].append((dt.date.fromisoformat(r['jour']), FE.surface_de(r.get('surface'))))
    for v in surf.values():
        v.sort()
    rows = []
    for x in L:
        f = fiches.get(x['id'])
        if not f or x['gagnant'] not in ('home', 'away') or None in (x.get('p_elo'), x.get('p_sim'), x.get('p_algo')):
            continue
        j = dt.date.fromisoformat(x['jour'])
        h, a = k(f['home'].get('nom')), k(f['away'].get('nom'))
        s = FE.surface_de(f.get('surface'))
        p, pe, ps = x['p_algo'], x['p_elo'], x['p_sim']
        fav, out_ = (h, a) if p >= .5 else (a, h)
        n = {q: sum(1 for d in (D.get(q) or []) if d < j and (j - d).days < 730) for q in (h, a)}
        age = {q: EA.age_au(naiss, q, j) for q in (h, a)}
        ret = max(ERA.etat_au(D.get(q), j)[0] for q in (h, a))

        def nouv(q):
            prev = [t for t in surf.get(q, []) if t[0] < j]
            return bool(prev) and prev[-1][1] != s and (j - prev[-1][0]).days <= 45
        pf = max(p, 1 - p)
        accord = 'favoris opposés' if (pe >= .5) != (ps >= .5) else ('écart ≥ 10 pts' if abs(pe - ps) >= .10 else 'accord')
        ag = age[fav]
        rows.append({'jour': x['jour'], 'p': p, 'y': int(x['gagnant'] == 'home'), 'seg': {
            'circuit': x['circuit'], 'surface': s or '?',
            'confiance': '50–60 %' if pf < .6 else '60–70 %' if pf < .7 else '70–80 %' if pf < .8 else '80 % et plus',
            'modèles': accord,
            'expérience du favori': '< 60 matchs' if n[fav] < 60 else '60–150' if n[fav] < 150 else '150 et plus',
            "expérience de l'outsider": '< 60 matchs' if n[out_] < 60 else '60–150' if n[out_] < 150 else '150 et plus',
            'âge du favori': '?' if ag is None else '< 23 ans' if ag < 23 else '23–29 ans' if ag < 30 else '30 ans et plus',
            "retour d'absence": 'oui' if ret > 0 else 'non',
            'changement de surface': 'oui' if (nouv(h) or nouv(a)) else 'non'}})
    return rows


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    R = lignes(archive, racine)
    per = {'août–sept': [r for r in R if r['jour'] < COUPURE], 'oct–nov': [r for r in R if r['jour'] >= COUPURE]}
    ref = {k: mesures(v) for k, v in per.items()}
    ref['tous'] = mesures(R)
    cles = list(R[0]['seg'])
    segs = []
    for nb in (1, 2):
        for combo in itertools.combinations(cles, nb):
            groupes = collections.defaultdict(list)
            for r in R:
                groupes[tuple(r['seg'][c] for c in combo)].append(r)
            for val, G in groupes.items():
                if len(G) < MIN_N:
                    continue
                P = {k: [r for r in G if (r['jour'] < COUPURE) == (k == 'août–sept')] for k in per}
                if min(len(v) for v in P.values()) < MIN_PER:
                    continue
                m = {k: mesures(v) for k, v in P.items()}
                ok = all(m[k]['maitrise'] > ref[k]['maitrise'] and 0.8 <= m[k]['pente'] <= 1.25 for k in per)
                segs.append({'segment': ' · '.join(f'{c} : {v}' for c, v in zip(combo, val)), 'tous': mesures(G),
                             'periodes': m, 'parmi_les_meilleurs': ok})
    segs.sort(key=lambda s: -s['tous']['maitrise'])
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'reference': ref,
           'regle': ("parmi les meilleurs : ≥ 150 matchs (≥ 60 par période), maîtrise au-dessus de l'ensemble sur les deux "
                     "périodes, pente entre 0,8 et 1,25 sur les deux"),
           'meilleurs': [s for s in segs if s['parmi_les_meilleurs']], 'tous_les_segments': segs}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print('référence', ref)
    for s in doc['meilleurs']:
        t = s['tous']
        print(f"★ {s['segment']:80} n{t['matchs']:5} maîtrise {t['maitrise']:.3f} réussite {t['reussite_pct']} (annoncée {t['annoncee_pct']}) pente {t['pente']} | "
              + ' / '.join(f"{k} {v['maitrise']:.3f}" for k, v in s['periodes'].items()))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
