#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_documentation.py — l'algo est-il trop prudent sur les matchs PEU DOCUMENTÉS ? (05/11/2026, demande de Lucas)

« Documentation » d'un match = points de service du joueur le moins vu, cumulés avant le match (archive Sackmann
depuis 2012 + feuilles TennisApi après l'archive ; aucune pondération). Constat sur les 5 979 pronostics rejoués hors
échantillon (pronostics_hors_echantillon.jsonl.gz) : sous 500 points, les favoris gagnent nettement plus que
l'annoncé sur les deux périodes (72,2 % pour 64,3 % puis 78,8 % pour 68,8 % ; pente d'étalonnage 1,64 puis 1,68),
alors que les autres tranches sont justes (pente 0,9–1,2).

Correction : sur ces matchs, p' = σ(a · logit p) (a > 1 : on écarte de 50 %), a par circuit.
RÈGLE FIXÉE LE 05/11/2026, AVANT LE JUGEMENT PAR CIRCUIT : a appris sur août–septembre (≥ 100 matchs), jugé sur
octobre → (≥ 100 matchs) ; ADOPTÉ DIRECTEMENT sur un circuit si la log loss y baisse d'au moins 0,001 (décision de
Lucas). Retrait : fantomes_circuits.py, deux semaines de suite pires (« documentation_faible »).
Usage : python simulateur/etude_documentation.py /tmp/sackmann .
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
SEUIL_BALLES = 500
COUPURE = '2026-09-29'
MIN_N, MARGE = 100, 0.001
SORTIE = os.path.join(ICI, 'rapport_documentation.json')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def evenements(archive, racine):
    """[(jour ISO, clé joueur, points de service)] triés : archive (fin du tournoi) puis feuilles postérieures."""
    import donnees as DN
    import elo as E
    import feuilles as FE
    ev, fin = [], dt.date(2000, 1, 1)
    for m in DN.charger(archive, 2012):
        fin = max(fin, m['date'])
        if m.get('detail'):
            for side, nom in (('w', 'nom_g'), ('l', 'nom_p')):
                ev.append((m['fin'].isoformat(), E.cle(m[nom]), m['detail'][side][0]))
    for m in FE.charger(racine):
        if m.get('detail') and m['date'] > fin:
            for side, nom in (('w', 'nom_g'), ('l', 'nom_p')):
                ev.append((m['date'].isoformat(), E.cle(m[nom]), m['detail'][side][0]))
    ev.sort()
    return ev


class Compteur:
    """Points de service cumulés par joueur, avancé dans le temps (point-in-time)."""

    def __init__(self, ev):
        self.ev, self.i, self.n = ev, 0, collections.Counter()

    def au(self, jour):
        while self.i < len(self.ev) and self.ev[self.i][0] < jour:
            self.n[self.ev[self.i][1]] += self.ev[self.i][2]
            self.i += 1
        return self.n


def pente(R):
    a = 1.0
    for _ in range(40):
        g = sum((y - _sg(a * _lg(p))) * _lg(p) for p, y in R)
        h = sum(_sg(a * _lg(p)) * (1 - _sg(a * _lg(p))) * _lg(p) ** 2 for p, y in R)
        a += g / max(h, 1e-9)
    return a


def ll(R, a=1.0):
    return sum(-math.log(max(_sg(a * _lg(p)) if y else 1 - _sg(a * _lg(p)), 1e-9)) for p, y in R) / max(1, len(R))


def main(argv):
    import elo as E
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    L = [json.loads(l) for l in gzip.open(os.path.join(ICI, 'pronostics_hors_echantillon.jsonl.gz'), 'rt', encoding='utf-8')]
    info = {}
    import glob
    for f in glob.glob(os.path.join(racine, 'feuilles', '*.jsonl.gz')):
        for l in gzip.open(f, 'rt', encoding='utf-8'):
            e = json.loads(l)
            info[e['id']] = (E.cle(e['home']['nom']), E.cle(e['away']['nom']))
    Q = sorted([x for x in L if x['id'] in info and x.get('p_algo') is not None and x.get('gagnant') in ('home', 'away')],
               key=lambda x: x['jour'])
    C = Compteur(evenements(archive, racine))
    rows = []
    for x in Q:
        n = C.au(x['jour'])
        h, a = info[x['id']]
        if min(n[h], n[a]) < SEUIL_BALLES:
            rows.append((x['jour'], x['circuit'], float(x['p_algo']), int(x['gagnant'] == 'home')))
    out = {}
    for c in ('ATP', 'WTA', 'CH'):
        A = [(p, y) for j, cc, p, y in rows if cc == c and j < COUPURE]
        J = [(p, y) for j, cc, p, y in rows if cc == c and j >= COUPURE]
        if len(A) < MIN_N or len(J) < MIN_N:
            out[c] = {'appris': len(A), 'juges': len(J), 'adopte': False, 'raison': 'trop peu de matchs peu documentés'}
            continue
        a = pente(A)
        gain = ll(J) - ll(J, a)
        out[c] = {'appris': len(A), 'juges': len(J), 'pente': round(a, 3), 'log_loss_sans': round(ll(J), 5),
                  'log_loss_avec': round(ll(J, a), 5), 'gain': round(gain, 5), 'adopte': bool(gain >= MARGE and a > 1)}
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'seuil_balles': SEUIL_BALLES,
           'regle': "a appris août–sept (≥ 100), jugé oct → (≥ 100) ; adopté directement si −0,001 de log loss",
           'circuits': out}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
