#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_classement_serie.py — deux pistes jugées SÉPARÉMENT, circuit par circuit (04/11/2026, demande de Lucas) :

1. ÉVOLUTION DU CLASSEMENT : un joueur qui monte (ou chute) au classement est-il mieux (moins bien) que son Elo ?
   tendance = ln(classement il y a 3 mois / classement actuel)   (> 0 : il monte ; 100e → 50e = 20e → 10e)
   classements publiés à la date de chaque tournoi (archive Sackmann), le dernier connu à la date voulue.
2. SÉRIE DES 10 DERNIERS MATCHS : un joueur qui gagne plus que l'Elo ne le prévoyait continue-t-il ?
   série = Σ (résultat − probabilité Elo d'avant-match) sur ses 10 derniers matchs (ITF compris, comme donnée).
Pour chacune : x = valeur_A − valeur_B ; correction z = logit p_elo + β·x (un paramètre par circuit). Aucune cote.

RÈGLE FIXÉE LE 04/11/2026, AVANT DE REGARDER LE RÉSULTAT, pour chaque piste et chaque circuit :
  β appris sur 2016–2022, jugé sur 2023 → 2026 (jamais vu), sur les matchs où la variable existe pour les deux joueurs ;
  positif si la log loss du vainqueur baisse d'au moins 0,001 sur au moins 1 000 matchs jugés.
  Positif → modèle fantôme sur les nouveaux matchs de ce circuit (deux semaines gagnantes pour l'adopter). Sinon : rien.
Usage : python simulateur/etude_classement_serie.py /tmp/sackmann .
"""
import bisect
import collections
import csv
import datetime as dt
import glob
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

COUPURE, DEBUT = dt.date(2023, 1, 1), dt.date(2016, 1, 1)
RECUL_J, SERIE_N = 91, 10
MIN_JUGES, MARGE = 1000, 0.001
SORTIE = os.path.join(ICI, 'rapport_classement_serie.json')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def ll(z):
    return -math.log(min(max(_sg(z), 1e-9), 1 - 1e-9))


def apprendre(R, ridge=1.0):
    b = 0.0
    for _ in range(50):
        g, h = ridge * b, ridge
        for z, x in R:
            q = _sg(z + b * x)
            g += (q - 1) * x
            h += q * (1 - q) * x * x
        d = g / h
        b -= d
        if abs(d) < 1e-10:
            break
    return b


def classements(archive, cle):
    """{joueur: ([jours], [classements])} triés — classement publié à la date de chaque tournoi joué."""
    C = collections.defaultdict(dict)
    for f in glob.glob(os.path.join(archive, '*', '*_matches_*.csv')):
        with open(f, encoding='utf-8', errors='replace', newline='') as fh:
            for r in csv.DictReader(fh):
                d = str(r.get('tourney_date') or '')
                if len(d) != 8:
                    continue
                try:
                    j = dt.date(int(d[:4]), int(d[4:6]), int(d[6:]))
                except ValueError:
                    continue
                for cote in ('winner', 'loser'):
                    try:
                        rk = int(float(r.get(f'{cote}_rank') or ''))
                    except ValueError:
                        continue
                    k = cle(r.get(f'{cote}_name'))
                    if k and rk > 0:
                        C[k][j] = rk
    return {k: (sorted(v), [v[j] for j in sorted(v)]) for k, v in C.items()}


def rang_au(C, k, jour):
    e = C.get(k)
    if not e:
        return None
    i = bisect.bisect_right(e[0], jour) - 1
    return e[1][i] if i >= 0 else None


def tendance(C, k, jour):
    """ln(classement il y a 3 mois / classement actuel) ; None si l'un manque (ou classement d'il y a 3 mois trop vieux)."""
    e = C.get(k)
    if not e:
        return None
    i = bisect.bisect_right(e[0], jour) - 1
    j = bisect.bisect_right(e[0], jour - dt.timedelta(days=RECUL_J)) - 1
    if i < 0 or j < 0 or (jour - e[0][j]).days > RECUL_J + 60 or (jour - e[0][i]).days > 60:
        return None
    return math.log(e[1][j] / e[1][i])


def lignes(archive, racine):
    import donnees as DN
    import elo as E
    import feuilles as FE
    M = DN.charger(archive, 2012)
    fin = max(m['date'] for m in M)
    M = M + [m for m in FE.charger(racine) if m['date'] > fin]
    try:
        with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
            alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    C = classements(archive, k)
    M.sort(key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    el, serie = E.Elo(), collections.defaultdict(lambda: collections.deque(maxlen=SERIE_N))
    jour, attente, rows = None, [], []
    for m in M:
        d = m['date']
        if d != jour:
            for g, p, s, gc in attente:
                el.maj(g, p, s, gc, None)
            attente, jour = [], d
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m['surface']
        if c in ('CH', 'ITF'):
            el.presenter(g, 1200.0)
            el.presenter(p, 1200.0)
        pe = el.proba(g, p, s)
        if c in ('ATP', 'WTA', 'CH') and d >= DEBUT and not m.get('abandon') and el.matchs(g) >= 10 and el.matchs(p) >= 10:
            tg, tp = tendance(C, g, d), tendance(C, p, d)
            sg_ = sum(serie[g]) if len(serie[g]) == SERIE_N else None
            sp_ = sum(serie[p]) if len(serie[p]) == SERIE_N else None
            rows.append({'d': d, 'c': c, 'z': _lg(pe),
                         'x_classement': (tg - tp) if tg is not None and tp is not None else None,
                         'x_serie': (sg_ - sp_) if sg_ is not None and sp_ is not None else None})
        if not m.get('abandon'):
            serie[g].append(1 - pe)
            serie[p].append(-(1 - pe))          # 0 − (1 − pe) : probabilité Elo du perdant = 1 − pe
        attente.append((g, p, s, m.get('niveau') == 'G'))
    return rows


def juger(rows, cle):
    out = {}
    for c in ('ATP', 'WTA', 'CH'):
        R = [r for r in rows if r['c'] == c and r[cle] is not None]
        av = [(r['z'], r[cle]) for r in R if r['d'] < COUPURE]
        ju = [r for r in R if r['d'] >= COUPURE]
        b = apprendre(av)
        l0 = sum(ll(r['z']) for r in ju) / max(1, len(ju))
        l1 = sum(ll(r['z'] + b * r[cle]) for r in ju) / max(1, len(ju))
        # descriptif : quart des matchs où l'écart est le plus fort ; le joueur « en avance » (x > 0 pour lui)
        S = sorted(ju, key=lambda r: abs(r[cle]))
        haut = S[3 * len(S) // 4:]
        ann = [(_sg(r['z']) if r[cle] > 0 else 1 - _sg(r['z']), int(r[cle] > 0)) for r in haut]
        pc = lambda L, i: round(100 * sum(t[i] for t in L) / max(1, len(L)), 1)
        out[c] = {'appris': len(av), 'juges': len(ju), 'beta': round(b, 4), 'log_loss_sans': round(l0, 5),
                  'log_loss_avec': round(l1, 5), 'gain': round(l0 - l1, 5),
                  'positif': bool(len(ju) >= MIN_JUGES and (l0 - l1) >= MARGE),
                  'quart_le_plus_marque': {'matchs': len(ann), 'elo_pct': pc(ann, 0), 'reel_pct': pc(ann, 1)}}
    return out


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    rows = lignes(archive, racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("par piste et par circuit : β appris 2016–2022, jugé 2023 → ; positif si −0,001 de log loss sur "
                     "≥ 1 000 matchs jugés"),
           'evolution_classement': {'definition': 'ln(classement il y a 3 mois / classement actuel), écart entre les joueurs',
                                    'circuits': juger(rows, 'x_classement')},
           'serie_10_matchs': {'definition': 'Σ (résultat − probabilité Elo) sur les 10 derniers matchs, écart entre les joueurs',
                               'circuits': juger(rows, 'x_serie')}}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
