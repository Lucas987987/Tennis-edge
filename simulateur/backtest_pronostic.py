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


def index_noms(noms_complets):
    """(nom de famille, initiale) -> clés Elo possibles, pour relier « Bublik A. » à « Alexander Bublik »."""
    idx = collections.defaultdict(set)
    for nm in noms_complets:
        for k in donnees.cles_sackmann(nm):
            idx[k].add(E.cle(nm))
    return idx


def main(argv):
    t0 = time.time()
    dossier = argv[1] if len(argv) > 1 else 'sackmann'
    racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    M = donnees.charger(dossier, 2016)
    if not M:
        print(f"::error::aucun match Sackmann sous {dossier}")
        return 1
    fin_sack = max(m['date'] for m in M)
    table_surf = NR.surfaces_tournois(M)
    nous = [x for x in NR.charger(racine, table_surf) if x['date'] > fin_sack + dt.timedelta(days=3)]
    print(f"Sackmann : {len(M)} matchs jusqu'au {fin_sack} · nos matchs ensuite : {len(nous)}", flush=True)

    elo, noms = E.Elo(), {}
    pred_sack = {}
    for i, m in enumerate(M):                        # 1. archive : prédire puis mettre à jour
        g, p = E.cle(m['nom_g']), E.cle(m['nom_p'])
        noms[g], noms[p] = m['nom_g'], m['nom_p']
        if DEBUT_A <= m['date'] < FIN_A and m['circuit'] in ('ATP', 'WTA'):
            pred_sack[i] = (elo.proba(g, p, m['surface']), min(elo.matchs(g), elo.matchs(p)))
        elo.maj(g, p, m['surface'], m.get('niveau') == 'G')
    T = Table()
    # 2. depuis juin : nos matchs (pronostiqués puis appris) + résultats tennis-data (appris seulement)
    idx = index_noms(set(m['nom_g'] for m in M) | set(m['nom_p'] for m in M) | {x['home'] for x in nous} | {x['away'] for x in nous})
    paires_nous = collections.defaultdict(list)
    for x in nous:
        paires_nous[frozenset((E.cle(x['home']), E.cle(x['away'])))].append(x['date'])
    ev, td_ok, td_doublon, td_inconnu = [], 0, 0, 0
    for d, w, l, _c in resultats_td(os.path.join(racine, 'historique', 'tennis_data_resultats.csv.gz'), fin_sack + dt.timedelta(days=3)):
        kw, kl = idx.get(donnees.cle_td(w) or ('', '')), idx.get(donnees.cle_td(l) or ('', ''))
        if not kw or not kl or len(kw) != 1 or len(kl) != 1:
            td_inconnu += 1
            continue
        w_, l_ = next(iter(kw)), next(iter(kl))
        if any(abs((d - d2).days) <= 2 for d2 in paires_nous.get(frozenset((w_, l_)), [])):
            td_doublon += 1
            continue
        ev.append((dt.datetime.combine(d, dt.time(23, 59, 59)), 'td', (w_, l_)))
        td_ok += 1
    for x in nous:
        ev.append((x['debut'], 'nous', x))
    ev.sort(key=lambda e: (e[0], e[1] == 'td'))
    B = []
    for _t, src, x in ev:
        if src == 'td':
            elo.maj(x[0], x[1])                       # surface inconnue : Elo général seulement
            continue
        h, a = E.cle(x['home']), E.cle(x['away'])
        noms.setdefault(h, x['home'])
        noms.setdefault(a, x['away'])
        B.append(dict(x, p_elo=elo.proba(h, a, x['surface']), connus=min(elo.matchs(h), elo.matchs(a))))
        if x['gagnant'] in ('home', 'away'):
            w, l = (h, a) if x['gagnant'] == 'home' else (a, h)
            elo.maj(w, l, x['surface'], x.get('grand_chelem', False))
    print(f"tennis-data depuis juin : {td_ok} résultats ajoutés, {td_doublon} doublons de nos matchs, {td_inconnu} joueurs non reconnus", flush=True)

    # ---- A : ATP / WTA principaux contre tennis-data
    td = donnees.charger_td(os.path.join(racine, 'historique', 'tennis_data.csv.gz'), DEBUT_A.isoformat())
    idx = {id(m): i for i, m in enumerate(M)}
    A = []
    for t, m in donnees.joindre(td, M):
        i = idx.get(id(m))
        if i in pred_sack and t['date'] < FIN_A:
            p, nc = pred_sack[i]
            A.append({'p_elo': p, 'p_pin': juste(t['psw'], t['psl']), 'connus': nc, 'circuit': m['circuit']})
    rapA = {}
    for nom, g in (('tous', A), ('joueurs connus (≥ 10 matchs)', [a for a in A if a['connus'] >= N_CONNU]),
                   ('ATP', [a for a in A if a['circuit'] == 'ATP']), ('WTA', [a for a in A if a['circuit'] == 'WTA'])):
        # le vainqueur réel est le joueur « A » de p_elo / p_pin : y = 1 ; on oriente au hasard pour la calibration
        rapA[nom] = {'stats_seules': bloc([(a['p_elo'], 1) for a in g]), 'stats_plus_marche': bloc([(a['p_pin'], 1) for a in g])}
    rapA['calibration_stats_seules'] = calibration([(a['p_elo'], 1) if k % 2 else (1 - a['p_elo'], 0) for k, a in enumerate(A)])
    rapA['calibration_marche'] = calibration([(a['p_pin'], 1) if k % 2 else (1 - a['p_pin'], 0) for k, a in enumerate(A)])

    # ---- B : nos matchs
    rapB = {}
    R = [b for b in B if b['gagnant'] in ('home', 'away')]
    for nom, g in (('tous', R), ('joueurs connus (≥ 10 matchs)', [b for b in R if b['connus'] >= N_CONNU])) + tuple(
            (c, [b for b in R if circuit(b['tournoi']) == c]) for c in ('ATP', 'CH', 'WTA', 'ITF')):
        rapB[nom] = {'stats_seules': bloc([(b['p_elo'], int(b['gagnant'] == 'home')) for b in g]),
                     'stats_plus_marche': bloc([(b['pin'], int(b['gagnant'] == 'home')) for b in g if b['pin']])}
    rapB['calibration_stats_seules'] = calibration([(b['p_elo'], int(b['gagnant'] == 'home')) for b in R])
    rapB['calibration_marche'] = calibration([(b['pin'], int(b['gagnant'] == 'home')) for b in R if b['pin']])
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

    rap = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'objectif': 'deviner le vainqueur et le score (pas battre Pinnacle)',
           'elo': 'FiveThirtyEight (Kovalchik 2016) : K = 250/(n+5)^0,4, ×1,1 en Grand Chelem, départ 1500 ; général + surface à parts égales ; aucun réglage',
           'sackmann_jusqu_au': fin_sack.isoformat(), 'nos_matchs': len(nous),
           'resultats_tennis_data_ajoutes': {'ajoutes': td_ok, 'doublons_ecartes': td_doublon, 'non_reconnus': td_inconnu},
           'A_atp_wta_2024_2026': dict(rapA, periode=f"{DEBUT_A} → {FIN_A}", matchs=len(A)),
           'B_nos_matchs': dict(rapB, periode=f"{nous[0]['date'] if nous else '—'} → {nous[-1]['date'] if nous else '—'}"),
           'duree_s': round(time.time() - t0)}
    with open(os.path.join(ICI, 'rapport_pronostic.json'), 'w', encoding='utf-8') as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    with open(os.path.join(ICI, 'elo_etat.json'), 'w', encoding='utf-8') as f:
        json.dump({'genere_le': rap['genere_le'], 'dernier_match': str(nous[-1]['date'] if nous else fin_sack),
                   'surfaces_tournois': table_surf, 'joueurs': elo.exporter(noms)}, f, ensure_ascii=False, separators=(',', ':'))
    print(json.dumps({k: rap[k] for k in ('A_atp_wta_2024_2026', 'B_nos_matchs')}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
