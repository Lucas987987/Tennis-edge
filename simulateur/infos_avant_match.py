#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
infos_avant_match.py — trois repères DESCRIPTIFS par match du jour (06/11/2026, paquet 210, demande de Lucas après
Sofascore) : séries en cours, face-à-face, et RÉUSSITE PAR RAPPORT AUX CHANCES D'AVANT MATCH.

Archive Sackmann (2016 →) + feuilles TennisApi collectées depuis, rejouées dans l'ordre :
  — SÉRIE : victoires (ou défaites) de suite, et sets gagnés (ou perdus) de suite, matchs joués (forfaits exclus) ;
  — FACE-À-FACE : bilan de toutes les rencontres connues et les 5 dernières (date, tournoi, vainqueur, score) ;
  — RÉUSSITE : sur ses 40 derniers matchs des 12 derniers mois (abandons et forfaits exclus), victoires RÉELLES contre
    victoires ATTENDUES, l'attendu étant la probabilité Elo d'avant chaque match (le cœur du % de l'algo, point-in-time).
  — APRÈS LE 1er SET (11/11/2026, paquet 221) : sur ses matchs des 24 derniers mois (abandons exclus), part des
    matchs gagnés quand il a GAGNÉ le 1er set, et quand il l'a PERDU (remontées), à côté de la moyenne de son
    circuit sur la même période. Descriptif (l'étude du set décisif du 05/11 : aucun apport au-delà de l'Elo).
    « +3,1 » = 3 victoires de plus que ses chances ne le laissaient prévoir. Descriptif : les études du 05/11/2026
    (set décisif, tie-breaks) ont montré que ce genre d'écart ne prédit pas le match suivant — rien n'entre dans le %.
Sortie : simulateur/infos_avant_match.json {uid: {'home': {...}, 'away': {...}, 'face_a_face': {...}}}, fusionnée
dans algo/donnees.json par vitrine.py.
Usage : python simulateur/infos_avant_match.py /tmp/sackmann [racine]
"""
import collections
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

SORTIE = os.path.join(ICI, 'infos_avant_match.json')
REUSSITE_N, REUSSITE_J = 40, 365
SET1_J, SET1_MIN = 730, 8
H2H_N = 5


def score_txt(sets):
    return ' '.join(f'{a}-{b}' for a, b in sets or [])


def rejouer(tout, alias=None):
    """Historique par joueur [(date, gagné, attendu|None, sets gagnés, sets perdus, adversaire, abandon)] et
    face-à-face {(a, b) trié: [(date, tournoi, vainqueur, score)]}."""
    import elo as E
    alias = alias or {}
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None   # noqa: E731
    el, jour, attente = E.Elo(), None, []
    H = collections.defaultdict(list)
    F = collections.defaultdict(list)
    for m in tout:
        d = m['date']
        if d != jour:
            for g, p, s, gc in attente:
                el.maj(g, p, s, gc, None)
            attente, jour = [], d
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        s = m.get('surface')
        if m['circuit'] in ('CH', 'ITF'):
            el.presenter(g, 1200.0)
            el.presenter(p, 1200.0)
        sets = m.get('sets') or []
        if sets:                                              # forfait (aucun jeu joué) : ni série ni réussite
            ab = bool(m.get('abandon')) or not m.get('complet', True)
            pe = None if ab else min(max(el.proba(g, p, s), 0.01), 0.99)
            sg = sum(1 for a, b in sets if a > b)
            sp = len(sets) - sg
            seq = tuple(1 if a > b else 0 for a, b in sets)       # sets du vainqueur, dans l'ordre
            H[g].append((d, 1, pe, sg, sp, p, ab, seq, m['circuit']))
            H[p].append((d, 0, None if pe is None else 1 - pe, sp, sg, g, ab, tuple(1 - x for x in seq), m['circuit']))
            F[tuple(sorted((g, p)))].append((d, m.get('tournoi'), g, score_txt(sets) + (' ab.' if ab else '')))
        attente.append((g, p, s, m.get('niveau') == 'G'))
    return H, F, k


def sets_de_suite(L):
    """('gagnes' | 'perdus', n) : sets gagnés (ou perdus) de suite, du plus récent au plus ancien, dans l'ordre réel."""
    if not L:
        return None
    sens = L[-1][1]
    n = 0
    for e in reversed(L):
        for x in reversed(e[7]):
            if x != sens:
                return ('gagnes' if sens else 'perdus'), n
            n += 1
    return ('gagnes' if sens else 'perdus'), n


def reussite(L, aujourdhui):
    R = [e for e in L if e[2] is not None and (aujourdhui - e[0]).days <= REUSSITE_J][-REUSSITE_N:]
    if len(R) < 10:
        return None
    v = sum(e[1] for e in R)
    att = sum(e[2] for e in R)
    return {'matchs': len(R), 'victoires': v, 'attendu': round(att, 1), 'ecart': round(v - att, 1)}


def apres_set1(L, aujourdhui):
    """{'gagne': [matchs gagnés, matchs], 'perdu': [...]} après avoir gagné / perdu le 1er set, 24 derniers mois."""
    out = {'gagne': [0, 0], 'perdu': [0, 0]}
    for e in L:
        if e[6] or not e[7] or (aujourdhui - e[0]).days > SET1_J:
            continue
        c = out['gagne' if e[7][0] == 1 else 'perdu']
        c[0] += e[1]
        c[1] += 1
    return out


def moyennes_set1(H, aujourdhui):
    """Moyenne par circuit (ATP, WTA, CH) : un match compté une fois, du côté du joueur qui a gagné le 1er set."""
    acc = collections.defaultdict(lambda: [0, 0])
    for L in H.values():
        for e in L:
            if e[6] or not e[7] or e[7][0] != 1 or (aujourdhui - e[0]).days > SET1_J or len(e) < 9:
                continue
            acc[e[8]][0] += e[1]
            acc[e[8]][1] += 1
    return {c: round(v / n, 4) for c, (v, n) in acc.items() if c in ('ATP', 'WTA', 'CH') and n >= 100}


def fiche_joueur(H, j, aujourdhui):
    L = H.get(j) or []
    if not L:
        return None
    der = L[-1][1]
    n = 0
    for e in reversed(L):
        if e[1] != der:
            break
        n += 1
    sens, ns = sets_de_suite(L)
    return {'serie': {'type': 'victoires' if der else 'defaites', 'n': n, 'sets': sens, 'sets_n': ns},
            'reussite': reussite(L, aujourdhui), 'apres_set1': apres_set1(L, aujourdhui)}


def face_a_face(F, a, b):
    R = F.get(tuple(sorted((a, b)))) or []
    if not R:
        return None
    va = sum(1 for e in R if e[2] == a)
    return {'rencontres': len(R), 'home': va, 'away': len(R) - va,
            'derniers': [{'date': e[0].isoformat(), 'tournoi': e[1], 'vainqueur': 'home' if e[2] == a else 'away',
                          'score': e[3]} for e in reversed(R[-H2H_N:])]}


def construire(matchs, H, F, k, aujourdhui):
    out = {}
    moy = moyennes_set1(H, aujourdhui)
    for m in matchs:
        a, b = k(m.get('home')), k(m.get('away'))
        if not a or not b or not m.get('uid'):
            continue
        out[m['uid']] = {'home': fiche_joueur(H, a, aujourdhui), 'away': fiche_joueur(H, b, aujourdhui),
                         'face_a_face': face_a_face(F, a, b)}
        c = m.get('circuit')
        if c in moy:            # 11/11/2026 (paquet 221) : P(gagner | 1er set gagné) moyenne du circuit ; perdu = 1 − ce chiffre
            out[m['uid']]['set1_circuit'] = {'circuit': c, 'gagne': moy[c], 'perdu': round(1 - moy[c], 4)}
    return out


def main(argv):
    archive = argv[1]
    racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    import donnees
    import elo as E
    import feuilles as FE
    M = donnees.charger(archive, 2016)
    fin_sack = max(x['date'] for x in M) if M else None
    Fe = [m for m in FE.charger(racine) if fin_sack is None or m['date'] > fin_sack]
    tout = sorted(M + Fe, key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    try:
        with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
            alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    H, F, k = rejouer(tout, alias)
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics.json'), encoding='utf-8') as f:
            matchs = json.load(f).get('matchs') or []
    except (OSError, ValueError):
        matchs = []
    doc = construire(matchs, H, F, k, dt.datetime.now(dt.timezone.utc).date())
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump({'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'matchs': doc},
                  f, ensure_ascii=False, separators=(',', ':'))
    print(f"{len(doc)} matchs · {len(H)} joueurs rejoués")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
