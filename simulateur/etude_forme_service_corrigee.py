#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_forme_service_corrigee.py — la forme du service / retour CORRIGÉE DU NIVEAU DES ADVERSAIRES (04/11/2026).

Différence avec forme_service.py (taux bruts) : pour chaque match des 30 derniers jours, on mesure ce que le joueur a
gagné au service (et au retour) PAR RAPPORT À CE QU'ATTENDAIT l'Elo service / retour face à CET adversaire
(elo_service_retour.py, η = 0,0015 fixé sur 2023–2024) : écart = logit(gagnés / joués) − logit(attendu).
Forme = moyenne de ces écarts pondérée par les points, × n / (n + 300), bornée à ±0,4 — mêmes constantes que
forme_service.py (fixées le 29/10), aucune nouvelle constante réglée sur les matchs jugés.

Mêmes deux lectures que etude_forme_service.py, sur les mêmes pronostics hors échantillon :
  A. mécanique : la simulation rejouée avec les écarts (service du joueur − retour adverse), ancrée sur p_sim, puis
     p_algo décalé de poids_simulation × Δlogit(p_sim) ;
  B. appris : z = logit p_algo + β·(décalage home − décalage away), β appris sur les semaines précédentes.
RÈGLE FIXÉE AVANT DE REGARDER (04/11/2026) : positif si −0,001 de log loss au total ET aucun circuit (ATP, WTA, CH)
dégradé de plus de 0,001. Positif → modèle fantôme sur les nouveaux matchs. Sinon : rien ne change.
"""
import bisect
import datetime as dt
import gzip
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo_service_retour as SR  # noqa: E402
import etude_forme_service as EF  # noqa: E402

ETA, RECENT_J, K, BORNE = 0.0015, 30, 300.0, 0.4


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


class FormeCorrigee:
    """Écarts au service et au retour, match par match, contre l'attendu de l'Elo service / retour d'avant-match."""
    def __init__(self, M):
        el, jour, attente = SR.EloSR(ETA), None, []
        self.h = {}                                      # clé → [(jour, 'S'|'R', points, écart)]
        for d, _, _, g, p, c, s, st in M:
            if d != jour:
                for y in attente:
                    el.maj(*y)
                attente, jour = [], d
            for srv, rel, cle in ((g, p, 'w'), (p, g, 'l')):
                n, w = st[cle]
                if n < 20 or not 0 < w < n:
                    continue
                e = _lg(w / n) - _lg(el.p_service(srv, rel, c, s))
                self.h.setdefault(srv, []).append((d, 'S', n, e))
                self.h.setdefault(rel, []).append((d, 'R', n, -e))
            attente.append((g, p, c, s, st))
        self.j = {k: [x[0] for x in v] for k, v in self.h.items()}

    def forme(self, k, jour):
        """(forme au service, forme au retour) en logit, sur [jour − 30 ; jour[."""
        L = self.j.get(k) or []
        i, f = bisect.bisect_left(L, jour - dt.timedelta(days=RECENT_J)), bisect.bisect_left(L, jour)
        out = []
        for q in ('S', 'R'):
            X = [(n, e) for (_, t, n, e) in self.h.get(k, [])[i:f] if t == q]
            n = sum(x[0] for x in X)
            if not n:
                out.append(0.0)
                continue
            m = sum(a * e for a, e in X) / n * n / (n + K)
            out.append(max(-BORNE, min(BORNE, m)))
        return tuple(out)


def main(archive, racine):
    import elo as E
    import feuilles as FE
    with gzip.open(os.path.join(racine, 'simulateur', 'pronostics_hors_echantillon.jsonl.gz'), 'rt', encoding='utf-8') as f:
        L = [json.loads(l) for l in f if l.strip()]
    fiches = {r.get('id'): r for r in FE.lire(racine)}
    try:
        alias = dict(E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'),
                                                  encoding='utf-8'))).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    kc = lambda n: alias.get(E.cle(n), E.cle(n))
    try:
        w_sim = json.load(open(os.path.join(ICI, 'choix_simulation.json'), encoding='utf-8'))['combinaison']['poids']['simulation']
    except (OSError, ValueError, KeyError):
        w_sim = 0.2377
    FC = FormeCorrigee(SR.matchs(archive, racine))
    rows = []
    for x in L:
        r = fiches.get(x.get('id'))
        if not r or x.get('gagnant') not in ('home', 'away') or x.get('p_sim') is None or x.get('p_algo') is None:
            continue
        j = dt.date.fromisoformat(x['jour'])
        sh, rh = FC.forme(kc((r.get('home') or {}).get('nom') or ''), j)
        sa, ra = FC.forme(kc((r.get('away') or {}).get('nom') or ''), j)
        dh, da = sh - ra, sa - rh
        if not (dh or da):
            continue
        ps2 = EF.p_sim_decale(x['p_sim'], x['circuit'], dh, da)
        pa2 = EF._sg(EF._lg(x['p_algo']) + w_sim * (EF._lg(ps2) - EF._lg(x['p_sim'])))
        rows.append({'jour': x['jour'], 'c': x['circuit'], 'y': int(x['gagnant'] == 'home'), 'p': x['p_algo'],
                     'pm': pa2, 'x': dh - da})
    rows.sort(key=lambda r: r['jour'])
    sem = lambda d: dt.date.fromisoformat(d).isocalendar()[:2]
    semaines = sorted({sem(r['jour']) for r in rows})
    for i, w in enumerate(semaines):
        avant = [r for r in rows if sem(r['jour']) < w]
        b = 0.0
        for _ in range(25):
            g = h = 0.0
            for r in avant:
                q = EF._sg(EF._lg(r['p']) + b * r['x'])
                g += (q - r['y']) * r['x']
                h += q * (1 - q) * r['x'] ** 2
            if h <= 0:
                break
            b -= g / (h + 1.0)
        for r in rows:
            if sem(r['jour']) == w:
                r['pb'] = EF._sg(EF._lg(r['p']) + b * r['x']) if i >= 3 else None
                r['b'] = b if i >= 3 else None
    out = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'poids_simulation': w_sim,
           'regle': "positif si −0,001 de log loss au total et aucun circuit dégradé de plus de 0,001 (fixée avant)",
           'mecanique': {}, 'appris': {}}
    for nom, cle, filtre in (('mecanique', 'pm', lambda r: True), ('appris', 'pb', lambda r: r.get('pb') is not None)):
        for c in ('TOUS', 'ATP', 'WTA', 'CH'):
            R = [r for r in rows if filtre(r) and (c == 'TOUS' or r['c'] == c)]
            if not R:
                continue
            a = sum(EF.ll(r['p'], r['y']) for r in R) / len(R)
            b_ = sum(EF.ll(r[cle], r['y']) for r in R) / len(R)
            out[nom][c] = {'matchs': len(R), 'log_loss_algo': round(a, 5), 'log_loss_avec_forme': round(b_, 5),
                           'gain': round(a - b_, 5)}
        T = out[nom]
        if 'TOUS' in T:
            T['positif'] = T['TOUS']['gain'] >= 0.001 and all(T[c]['gain'] >= -0.001 for c in ('ATP', 'WTA', 'CH') if c in T)
    if any(r.get('b') is not None for r in rows):
        out['appris']['beta_final'] = round([r['b'] for r in rows if r.get('b') is not None][-1], 4)
    out['decalage_moyen_abs'] = round(sum(abs(r['x']) for r in rows) / max(1, len(rows)), 4)
    with open(os.path.join(ICI, 'rapport_forme_service_corrigee.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(ICI, '..'))
