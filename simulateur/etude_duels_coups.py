#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_duels_coups.py — le détail des coups donne-t-il un avantage à l'un des joueurs, au-delà de l'Elo ? (12/11/2026,
paquet 250, demande de Lucas après le tiroir « Points marqués »)

DONNÉES. Archive Sackmann (vainqueur, perdant, date du tournoi) et Match Charting Project (matchs relevés coup par coup,
Jeff Sackmann et bénévoles, CC BY-NC-SA 4.0). Base : l'Elo de production corrigé des pentes en place et des signaux en
place sur le circuit (etude_signaux_reappris.py, comme etude_balayage_pistes.py), vu du vainqueur.
PROFIL D'UN JOUEUR À LA DATE D : ses matchs relevés des 3 ans avant D (jamais le tournoi jugé : date < début du
tournoi), au moins 10. Pour chaque match relevé, on garde aussi ce que son ADVERSAIRE a fait contre lui.

LES CINQ DUELS, ÉCRITS LE 12/11/2026 AVANT TOUT CALCUL (x vu du vainqueur A contre le perdant B ; m = moyenne du
circuit sur les profils de 2018–2022) :
  filet          fA·((wA + cB)/2 − m) − fB·((wB + cA)/2 − m)   f = montées au filet par point joué, w = part des points
                 gagnés au filet, c = part des points que ses adversaires gagnent au filet contre lui
  amorti         même forme : f = amortis joués par point, w = amortis gagnants ou faute provoquée, c = idem chez ses
                 adversaires contre lui
  service rapide ((rA + cB)/2 − m) − ((rB + cA)/2 − m)   r = part de ses points de service gagnés en 3 frappes ou moins,
                 c = la même part chez ses adversaires quand il retourne
  coups gagnants gA − gB   g = (coups gagnants + fautes provoquées) par point joué, hors service
  fautes directes eB − eA  e = fautes directes par point joué
Chaque variable est divisée par sa moyenne quadratique sur les matchs d'apprentissage du circuit (unité commune ; jamais
centrée : les lignes sont vues du vainqueur, une moyenne retirée ferait une constante « le vainqueur gagne »).
RÈGLE (celle du dépôt) : par duel et par circuit (ATP, WTA ; le Challenger n'est presque pas relevé), β appris sur les
matchs concernés de 2018–2022, jugé sur ceux de 2023 → juin 2026 : RETENU si la log loss du vainqueur baisse d'au moins
0,001 sur au moins 1 000 matchs concernés jugés ET si β appris sur 2023 → a le même signe. Dix essais : un duel retenu
de justesse (moins de 2 erreurs types) est signalé comme tel. Retenu → candidat au fantôme, jamais en production ici.
Sinon : le duel reste une information descriptive dans le tiroir, avec « ne change pas le % ».

Usage : python simulateur/etude_duels_coups.py /tmp/sackmann . [/tmp/mcp]
"""
import bisect
import collections
import csv
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import coups_joueurs as CJ  # noqa: E402

SORTIE = os.path.join(ICI, 'rapport_duels_coups.json')
FENETRE_J, MIN_MATCHS = 3 * 365, 10
DUELS = ('filet', 'amorti', 'service_rapide', 'coups_gagnants', 'fautes_directes')
CIRCUITS = ('ATP', 'WTA')
MIN_JUGES, MARGE = 1000, 0.001
CHAMPS = ('pj', 'net', 'net_g', 'a_net', 'a_net_g', 'dr', 'dr_g', 'a_dr', 'a_dr_g', 'srv', 'srv_r', 'a_srv', 'a_srv_r',
          'gp', 'ue')
DROP = 'UY'


def _st_row(st, k):
    return st.get(k) or {}


def comptes(ov, st, sb, net, ov_a, st_a, sb_a, net_a):
    i = CJ._i
    dr = sum(i(_st_row(st, k).get('shots')) for k in DROP)
    dr_g = sum(i(_st_row(st, k).get('winners')) + i(_st_row(st, k).get('induced_forced')) for k in DROP)
    a_dr = sum(i(_st_row(st_a, k).get('shots')) for k in DROP)
    a_dr_g = sum(i(_st_row(st_a, k).get('winners')) + i(_st_row(st_a, k).get('induced_forced')) for k in DROP)
    tot = _st_row(st, 'Total')
    return {'pj': i(ov.get('serve_pts')) + i(ov.get('return_pts')),
            'net': i((net or {}).get('net_pts')), 'net_g': i((net or {}).get('pts_won')),
            'a_net': i((net_a or {}).get('net_pts')), 'a_net_g': i((net_a or {}).get('pts_won')),
            'dr': dr, 'dr_g': dr_g, 'a_dr': a_dr, 'a_dr_g': a_dr_g,
            'srv': i(sb.get('pts')), 'srv_r': i(sb.get('pts_won_lte_3_shots')),
            'a_srv': i(sb_a.get('pts')), 'a_srv_r': i(sb_a.get('pts_won_lte_3_shots')),
            'gp': i(tot.get('winners')) + i(tot.get('induced_forced')), 'ue': i(tot.get('unforced'))}


def charger(dossier, cle):
    """{clé: (dates triées, sommes cumulées)} et le circuit (m / w) de chaque joueur."""
    par = collections.defaultdict(list)
    for g in ('m', 'w'):
        f = lambda n: os.path.join(dossier, f'charting-{g}-{n}.csv')  # noqa: E731
        dates = {}
        for r in CJ._lire(f('matches')):
            try:
                d = str(r.get('Date') or '')
                dates[r['match_id']] = dt.date(int(d[:4]), int(d[4:6]), int(d[6:8]))
            except (KeyError, ValueError):
                continue
        ov = {(r['match_id'], r['player']): r for r in CJ._lire(f('stats-Overview')) if r.get('set') == 'Total'}
        sb = {(r['match_id'], r['player']): r for r in CJ._lire(f('stats-ServeBasics')) if r.get('row') == 'Total'}
        net = {(r['match_id'], r['player']): r for r in CJ._lire(f('stats-NetPoints')) if r.get('row') == 'NetPoints'}
        st = collections.defaultdict(dict)
        for r in CJ._lire(f('stats-ShotTypes')):
            st[(r['match_id'], r['player'])][r['row']] = r
        pm = collections.defaultdict(list)
        for (mid, p) in ov:
            pm[mid].append(p)
        for mid, ps in pm.items():
            if len(ps) != 2 or mid not in dates:
                continue
            for i in (0, 1):
                p, q = ps[i], ps[1 - i]
                if not all(x in st for x in ((mid, p), (mid, q))) or (mid, p) not in sb or (mid, q) not in sb:
                    continue
                c = comptes(ov[(mid, p)], st[(mid, p)], sb[(mid, p)], net.get((mid, p)), ov[(mid, q)], st[(mid, q)],
                            sb[(mid, q)], net.get((mid, q)))
                if c['pj'] > 0 and cle(p):
                    par[(cle(p), g)].append((dates[mid], c))
    out = {}
    for (k, g), L in par.items():
        L.sort(key=lambda x: x[0])
        cum, s = [], collections.Counter()
        for _, c in L:
            s.update(c)
            cum.append(dict(s))
        out[(k, g)] = ([d for d, _ in L], cum)
    return out


def profil(P, k, g, jour):
    """Sommes des matchs relevés dans [jour − 3 ans, jour), ou None sous MIN_MATCHS."""
    e = P.get((k, g))
    if not e:
        return None
    D, C = e
    i1 = bisect.bisect_left(D, jour)
    i0 = bisect.bisect_left(D, jour - dt.timedelta(days=FENETRE_J))
    if i1 - i0 < MIN_MATCHS:
        return None
    haut, bas = C[i1 - 1], (C[i0 - 1] if i0 > 0 else {})
    return {x: haut.get(x, 0) - bas.get(x, 0) for x in CHAMPS}


def _r(a, b):
    return a / b if b else None


def taux(s):
    return {'f_net': _r(s['net'], s['pj']), 'w_net': _r(s['net_g'], s['net']), 'c_net': _r(s['a_net_g'], s['a_net']),
            'f_dr': _r(s['dr'], s['pj']), 'w_dr': _r(s['dr_g'], s['dr']), 'c_dr': _r(s['a_dr_g'], s['a_dr']),
            'r': _r(s['srv_r'], s['srv']), 'c_r': _r(s['a_srv_r'], s['a_srv']),
            'g': _r(s['gp'], s['pj']), 'e': _r(s['ue'], s['pj'])}


def variables(tA, tB, m):
    """{duel: x vu de A} (None si une part manque)."""
    def duel(f, w, c, mm):
        if None in (tA[f], tA[w], tB[c], tB[f], tB[w], tA[c], mm):
            return None
        return tA[f] * ((tA[w] + tB[c]) / 2 - mm) - tB[f] * ((tB[w] + tA[c]) / 2 - mm)
    out = {'filet': duel('f_net', 'w_net', 'c_net', m.get('net')), 'amorti': duel('f_dr', 'w_dr', 'c_dr', m.get('dr'))}
    out['service_rapide'] = (None if None in (tA['r'], tB['c_r'], tB['r'], tA['c_r']) else
                             (tA['r'] + tB['c_r']) / 2 - (tB['r'] + tA['c_r']) / 2)
    out['coups_gagnants'] = None if None in (tA['g'], tB['g']) else tA['g'] - tB['g']
    out['fautes_directes'] = None if None in (tA['e'], tB['e']) else tB['e'] - tA['e']
    return out


def moyennes(P, g, fin):
    """Moyennes du circuit (m / w) sur les matchs relevés avant `fin` : part des points au filet et des amortis gagnés."""
    s = collections.Counter()
    for (k, gg), (D, C) in P.items():
        if gg != g:
            continue
        i = bisect.bisect_left(D, fin)
        if i:
            s.update(C[i - 1])
    return {'net': _r(s['net_g'], s['net']), 'dr': _r(s['dr_g'], s['dr'])}


def juger(rows, duel, circuit):
    import etude_outsiders as EO
    import etude_signaux_combines as ESC
    import etude_signaux_reappris as ER
    R = [r for r in rows if r['c'] == circuit and r['v'].get(duel) is not None]
    av, ju = [r for r in R if r['d'] < ER.COUPURE], [r for r in R if r['d'] >= ER.COUPURE]
    out = {'matchs': {'2018–2022': len(av), '2023 → juin 2026': len(ju)}}
    if len(av) < 200 or not ju:
        return dict(out, retenu=False, note='trop peu de matchs concernés')
    # variable réduite sur l'apprentissage : la crête (ridge = 1) d'ESC.apprendre ne doit pas dépendre de l'unité de la
    # variable (premier passage : variables en parts de points, β écrasés vers 0 — corrigé avant toute conclusion)
    # JAMAIS centrée : les lignes sont vues du vainqueur, retirer une moyenne reviendrait à ajouter une constante
    # « le vainqueur gagne » (deuxième passage, corrigé avant toute conclusion) ; seulement réduite (moyenne quadratique)
    rms = (sum(r['v'][duel] ** 2 for r in av) / len(av)) ** .5 or 1.0
    x = lambda r: r['v'][duel] / rms  # noqa: E731
    b1 = ESC.apprendre([(r['zf'], (x(r),)) for r in av], k=1)[0]
    b2 = ESC.apprendre([(r['zf'], (x(r),)) for r in ju], k=1)[0]
    b = EO.bilan([r['zf'] for r in ju], [r['zf'] + b1 * x(r) for r in ju])
    ok = len(ju) >= MIN_JUGES and b['gain'] >= MARGE and b1 * b2 > 0
    return dict(out, beta_2018_2022=round(b1, 3), beta_2023=round(b2, 3), gain=b['gain'], erreur_type=b['erreur_type'],
                erreurs_types=b['erreurs_types'], retenu=bool(ok), de_justesse=bool(ok and (b['erreurs_types'] or 0) < 2))


def main(argv):
    import donnees as DN
    import elo as E
    import etude_age as EA
    import etude_signaux_reappris as ER
    archive = argv[1] if len(argv) > 1 else '/tmp/sackmann'
    racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    mcp = argv[3] if len(argv) > 3 else '/tmp/mcp'
    etat = ER._json(racine, 'elo_etat.json')
    alias = dict(E.migrer_etat(etat).get('alias') or {}) if etat else {}
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None  # noqa: E731
    P = charger(mcp, k)
    M = DN.charger(archive, 2012)
    Rr = ER._json(racine, 'rapport_signaux_reappris.json').get('circuits') or {}
    m = {g: moyennes(P, g, ER.COUPURE) for g in ('m', 'w')}
    rows = []
    for r in ER.lignes(M, racine, EA.naissances(archive, k), k, details=True):
        if r['c'] not in CIRCUITS:
            continue
        g = 'm' if r['c'] == 'ATP' else 'w'
        pa, pb = profil(P, r['g'], g, r['d']), profil(P, r['p'], g, r['d'])
        if not pa or not pb:
            continue
        R_ = Rr.get(r['c']) or {}
        b = R_.get('betas') if R_.get('adopte') else R_.get('betas_en_place')
        r['zf'] = ER._zc(r, [(b or {}).get(n, 0.0) for n in ER.NOMS])
        v = variables(taux(pa), taux(pb), m[g])
        rows.append({'d': r['d'], 'c': r['c'], 'zf': r['zf'], 'v': v})
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 250, 'statut': 'etude',
           'regle': ("par duel et par circuit : β appris sur les matchs concernés de 2018–2022, jugé sur 2023 → juin 2026 ; "
                     "retenu si −0,001 de log loss sur au moins 1 000 matchs concernés et β de même signe sur les deux "
                     "périodes ; base : Elo de production, pentes et signaux en place"),
           'source': 'Match Charting Project (Jeff Sackmann et bénévoles, CC BY-NC-SA 4.0)',
           'joueurs_releves': len(P), 'matchs_avec_deux_profils': {c: sum(1 for r in rows if r['c'] == c) for c in CIRCUITS},
           'moyennes_du_circuit': {g: {x: round(v, 4) for x, v in m[g].items() if v is not None} for g in m},
           'duels': {d: {c: juger(rows, d, c) for c in CIRCUITS} for d in DUELS}}
    doc['retenus'] = [f"{d} · {c}" for d in DUELS for c in CIRCUITS if doc['duels'][d][c].get('retenu')]
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps({x: doc[x] for x in ('joueurs_releves', 'matchs_avec_deux_profils', 'retenus')}, ensure_ascii=False))
    for d in DUELS:
        for c in CIRCUITS:
            print(d, c, json.dumps(doc['duels'][d][c], ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
