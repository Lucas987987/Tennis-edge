#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_forme_veille.py — la FORME LUE dans le match précédent (la veille, l'avant-veille) aide-t-elle AVANT le match
suivant ? (06/11/2026, demande de Lucas après le % en direct réévalué : « testons quand même le pré-live »).

FORME D'UN MATCH : comme le % en direct réévalué (etude_live_reevaluation.py), la forme du jour z (logit : service de
home + z, de away − z ; a priori normal, σ = 0,15 ATP / WTA, 0,225 Challenger) est lue dans TOUS les points de service
du match (feuilles TennisApi, juin → novembre 2026), autour des probabilités d'avant match ancrées sur le % publié
(Elo + simulation, point-in-time). Forme du joueur dans ce match = moyenne a posteriori de z (home) ou − z (away).

DEUX VARIABLES AVANT LE MATCH M, joueur A moins joueur B, avec seulement les matchs JOUÉS AVANT M :
  — veille : la forme du DERNIER match du joueur s'il a eu lieu dans les 4 jours, sinon 0 ;
  — 30 jours : la moyenne des formes de ses matchs des 30 derniers jours (dernier compris), rappelée vers 0
    (somme / (n + 3)) — c'est l'équivalent, en forme lue, du facteur « forme_fatigue » déjà jugé chaque semaine.
La question : la VEILLE apporte-t-elle quelque chose EN PLUS des 30 jours ?

DEUX MESURES, apprises sur juin → août 2026, jugées sur septembre → novembre 2026, circuit par circuit :
  1. VAINQUEUR : logit p = logit(% d'avant match) + β30 · x30 + βv · xveille ;
  2. DÉROULEMENT : points de service du match M : P(home gagne son point de service) = σ(logit a + γ30 · x30 + γv · xv),
     P(away) = σ(logit b − γ30 · x30 − γv · xv) — log loss par point de service.
RÈGLE FIXÉE LE 06/11/2026, AVANT DE REGARDER LE RÉSULTAT : la veille est RETENUE pour une mesure si, sur le jugement,
le modèle « 30 jours + veille » fait mieux que « 30 jours seuls » d'au moins 0,001 (vainqueur, par match) ou de
0,0005 (déroulement, par point de service), sur au moins 1 000 matchs jugés, ET si le coefficient de la veille appris
sur le jugement a le même signe. Moins de 1 000 matchs jugés : « en attente ». Pour information : les 30 jours seuls
contre le % d'avant match.
Usage : python simulateur/etude_forme_veille.py /tmp/sackmann [racine]
"""
import bisect
import collections
import datetime as dt
import json
import math
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_live_reevaluation as LR  # noqa: E402

SIGMA = {'ATP': 0.15, 'WTA': 0.15, 'CH': 0.225}
COUPURE = dt.date(2026, 9, 1)
VEILLE_S, FENETRE_S, RAPPEL = 4 * 86400, 30 * 86400, 3.0
MIN_JUGES, MARGE_V, MARGE_P = 1000, 0.001, 0.0005
SORTIE = os.path.join(ICI, 'rapport_forme_veille.json')
_lg, _sg = LR._lg, LR._sg


def forme_du_match(t):
    """(a, b ancrés, z a posteriori) pour un match : t = (a0, b0, p_elo, w_elo, w_sim, n, tbf, sigma, wA, nA, wB, nB)."""
    a0, b0, p_elo, w_elo, w_sim, n, tbf, s, wA, nA, wB, nB = t
    p_sim = sum(w * LR.Etat(_sg(_lg(a0) + z), _sg(_lg(b0) - z), n, tbf).avant_match() for z, w in LR.noeuds(0.15))
    p = _sg(w_elo * _lg(p_elo) + w_sim * _lg(p_sim))
    a, b = LR.ancrer(a0, b0, p, n, tbf, s)
    la, lb = _lg(a), _lg(b)
    lw = []
    for z, w in LR.noeuds(s):
        pa, pb = _sg(la + z), _sg(lb - z)
        lw.append((math.log(w) + wA * math.log(pa) + (nA - wA) * math.log(1 - pa)
                   + wB * math.log(pb) + (nB - wB) * math.log(1 - pb), z))
    mx = max(x for x, _ in lw)
    tot = sum(math.exp(x - mx) for x, _ in lw)
    zm = sum(math.exp(x - mx) * z for x, z in lw) / tot
    return p, a, b, zm


def newton(R, X, f_ll, iters=25):
    """Coefficients (liste) minimisant la log loss moyenne f_ll(R, coefs) — Newton à différences finies (2 coefs au plus)."""
    c = [0.0] * len(X)
    h = 1e-4
    for _ in range(iters):
        f0 = f_ll(R, c)
        g = []
        H = [[0.0] * len(c) for _ in c]
        for i in range(len(c)):
            ci = c[:]; ci[i] += h
            cm = c[:]; cm[i] -= h
            fp, fm = f_ll(R, ci), f_ll(R, cm)
            g.append((fp - fm) / (2 * h))
            H[i][i] = (fp - 2 * f0 + fm) / (h * h)
        if len(c) == 2:
            cpp = [c[0] + h, c[1] + h]; cmm = [c[0] - h, c[1] - h]
            cpm = [c[0] + h, c[1] - h]; cmp_ = [c[0] - h, c[1] + h]
            H[0][1] = H[1][0] = (f_ll(R, cpp) - f_ll(R, cpm) - f_ll(R, cmp_) + f_ll(R, cmm)) / (4 * h * h)
            det = H[0][0] * H[1][1] - H[0][1] ** 2
            if det <= 0:
                break
            d = [(H[1][1] * g[0] - H[0][1] * g[1]) / det, (H[0][0] * g[1] - H[0][1] * g[0]) / det]
        else:
            if H[0][0] <= 0:
                break
            d = [g[0] / H[0][0]]
        c = [ci - di for ci, di in zip(c, d)]
        if max(abs(x) for x in d) < 1e-7:
            break
    return c


def ll_vainqueur(X):
    def f(R, c):
        t = 0.0
        for r in R:
            z = _lg(r['p']) + sum(ci * r[x] for ci, x in zip(c, X))
            q = _sg(z)
            t -= math.log(max(q if r['y'] else 1 - q, 1e-12))
        return t / max(1, len(R))
    return f


def ll_points(X):
    def f(R, c):
        t = n = 0.0
        for r in R:
            d = sum(ci * r[x] for ci, x in zip(c, X))
            pa, pb = _sg(_lg(r['a']) + d), _sg(_lg(r['b']) - d)
            t -= r['wA'] * math.log(pa) + (r['nA'] - r['wA']) * math.log(1 - pa)
            t -= r['wB'] * math.log(pb) + (r['nB'] - r['wB']) * math.log(1 - pb)
            n += r['nA'] + r['nB']
        return t / max(1, n)
    return f


def main(argv):
    t0 = time.time()
    archive = argv[1]
    racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    L, (w_elo, w_sim), _ = LR.lignes_matchs(archive, racine)
    T, M = [], []
    for x in L:
        if x['circuit'] not in SIGMA:
            continue
        n = 3 if x['bo'] == 5 else 2
        tbf = 10 if any(g in str(x.get('nom_tournoi') or '').lower() for g in LR.GRANDS) else 7
        sa, sb = x['srv']
        wA, wB = round(sa['res'] + sa['n'] * sa['p']), round(sb['res'] + sb['n'] * sb['p'])
        if sa['n'] < 20 or sb['n'] < 20:
            continue
        T.append((sa['p'], sb['p'], x['p_elo'], w_elo, w_sim, n, tbf, SIGMA[x['circuit']], wA, sa['n'], wB, sb['n']))
        M.append(x)
    print(f"{len(T)} matchs avec feuille complète ({round(time.time() - t0)} s)", flush=True)
    import multiprocessing as mp
    with mp.Pool(max(1, os.cpu_count() or 1)) as pool:
        F = pool.map(forme_du_match, T, chunksize=50)
    print(f"formes lues ({round(time.time() - t0)} s)", flush=True)
    # historique par joueur : (début, forme du joueur)
    H = collections.defaultdict(list)
    ordre = sorted(range(len(M)), key=lambda i: M[i]['t'])
    rows = []
    for i in ordre:
        x, (p, a, b, z), t = M[i], F[i], T[i]
        ts = x['t']
        var = {}
        for cle, j in (('A', x['a']), ('B', x['b'])):
            Lj = H[j]
            k = bisect.bisect_left(Lj, (ts,))
            avant = Lj[:k]
            der = avant[-1] if avant else None
            veille = der[1] if der and ts - der[0] <= VEILLE_S else 0.0
            rec = [f for tt, f in avant if ts - tt <= FENETRE_S]
            var[cle] = (veille, sum(rec) / (len(rec) + RAPPEL), bool(der and ts - der[0] <= VEILLE_S))
        rows.append({'c': x['circuit'], 'jour': x['jour'], 'p': p, 'a': a, 'b': b, 'y': 1 if x['vainqueur'] == 0 else 0,
                     'xv': var['A'][0] - var['B'][0], 'x30': var['A'][1] - var['B'][1],
                     'veille_connue': var['A'][2] or var['B'][2],
                     'wA': t[8], 'nA': t[9], 'wB': t[10], 'nB': t[11]})
        bisect.insort(H[x['a']], (ts, z))
        bisect.insort(H[x['b']], (ts, -z))
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("veille retenue si « 30 jours + veille » bat « 30 jours seuls » sur sept. → nov. 2026 d'au moins 0,001 "
                     "(vainqueur, par match) ou 0,0005 (déroulement, par point de service), sur ≥ 1 000 matchs jugés, "
                     "coefficient de la veille de même signe appris sur le jugement"),
           'matchs': len(rows), 'circuits': {}}
    for c in ('ATP', 'WTA', 'CH', 'tous'):
        R = [r for r in rows if c == 'tous' or r['c'] == c]
        ap, ju = [r for r in R if r['jour'] < COUPURE], [r for r in R if r['jour'] >= COUPURE]
        bloc = {'matchs': {'appr': len(ap), 'juge': len(ju)},
                'part_avec_un_match_dans_les_4_jours_pct': round(100 * sum(r['veille_connue'] for r in ju) / max(1, len(ju)), 1)}
        for nom, fab, marge in (('vainqueur', ll_vainqueur, MARGE_V), ('deroulement', ll_points, MARGE_P)):
            f30, f2 = fab(['x30']), fab(['x30', 'xv'])
            c30 = newton(ap, ['x30'], f30)
            c2 = newton(ap, ['x30', 'xv'], f2)
            c2j = newton(ju, ['x30', 'xv'], f2)
            base = f30(ju, [0.0])
            l30, l2 = f30(ju, c30), f2(ju, c2)
            gain = l30 - l2
            ok = len(ju) >= MIN_JUGES and gain >= marge and c2[1] * c2j[1] > 0
            bloc[nom] = {'coef_30j_seul': round(c30[0], 4), 'coefs_30j_veille': [round(v, 4) for v in c2],
                         'coefs_30j_veille_appris_sur_le_jugement': [round(v, 4) for v in c2j],
                         'log_loss_juge': {'avant_match': round(base, 5), '30_jours': round(l30, 5),
                                           '30_jours_et_veille': round(l2, 5)},
                         'gain_30_jours_seuls': round(base - l30, 5), 'gain_veille_en_plus': round(gain, 5),
                         'verdict': ('information' if c == 'tous' else 'RETENUE' if ok else
                                     'en attente (moins de 1 000 matchs jugés)' if len(ju) < MIN_JUGES else 'non retenue')}
        doc['circuits'][c] = bloc
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
