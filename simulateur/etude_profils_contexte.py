#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_profils_contexte.py — des effets PROPRES À CHAQUE JOUEUR, au-delà de l'Elo (04/11/2026, demande de Lucas, à partir
d'un site concurrent qui affiche « contre gaucher / droitier » et « en favori / en outsider »). Jugé SÉPARÉMENT sur
l'ATP, la WTA et le Challenger. (Le revers à une ou deux mains n'existe pas dans nos données : non testé.)

Pour chaque joueur, avec ses seuls matchs passés : résidu = résultat − probabilité Elo d'avant-match.
1. CONTRE GAUCHER : e_j = résidu moyen contre gauchers − résidu moyen contre droitiers, chaque moyenne rétrécie
   (somme / (n + 20)). Match contre un gaucher : le joueur reçoit son e_j. x = e_A·[B gaucher] − e_B·[A gaucher].
2. FAVORI / OUTSIDER : résidu moyen rétréci du joueur dans le RÔLE qu'il a dans ce match (favori de l'Elo ou
   outsider). x = r_A(rôle de A) − r_B(rôle de B).
Correction : z = logit p_elo + β·x, un paramètre par piste et par circuit. Aucune cote.

RÈGLE FIXÉE LE 04/11/2026, AVANT DE REGARDER LE RÉSULTAT, pour chaque piste et chaque circuit :
  β appris sur 2016–2022, jugé sur 2023 → 2026 (jamais vu) ;
  positif si, sur les matchs CONCERNÉS (x ≠ 0) jugés, au moins 300, la log loss baisse d'au moins 0,001 ET le gain
  reste positif sur tous les matchs jugés du circuit. Positif → modèle fantôme (deux semaines gagnantes). Sinon : rien.
Usage : python simulateur/etude_profils_contexte.py /tmp/sackmann .
"""
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_classement_serie as ECS  # noqa: E402  (apprendre : un paramètre)

COUPURE, DEBUT = dt.date(2023, 1, 1), dt.date(2016, 1, 1)
K = 20.0
MIN_CONCERNES, MARGE = 300, 0.001
SORTIE = os.path.join(ICI, 'rapport_profils_contexte.json')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def ll(z):
    return -math.log(min(max(_sg(z), 1e-9), 1 - 1e-9))


class Residus:
    def __init__(self):
        self.s = collections.defaultdict(lambda: [0.0, 0])      # (joueur, contexte) → [somme, n]

    def moy(self, j, ctx):
        s, n = self.s[(j, ctx)]
        return s / (n + K)

    def ajouter(self, j, ctx, r):
        e = self.s[(j, ctx)]
        e[0] += r
        e[1] += 1


def lignes(archive, racine, etat_final=False):
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
    M.sort(key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    main = {}
    for m in M:
        for n, h in ((m.get('nom_g'), m.get('main_g')), (m.get('nom_p'), m.get('main_p'))):
            if h in ('L', 'R') and k(n):
                main[k(n)] = h
    el, RS = E.Elo(), Residus()
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
        hg, hp = main.get(g), main.get(p)
        role_g, role_p = ('fav', 'out') if pe >= 0.5 else ('out', 'fav')
        if c in ('ATP', 'WTA', 'CH') and d >= DEBUT and not m.get('abandon') and el.matchs(g) >= 10 and el.matchs(p) >= 10:
            eL = lambda j: RS.moy(j, 'L') - RS.moy(j, 'R')
            x_main = (eL(g) if hp == 'L' else 0.0) - (eL(p) if hg == 'L' else 0.0)
            x_role = RS.moy(g, role_g) - RS.moy(p, role_p)
            x_tout = RS.moy(g, 'tout') - RS.moy(p, 'tout')
            rows.append({'d': d, 'c': c, 'z': _lg(pe), 'x_gaucher': x_main, 'x_role': x_role, 'x_tout': x_tout})
        if not m.get('abandon'):
            for j, adv_main, role, r in ((g, hp, role_g, 1 - pe), (p, hg, role_p, -(1 - pe))):
                if adv_main in ('L', 'R'):
                    RS.ajouter(j, adv_main, r)
                RS.ajouter(j, role, r)
                RS.ajouter(j, 'tout', r)
        attente.append((g, p, s, m.get('niveau') == 'G'))
    return (rows, RS) if etat_final else rows


def residus_actuels(archive, racine):
    """Pour le pronostic du jour : {joueur: {'fav': résidu moyen rétréci en favori, 'out': … en outsider}}, après tous
    les matchs connus (archive + feuilles). Clés unifiées comme l'Elo."""
    _, RS = lignes(archive, racine, etat_final=True)
    out = {}
    for (j, ctx), (s_, n) in RS.s.items():
        if ctx in ('fav', 'out') and n:
            out.setdefault(j, {})[ctx] = s_ / (n + K)
    return out


def variable_role(R, a, b, p_elo_a):
    """x = r_A(rôle de A) − r_B(rôle de B), rôles donnés par l'Elo (favori si p_elo ≥ 0,5)."""
    ra, rb = ('fav', 'out') if p_elo_a >= 0.5 else ('out', 'fav')
    return (R.get(a) or {}).get(ra, 0.0) - (R.get(b) or {}).get(rb, 0.0)


def juger(rows, cle):
    out = {}
    for c in ('ATP', 'WTA', 'CH'):
        R = [r for r in rows if r['c'] == c]
        av = [(r['z'], r[cle]) for r in R if r['d'] < COUPURE and r[cle]]
        ju = [r for r in R if r['d'] >= COUPURE]
        b = ECS.apprendre(av)
        cc = [r for r in ju if r[cle]]
        l0c = sum(ll(r['z']) for r in cc) / max(1, len(cc))
        l1c = sum(ll(r['z'] + b * r[cle]) for r in cc) / max(1, len(cc))
        g_tout = sum(ll(r['z']) - ll(r['z'] + b * r[cle]) for r in ju) / max(1, len(ju))
        out[c] = {'appris_concernes': len(av), 'juges': len(ju), 'juges_concernes': len(cc), 'beta': round(b, 4),
                  'log_loss_concernes_sans': round(l0c, 5), 'log_loss_concernes_avec': round(l1c, 5),
                  'gain_concernes': round(l0c - l1c, 5), 'gain_tous': round(g_tout, 6),
                  'positif': bool(len(cc) >= MIN_CONCERNES and (l0c - l1c) >= MARGE and g_tout > 0)}
    return out


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    rows = lignes(archive, racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("par piste et par circuit : β appris 2016–2022, jugé 2023 → ; positif si −0,001 sur ≥ 300 matchs "
                     "concernés et gain positif sur tous les matchs"),
           'contre_gaucher': juger(rows, 'x_gaucher'), 'favori_outsider': juger(rows, 'x_role'),
           # DESCRIPTIF, hors règle (ajouté après le résultat) : le même résidu SANS distinguer le rôle — le rôle
           # apporte-t-il quelque chose, ou est-ce un biais de l'Elo propre au joueur ?
           'comparaison_sans_role': juger(rows, 'x_tout')}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
