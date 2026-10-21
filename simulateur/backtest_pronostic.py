#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_pronostic.py — le modèle devine-t-il le vainqueur ? (21/10/2026)

Objectif fixé par Lucas : DEVINER l'issue (pas battre Pinnacle). Deux versions,
jugées côte à côte sur les mêmes matchs :
  * « stats seules »  : force Elo tirée des résultats (elo.py, paramètres
    FiveThirtyEight jamais réglés ici) ;
  * « stats + marché » : la cote Pinnacle de clôture, marge retirée.
Le détail des sets (2-0, 2-1…) vient du moteur (forme du jour) appliqué au
niveau de chaque version.

PROTOCOLE : tous les résultats sont rejoués dans l'ordre (archive Sackmann,
puis, depuis juin, nos matchs ET les résultats ATP/WTA de tennis-data,
historique/tennis_data_resultats.csv.gz) ; chaque match est PRONOSTIQUÉ avant
que son résultat ne mette le classement à jour. Un résultat tennis-data n'a
que la date : il est placé en FIN de journée (il ne sert jamais à pronostiquer
un match du même jour) et écarté s'il double l'un de nos matchs (même paire,
± 2 jours). Aucun réglage : rien ne regarde le futur.

Mesures : taux de vainqueurs devinés (une prédiction à 50 % compte pour ½),
log loss, Brier, calibration ; sur nos matchs, aussi le score en sets
(log score, « score le plus probable » juste ou non, 3 sets prévu / réel).
  A. ATP + WTA principaux, 2024 → janvier 2026 (tennis-data : clôture Pinnacle) ;
  B. nos matchs depuis juin 2026 (tous niveaux, Challengers et ITF compris).

Usage : python simulateur/backtest_pronostic.py DOSSIER_SACKMANN [racine]
Sorties : simulateur/rapport_pronostic.json, simulateur/elo_etat.json
"""
import collections
import datetime as dt
import json
import math
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees  # noqa: E402
import elo as E  # noqa: E402
import nos_resultats as NR  # noqa: E402

DEBUT_A, FIN_A = dt.date(2024, 1, 1), dt.date(2026, 2, 1)
N_CONNU = 10            # « joueurs connus » : au moins 10 matchs chacun avant le match
TABLE = os.path.join(ICI, 'table_sets.json')


def circuit(t):
    t = str(t or '').lower()
    if 'wta' in t or 'women' in t:
        return 'WTA'
    if 'itf' in t:
        return 'ITF'
    if 'challenger' in t:
        return 'CH'
    return 'ATP'


class Table:
    def __init__(self, chemin=TABLE):
        self.t = json.load(open(chemin, encoding='utf-8'))['circuits']

    def __call__(self, c, p_fav):
        L = self.t.get(c) or self.t['ATP']
        p = min(max(p_fav, L[0][0]), L[-1][0])
        i = min(int((p - L[0][0]) / 0.01), len(L) - 2)
        a, b = L[i], L[i + 1]
        w = (p - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0.0
        return dict(zip(('2-0', '2-1', '1-2', '0-2', 'set1'), [a[k] + w * (b[k] - a[k]) for k in range(1, 6)]))


def sets_home(T, c, p_home):
    """Distribution des scores du point de vue de HOME depuis sa probabilité de victoire."""
    fav = p_home >= 0.5
    d = T(c, p_home if fav else 1 - p_home)
    if fav:
        return {k: d[k] for k in ('2-0', '2-1', '1-2', '0-2')}
    return {'2-0': d['0-2'], '2-1': d['1-2'], '1-2': d['2-1'], '0-2': d['2-0']}


def juste(c1, c2):
    a, b = 1 / c1, 1 / c2
    lo, hi = 1e-6, 1.0
    f = lambda k: a ** k + b ** k - 1
    while f(hi) > 0:
        hi *= 2
    for _ in range(80):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if f(m) > 0 else (lo, m)
    return a ** ((lo + hi) / 2)


def bloc(items):
    """items : [(p, y)] — p = probabilité que l'issue y=1 arrive."""
    n = len(items)
    if not n:
        return {'n': 0}
    acc = sum(1.0 if (p > 0.5) == bool(y) and p != 0.5 else (0.5 if p == 0.5 else 0.0) for p, y in items) / n
    se = math.sqrt(acc * (1 - acc) / n)
    return {'n': n, 'reussite_pct': round(100 * acc, 1), 'ic95_pct': [round(100 * (acc - 1.96 * se), 1), round(100 * (acc + 1.96 * se), 1)],
            'log_loss': round(sum(E.log_loss(p, y) for p, y in items) / n, 4),
            'brier': round(sum((p - y) ** 2 for p, y in items) / n, 4)}


def calibration(items):
    """Côté du favori de la version : prévu vs réel par tranche."""
    out = []
    for lo in (0.5, 0.6, 0.7, 0.8, 0.9):
        g = [(max(p, 1 - p), y if p >= 0.5 else 1 - y) for p, y in items if lo <= max(p, 1 - p) < lo + 0.1 or (lo == 0.9 and max(p, 1 - p) == 1)]
        if len(g) >= 30:
            out.append({'tranche': f"{int(lo * 100)}–{int(lo * 100 + 10)} %", 'n': len(g),
                        'prevu': round(100 * sum(p for p, _ in g) / len(g), 1), 'reel': round(100 * sum(y for _, y in g) / len(g), 1)})
    return out


def resultats_td(chemin, depuis):
    """[(date, vainqueur, perdant, circuit)] des résultats tennis-data postérieurs à `depuis`."""
    import csv
    import gzip
    out = []
    try:
        with gzip.open(chemin, 'rt', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                try:
                    d = dt.date.fromisoformat(r['date'])
                except (KeyError, ValueError):
                    continue
                if d > depuis and r.get('vainqueur') and r.get('perdant'):
                    out.append((d, r['vainqueur'], r['perdant'], r.get('circuit')))
    except OSError:
        pass
    return out


def index_td(noms_par_cle, sexe=None):
    """(nom de famille, initiale) -> {(clé, mots du nom, sexe)} pour relier les noms tennis-data.
    sexe : {clé: 'H' | 'F'} (circuits où le joueur a joué), pour départager les homonymes."""
    sexe = sexe or {}
    idx = collections.defaultdict(set)
    for k, nm in noms_par_cle.items():
        cles, t = donnees.cles_sackmann_etendues(nm)
        for c in cles:
            idx[c].add((k, tuple(t), sexe.get(k)))
    return idx


def cle_tennis_data(idx, nom, circuit_td=None):
    """Clé du joueur pour « Wang Xin. » / « Mpetshi G. » ; None si inconnu ou ambigu.
    circuit_td 'ATP' / 'WTA' écarte les homonymes de l'autre circuit (« Nakashima B. »)."""
    k = donnees.cle_td_prefixe(nom)
    if not k:
        return None
    s = {'ATP': 'H', 'WTA': 'F'}.get(str(circuit_td or '').upper())
    cands = {c for c, t, sx in idx.get((k[0], k[1][0]), ())
             if any(w.startswith(k[1]) for w in t) and (s is None or sx in (None, s))}
    return next(iter(cands)) if len(cands) == 1 else None


def sexe_de_circuit(c):
    return 'F' if c in ('WTA', 'ITF') else 'H'


BAS = ('CH', 'ITF')          # niveaux où un nouveau joueur part plus bas (règle Tennis Abstract)
DEPART_BAS = 1200.0


def rejouer(M, nous, td_rows, cle_c, idx, depart_bas):
    """Rejoue tout dans l'ordre ; renvoie classement, pronostics de l'archive et de nos matchs."""
    elo, noms, pred_sack = E.Elo(), {}, {}
    bas, tot = collections.Counter(), collections.Counter()

    def voir(k, circ):
        if depart_bas and circ in BAS:
            elo.presenter(k, DEPART_BAS)
        tot[k] += 1
        bas[k] += circ in BAS

    for i, m in enumerate(M):
        g, p = cle_c(m['nom_g']), cle_c(m['nom_p'])
        noms[g], noms[p] = m['nom_g'], m['nom_p']
        voir(g, m['circuit'])
        voir(p, m['circuit'])
        if DEBUT_A <= m['date'] < FIN_A and m['circuit'] in ('ATP', 'WTA'):
            pred_sack[i] = (elo.proba(g, p, m['surface']), min(elo.matchs(g), elo.matchs(p)))
        elo.maj(g, p, m['surface'], m.get('niveau') == 'G')
    paires_nous = collections.defaultdict(list)
    for x in nous:
        paires_nous[frozenset((cle_c(x['home']), cle_c(x['away'])))].append(x['date'])
    ev, cpt = [], collections.Counter()
    for d, w, l, _c in td_rows:
        w_, l_ = cle_tennis_data(idx, w, _c), cle_tennis_data(idx, l, _c)
        if not w_ or not l_:
            cpt['non_reconnus'] += 1
            continue
        if any(abs((d - d2).days) <= 2 for d2 in paires_nous.get(frozenset((w_, l_)), [])):
            cpt['doublons_ecartes'] += 1
            continue
        ev.append((dt.datetime.combine(d, dt.time(23, 59, 59)), 'td', (w_, l_)))
        cpt['ajoutes'] += 1
    for x in nous:
        ev.append((x['debut'], 'nous', x))
    ev.sort(key=lambda e: (e[0], e[1] == 'td'))
    B = []
    for _t, src, x in ev:
        if src == 'td':
            elo.maj(x[0], x[1])                       # surface inconnue : Elo général seulement
            continue
        h, a = cle_c(x['home']), cle_c(x['away'])
        noms.setdefault(h, x['home'])
        noms.setdefault(a, x['away'])
        c = circuit(x['tournoi'])
        if depart_bas and c in BAS:
            elo.presenter(h, DEPART_BAS)
            elo.presenter(a, DEPART_BAS)
        p = elo.proba(h, a, x['surface'])
        fav = h if p >= 0.5 else a
        B.append(dict(x, p_elo=p, connus=min(elo.matchs(h), elo.matchs(a)),
                      part_bas_fav=(bas[fav] / tot[fav]) if tot[fav] else None))
        tot[h] += 1; tot[a] += 1
        bas[h] += c in BAS; bas[a] += c in BAS
        if x['gagnant'] in ('home', 'away'):
            w, l = (h, a) if x['gagnant'] == 'home' else (a, h)
            elo.maj(w, l, x['surface'], x.get('grand_chelem', False))
    return {'elo': elo, 'noms': noms, 'pred_sack': pred_sack, 'B': B, 'td': dict(cpt)}


def evaluer(V, M, td, T):
    """Rapports A (ATP/WTA contre tennis-data) et B (nos matchs) d'une variante."""
    idx = {id(m): i for i, m in enumerate(M)}
    A = []
    for t, m in donnees.joindre(td, M):
        i = idx.get(id(m))
        if i in V['pred_sack'] and t['date'] < FIN_A:
            p, nc = V['pred_sack'][i]
            A.append({'p_elo': p, 'p_pin': juste(t['psw'], t['psl']), 'connus': nc, 'circuit': m['circuit'],
                      'bo': m['bo'], 'sets': m['sets'], 'complet': m['complet']})
    rapA = {}
    for nom, g in (('tous', A), ('joueurs connus (≥ 10 matchs)', [a for a in A if a['connus'] >= N_CONNU]),
                   ('ATP', [a for a in A if a['circuit'] == 'ATP']), ('WTA', [a for a in A if a['circuit'] == 'WTA'])):
        rapA[nom] = {'stats_seules': bloc([(a['p_elo'], 1) for a in g]), 'stats_plus_marche': bloc([(a['p_pin'], 1) for a in g])}
    rapA['calibration_stats_seules'] = calibration([(a['p_elo'], 1) if k % 2 else (1 - a['p_elo'], 0) for k, a in enumerate(A)])
    rapA['calibration_marche'] = calibration([(a['p_pin'], 1) if k % 2 else (1 - a['p_pin'], 0) for k, a in enumerate(A)])
    rapA['matchs'] = len(A)
    R = [b for b in V['B'] if b['gagnant'] in ('home', 'away')]
    y = lambda b: int(b['gagnant'] == 'home')
    rapB = {}
    for nom, g in (('tous', R), ('joueurs connus (≥ 10 matchs)', [b for b in R if b['connus'] >= N_CONNU])) + tuple(
            (c, [b for b in R if circuit(b['tournoi']) == c]) for c in ('ATP', 'CH', 'WTA', 'ITF')):
        rapB[nom] = {'stats_seules': bloc([(b['p_elo'], y(b)) for b in g]),
                     'stats_plus_marche': bloc([(b['pin'], y(b)) for b in g if b['pin']])}
    rapB['calibration_stats_seules'] = calibration([(b['p_elo'], y(b)) for b in R])
    rapB['calibration_marche'] = calibration([(b['pin'], y(b)) for b in R if b['pin']])
    # ---- diagnostic (point 1) : où le classement se trompe-t-il de confiance ?
    diag = {'par_circuit': {}, 'par_origine_du_favori': {}}
    for c in ('ATP', 'CH', 'WTA'):
        g = [b for b in R if circuit(b['tournoi']) == c]
        diag['par_circuit'][c] = calibration([(b['p_elo'], y(b)) for b in g])
    for nom, lo, hi in (('surtout ITF / Challenger (≥ 70 % de ses matchs)', 0.7, 1.01), ('mixte (30–70 %)', 0.3, 0.7),
                        ('surtout grand circuit (< 30 %)', -0.01, 0.3)):
        g = [b for b in R if b['part_bas_fav'] is not None and lo <= b['part_bas_fav'] < hi]
        diag['par_origine_du_favori'][nom] = {'n': len(g), 'stats_seules': bloc([(b['p_elo'], y(b)) for b in g]),
                                               'calibration': calibration([(b['p_elo'], y(b)) for b in g])}
    rapB['diagnostic'] = diag
    S = [b for b in R if b['bo'] == 3 and b['sets'] and b['pin']]
    sc = {}
    for nom, cle_p in (('stats_seules', 'p_elo'), ('stats_plus_marche', 'pin')):
        ls, juste_, p3, r3 = 0.0, 0, 0.0, 0
        for b in S:
            d = sets_home(T, circuit(b['tournoi']), b[cle_p])
            ls += -math.log(max(d[b['sets']], 1e-6))
            juste_ += max(d, key=d.get) == b['sets']
            p3 += d['2-1'] + d['1-2']
            r3 += b['sets'] in ('2-1', '1-2')
        n = len(S) or 1
        sc[nom] = {'n': len(S), 'log_score': round(ls / n, 4), 'score_le_plus_probable_juste_pct': round(100 * juste_ / n, 1),
                   'trois_sets_prevu_pct': round(100 * p3 / n, 1), 'trois_sets_reel_pct': round(100 * r3 / n, 1)}
    rapB['scores_en_sets'] = sc
    return rapA, rapB, A


SERVICE_MOYEN = {'ATP': 0.646, 'WTA': 0.559}


def scores_exacts(A):
    """Point 4 : le score EXACT (set par set) des matchs ATP/WTA, deux versions."""
    import modele as Mo
    cache = {}

    def dist(c, bo, pf):
        k = (c, bo, round(min(max(pf, 0.5), 0.99), 2))
        if k not in cache:
            sg = 3 if bo == 5 else 2
            a, b = Mo.ancrer_forme(SERVICE_MOYEN[c], SERVICE_MOYEN[c], k[2], sg, 0.15, iterations=20)
            cache[k] = dict(Mo.scores_complets(a, b, sg, 0.15, top=10 ** 7, faisceau=1500)['scores'])
        return cache[k]

    def sets_de(s):
        return [tuple(int(v) for v in x.split('-')) for x in s.split()]
    EV = {'au moins un tie-break': lambda S: any({a, b} == {6, 7} for a, b in S),
          'au moins un set à 6-0 ou 6-1': lambda S: any(min(a, b) <= 1 for a, b in S),
          'match en 3 sets': lambda S: len(S) == 3,
          'plus de 22,5 jeux': lambda S: sum(a + b for a, b in S) > 22.5}
    out = {}
    G = [a for a in A if a['complet'] and a['sets'] and a['circuit'] in SERVICE_MOYEN]
    for nom, cle_p in (('stats_seules', 'p_elo'), ('stats_plus_marche', 'p_pin')):
        r = {}
        for bo in (3, 5):
            g = [a for a in G if a['bo'] == bo]
            if not g:
                continue
            pv, top1, top3, top10, ls = 0.0, 0, 0, 0, 0.0
            ev = {k: [0.0, 0] for k in EV}
            for a in g:
                p = a[cle_p]                                   # probabilité du VAINQUEUR réel
                fav = p >= 0.5
                D = dist(a['circuit'], bo, p if fav else 1 - p)
                s_reel = ' '.join(f"{x}-{y}" for x, y in a['sets'])          # vu du vainqueur
                s_fav = s_reel if fav else ' '.join(f"{y}-{x}" for x, y in a['sets'])
                q = D.get(s_fav, 0.0)
                rang = 1 + sum(1 for v in D.values() if v > q)
                pv += q
                ls += -math.log(max(q, 1e-9))
                top1 += rang == 1
                top3 += rang <= 3
                top10 += rang <= 10
                if bo == 3:
                    for k, f in EV.items():
                        ev[k][0] += sum(v for s_, v in D.items() if f(sets_de(s_)))
                        ev[k][1] += f(sets_de(s_fav))
            n = len(g)
            r[f'meilleur_des_{bo}'] = {'n': n, 'proba_moyenne_du_vrai_score_pct': round(100 * pv / n, 2), 'log_score': round(ls / n, 3),
                                       'score_n1_juste_pct': round(100 * top1 / n, 1), 'dans_le_top3_pct': round(100 * top3 / n, 1),
                                       'dans_le_top10_pct': round(100 * top10 / n, 1)}
            if bo == 3:
                r['evenements_meilleur_des_3'] = {k: {'prevu_pct': round(100 * v[0] / n, 1), 'reel_pct': round(100 * v[1] / n, 1)}
                                                   for k, v in ev.items()}
        out[nom] = r
    return out


def main(argv):
    t0 = time.time()
    args = [a for a in argv[1:] if not a.startswith('--')]
    avec_scores = '--scores' in argv
    dossier = args[0] if args else 'sackmann'
    racine = args[1] if len(args) > 1 else os.path.join(ICI, '..')
    M = donnees.charger(dossier, 2016)
    if not M:
        print(f"::error::aucun match Sackmann sous {dossier}")
        return 1
    fin_sack = max(m['date'] for m in M)
    table_surf = NR.surfaces_tournois(M)
    nous = [x for x in NR.charger(racine, table_surf) if x['date'] > fin_sack + dt.timedelta(days=3)]
    print(f"Sackmann : {len(M)} matchs jusqu'au {fin_sack} · nos matchs ensuite : {len(nous)}", flush=True)
    # Point 3 : un joueur = un classement, quel que soit l'écriture de son nom.
    connus = {}
    for m in M:
        connus.setdefault(E.cle(m['nom_g']), m['nom_g'])
        connus.setdefault(E.cle(m['nom_p']), m['nom_p'])
    alias = E.unifier(connus, {x['home'] for x in nous} | {x['away'] for x in nous})
    cle_c = lambda n: alias.get(E.cle(n), E.cle(n))
    noms_c = dict(connus)
    for x in nous:
        for n in (x['home'], x['away']):
            noms_c.setdefault(cle_c(n), n)
    sexe = {}
    for m in M:
        for n in (m['nom_g'], m['nom_p']):
            sexe.setdefault(cle_c(n), sexe_de_circuit(m['circuit']))
    for x in nous:
        sx = 'F' if circuit(x['tournoi']) == 'WTA' or 'women' in x['tournoi'].lower() else 'H'
        for n in (x['home'], x['away']):
            sexe.setdefault(cle_c(n), sx)
    idx = index_td(noms_c, sexe)
    td_rows = resultats_td(os.path.join(racine, 'historique', 'tennis_data_resultats.csv.gz'), fin_sack + dt.timedelta(days=3))
    td = donnees.charger_td(os.path.join(racine, 'historique', 'tennis_data.csv.gz'), DEBUT_A.isoformat())
    T = Table()
    V = {}
    for nom, bas_ in (('depart_1500', False), ('depart_1200_petits_niveaux', True)):
        V[nom] = rejouer(M, nous, td_rows, cle_c, idx, bas_)
        V[nom]['rapA'], V[nom]['rapB'], V[nom]['A'] = evaluer(V[nom], M, td, T)
        print(f"{nom} : A {V[nom]['rapA']['tous']['stats_seules']} · B {V[nom]['rapB']['tous']['stats_seules']}", flush=True)
    # Règle d'adoption fixée AVANT les résultats : la variante « départ bas » n'est retenue que si
    # elle améliore nos matchs (log loss B) sans dégrader l'ATP/WTA (log loss A, tolérance 0,001).
    a0, a1 = V['depart_1500']['rapA']['tous']['stats_seules'], V['depart_1200_petits_niveaux']['rapA']['tous']['stats_seules']
    b0, b1 = V['depart_1500']['rapB']['tous']['stats_seules'], V['depart_1200_petits_niveaux']['rapB']['tous']['stats_seules']
    a_ok = (a0.get('n', 0) == 0 and a1.get('n', 0) == 0) or \
        ('log_loss' in a0 and 'log_loss' in a1 and a1['log_loss'] <= a0['log_loss'] + 0.001)
    b_ok = 'log_loss' in b0 and 'log_loss' in b1 and b1['log_loss'] < b0['log_loss']
    retenue = 'depart_1200_petits_niveaux' if (a_ok and b_ok) else 'depart_1500'
    W = V[retenue]
    rap = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'objectif': 'deviner le vainqueur et le score (pas battre Pinnacle)',
           'elo': 'FiveThirtyEight (Kovalchik 2016) : K = 250/(n+5)^0,4, ×1,1 en Grand Chelem ; général + surface à parts égales ; aucun réglage',
           'variantes': {k: {'A': v['rapA']['tous']['stats_seules'], 'B': v['rapB']['tous']['stats_seules'],
                             'B_calibration': v['rapB']['calibration_stats_seules'], 'tennis_data': v['td']} for k, v in V.items()},
           'regle_adoption': "départ bas retenu seulement si log loss B baisse et log loss A ne monte pas de plus de 0,001",
           'variante_retenue': retenue,
           'joueurs_relies_nom_different': len(alias),
           'sackmann_jusqu_au': fin_sack.isoformat(), 'nos_matchs': len(nous),
           'resultats_tennis_data_ajoutes': W['td'],
           'A_atp_wta_2024_2026': dict(W['rapA'], periode=f"{DEBUT_A} → {FIN_A}"),
           'B_nos_matchs': dict(W['rapB'], periode=f"{nous[0]['date'] if nous else '—'} → {nous[-1]['date'] if nous else '—'}")}
    if avec_scores:
        print("scores exacts…", flush=True)
        rap['scores_exacts_atp_wta'] = scores_exacts(W['A'])
    rap['duree_s'] = round(time.time() - t0)
    with open(os.path.join(ICI, 'rapport_pronostic.json'), 'w', encoding='utf-8') as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    elo = W['elo']
    with open(os.path.join(ICI, 'elo_etat.json'), 'w', encoding='utf-8') as f:
        json.dump({'genere_le': rap['genere_le'], 'dernier_match': str(nous[-1]['date'] if nous else fin_sack),
                   'variante': retenue, 'depart_bas': DEPART_BAS if retenue != 'depart_1500' else None,
                   'surfaces_tournois': table_surf, 'alias': alias, 'joueurs': elo.exporter(W['noms'])},
                  f, ensure_ascii=False, separators=(',', ':'))
    print(json.dumps({k: rap[k] for k in ('variantes', 'variante_retenue', 'joueurs_relies_nom_different')}, ensure_ascii=False, indent=1))
    if avec_scores:
        print(json.dumps(rap['scores_exacts_atp_wta'], ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
