#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_pistes_tournoi.py — deux pistes de la loupe Pinnacle (04/11/2026, demande de Lucas), jugées circuit par circuit :

1. MONTÉE DES PETITS TOURNOIS : part de ses 20 derniers matchs joués en ITF ou en Challenger (en ATP, ces joueurs étaient
   annoncés 29,8 % par l'Elo et gagnaient 34,2 %). x_bas = part_A − part_B.
2. PARCOURS DANS LE TOURNOI : matchs déjà gagnés dans CE tournoi, qualifications comprises (plafonné à 6) — adaptation
   au lieu, aux balles, aux conditions (en ATP, 27,7 % annoncés, 34,0 % réels). x_tournoi = n_A − n_B.

RÈGLE FIXÉE LE 04/11/2026, AVANT DE REGARDER LE RÉSULTAT, pour chaque piste et chaque circuit :
  a) SEULE contre l'Elo : β appris sur 2016–2022, jugé sur 2023 → ; positive si −0,001 de log loss sur les matchs
     concernés (x ≠ 0, au moins 300) ET gain positif sur tous les matchs ;
  b) AJOUTÉE au modèle combiné en place (etude_signaux_combines.py, 6 paramètres) : β ré-appris ENSEMBLE (7 paramètres)
     sur 2016–2022 ; ajoutée à l'algo sur ce circuit seulement si le combiné gagne ENCORE au moins 0,001 sur tous les
     matchs jugés 2023 → (sinon elle n'apporte rien de plus que les signaux déjà en place).
  Les deux conditions a) et b) sont exigées. Retrait : même règle que les signaux combinés.
Usage : python simulateur/etude_pistes_tournoi.py /tmp/sackmann .
"""
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_age as EA  # noqa: E402
import etude_changement_surface as ECS  # noqa: E402
import etude_classement_serie as ECL  # noqa: E402  (apprendre : un paramètre)
import etude_profils_contexte as EPC  # noqa: E402
import etude_retour_absence as ERA  # noqa: E402
import etude_signaux_combines as ESC  # noqa: E402

COUPURE, DEBUT = dt.date(2023, 1, 1), dt.date(2016, 1, 1)
NIVEAU_N, PLAFOND_TOURNOI = 20, 6
MIN_CONCERNES, MARGE = 300, 0.001
SORTIE = os.path.join(ICI, 'rapport_pistes_tournoi.json')
PISTES = ('montee_petits_tournois', 'parcours_tournoi')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def ll(z):
    return ESC.ll(z)


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
    naiss = EA.naissances(archive, k)
    M.sort(key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    el, su, rt, RS = E.Elo(), ECS.Suivi(), ERA.Retours(), EPC.Residus()
    niv = collections.defaultdict(lambda: collections.deque(maxlen=NIVEAU_N))
    tour_n = {}
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
        tid = m.get('tournoi_id') or m.get('tournoi')
        role_g, role_p = ('fav', 'out') if pe >= 0.5 else ('out', 'fav')
        if c in ('ATP', 'WTA', 'CH') and d >= DEBUT and not m.get('abandon') and el.matchs(g) >= 10 and el.matchs(p) >= 10:
            xs = su.nouveau(g, d, s) - su.nouveau(p, d, s)
            xa = ERA.variables(rt.etat(g, d), rt.etat(p, d))
            xg = EA.variables(EA.age_au(naiss, g, d), EA.age_au(naiss, p, d)) or (0.0, 0.0)
            xr = RS.moy(g, role_g) - RS.moy(p, role_p)
            part = lambda j: (sum(niv[j]) / len(niv[j])) if len(niv[j]) >= 5 else 0.0
            x_bas = part(g) - part(p)
            x_tour = min(tour_n.get((g, tid), 0), PLAFOND_TOURNOI) - min(tour_n.get((p, tid), 0), PLAFOND_TOURNOI)
            rows.append({'d': d, 'c': c, 'z': _lg(pe), 'x6': (float(xs), xa[0], xa[1], xg[0], xg[1], xr),
                         'montee_petits_tournois': x_bas, 'parcours_tournoi': float(x_tour)})
        su.jouer(g, d, s)
        su.jouer(p, d, s)
        rt.jouer(g, d)
        rt.jouer(p, d)
        for j in (g, p):
            niv[j].append(1.0 if c in ('CH', 'ITF') else 0.0)
        tour_n[(g, tid)] = tour_n.get((g, tid), 0) + 1        # le vainqueur continue ; le perdant est éliminé
        if not m.get('abandon'):
            RS.ajouter(g, role_g, 1 - pe)
            RS.ajouter(p, role_p, -(1 - pe))
        attente.append((g, p, s, m.get('niveau') == 'G'))
    return rows


def juger(rows):
    out = {}
    for c in ('ATP', 'WTA', 'CH'):
        R = [r for r in rows if r['c'] == c]
        av = [r for r in R if r['d'] < COUPURE]
        ju = [r for r in R if r['d'] >= COUPURE]
        b6 = ESC.apprendre([(r['z'], r['x6']) for r in av])
        z6 = lambda r: r['z'] + sum(bi * xi for bi, xi in zip(b6, r['x6']))
        l6 = sum(ll(z6(r)) for r in ju) / max(1, len(ju))
        bloc = {'juges': len(ju), 'log_loss_combine_6': round(l6, 5)}
        for piste in PISTES:
            # a) seule contre l'Elo
            b1 = ECL.apprendre([(r['z'], r[piste]) for r in av if r[piste]])
            cc = [r for r in ju if r[piste]]
            l0c = sum(ll(r['z']) for r in cc) / max(1, len(cc))
            l1c = sum(ll(r['z'] + b1 * r[piste]) for r in cc) / max(1, len(cc))
            g_tout = sum(ll(r['z']) - ll(r['z'] + b1 * r[piste]) for r in ju) / max(1, len(ju))
            seule = len(cc) >= MIN_CONCERNES and (l0c - l1c) >= MARGE and g_tout > 0
            # b) ajoutée au combiné (7 paramètres appris ensemble)
            b7 = ESC.apprendre([(r['z'], r['x6'] + (r[piste],)) for r in av], k=7)
            l7 = sum(ll(r['z'] + sum(bi * xi for bi, xi in zip(b7, r['x6'] + (r[piste],)))) for r in ju) / max(1, len(ju))
            ajout = l6 - l7
            bloc[piste] = {'seule': {'beta': round(b1, 4), 'concernes': len(cc), 'gain_concernes': round(l0c - l1c, 5),
                                     'gain_tous': round(g_tout, 6), 'positive': bool(seule)},
                           'ajoutee_au_combine': {'betas_7': [round(v, 4) for v in b7], 'gain_en_plus': round(ajout, 5),
                                                  'suffisant': bool(ajout >= MARGE)},
                           'adoptee': bool(seule and ajout >= MARGE)}
        out[c] = bloc
    return out


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("par piste et par circuit : seule, −0,001 sur ≥ 300 matchs concernés et gain positif sur tous ; ET "
                     "ajoutée au combiné, encore −0,001 sur tous les matchs jugés 2023 →"),
           'circuits': juger(lignes(archive, racine))}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
