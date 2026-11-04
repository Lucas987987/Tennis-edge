#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_age.py — l'Elo suit-il le déclin des joueurs âgés et la progression des jeunes ? (04/11/2026, demande de Lucas,
piste 1 du bilan des notes : en ATP, favoris à plus de 400 matchs annoncés 68,4 %, gagnants 57,4 % sur 68 matchs.)
Jugé SÉPARÉMENT sur l'ATP, la WTA et le Challenger.

L'Elo est une moyenne des résultats passés : il retarde quand un joueur décline (âge) ou progresse vite (jeunesse).
Âge le jour du match, tiré de la date de naissance estimée dans l'archive Sackmann (âge publié au premier match).
Variables (A, B les deux joueurs) :
    vieux   = max(0, âge − 30)     jeune = max(0, 23 − âge)       (en années)
    x_vieux = vieux_A − vieux_B    x_jeune = jeune_A − jeune_B
Correction : z = logit p_elo + β_vieux·x_vieux + β_jeune·x_jeune (deux paramètres par circuit). Aucune cote.

RÈGLE FIXÉE LE 04/11/2026, AVANT DE REGARDER LE RÉSULTAT, pour chaque circuit :
  β appris sur 2016–2022, jugé sur 2023 → 2026 (jamais vu), sur TOUS les matchs dont les deux âges sont connus
  (l'âge touche presque tous les matchs : pas de sous-ensemble « concerné ») ;
  positif si la log loss du vainqueur baisse d'au moins 0,001 sur au moins 1 000 matchs jugés.
  Positif → modèle fantôme « âge » sur les nouveaux matchs de ce circuit, adopté seulement après deux semaines
  gagnantes (fantomes_circuits.py). Sinon : rien ne change.
Usage : python simulateur/etude_age.py /tmp/sackmann .
"""
import csv
import datetime as dt
import glob
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_retour_absence as ERA  # noqa: E402  (apprendre : Newton à deux paramètres)

COUPURE, DEBUT = dt.date(2023, 1, 1), dt.date(2016, 1, 1)
VIEUX, JEUNE = 30.0, 23.0
MIN_JUGES, MARGE = 1000, 0.001
SORTIE = os.path.join(ICI, 'rapport_age.json')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def ll(z):
    return -math.log(min(max(_sg(z), 1e-9), 1 - 1e-9))


def naissances(archive, cle=None):
    """{clé joueur: date de naissance estimée} — médiane de (date du tournoi − âge publié) sur ses matchs."""
    import elo as E
    cle = cle or E.cle
    est = {}
    for f in glob.glob(os.path.join(archive, '*', '*_matches_*.csv')):
        with open(f, encoding='utf-8', errors='replace', newline='') as fh:
            for r in csv.DictReader(fh):
                d = str(r.get('tourney_date') or '')
                if len(d) != 8:
                    continue
                try:
                    j0 = dt.date(int(d[:4]), int(d[4:6]), int(d[6:])).toordinal()
                except ValueError:
                    continue
                for cote in ('winner', 'loser'):
                    try:
                        age = float(r.get(f'{cote}_age') or '')
                    except ValueError:
                        continue
                    k = cle(r.get(f'{cote}_name'))
                    if k and 13 < age < 50:
                        L = est.setdefault(k, [])
                        if len(L) < 40:
                            L.append(j0 - age * 365.25)
    return {k: dt.date.fromordinal(int(sorted(v)[len(v) // 2])) for k, v in est.items()}


def age_au(naiss, k, jour):
    b = naiss.get(k)
    return (jour - b).days / 365.25 if b else None


def variables(age_a, age_b):
    if age_a is None or age_b is None:
        return None
    v = lambda a: max(0.0, a - VIEUX)
    j = lambda a: max(0.0, JEUNE - a)
    return (v(age_a) - v(age_b), j(age_a) - j(age_b))


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
    naiss = naissances(archive, k)
    M.sort(key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    el, jour, attente, rows = E.Elo(), None, [], []
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
        x = variables(age_au(naiss, g, d), age_au(naiss, p, d))
        if (x is not None and c in ('ATP', 'WTA', 'CH') and d >= DEBUT and not m.get('abandon')
                and el.matchs(g) >= 10 and el.matchs(p) >= 10):
            rows.append({'d': d, 'c': c, 'z': _lg(el.proba(g, p, s)), 'x': x, 'n': (el.matchs(g), el.matchs(p))})
        attente.append((g, p, s, m.get('niveau') == 'G'))
    return rows


def juger(rows):
    out = {}
    for c in ('ATP', 'WTA', 'CH'):
        R = [r for r in rows if r['c'] == c]
        av = [(r['z'], r['x']) for r in R if r['d'] < COUPURE]
        ju = [r for r in R if r['d'] >= COUPURE]
        b = ERA.apprendre(av)
        cor = lambda r: r['z'] + b[0] * r['x'][0] + b[1] * r['x'][1]
        l0 = sum(ll(r['z']) for r in ju) / max(1, len(ju))
        l1 = sum(ll(cor(r)) for r in ju) / max(1, len(ju))
        # descriptif : le joueur le plus âgé (écart ≥ 4 ans, plus de 30 ans), annoncé par l'Elo contre réel (A = vainqueur)
        vx = [r for r in ju if abs(r['x'][0]) >= 4]
        ann = [(_sg(r['z']) if r['x'][0] > 0 else 1 - _sg(r['z']), int(r['x'][0] > 0)) for r in vx]
        jx = [r for r in ju if abs(r['x'][1]) >= 2]
        annj = [(_sg(r['z']) if r['x'][1] > 0 else 1 - _sg(r['z']), int(r['x'][1] > 0)) for r in jx]
        pc = lambda L, i: round(100 * sum(t[i] for t in L) / max(1, len(L)), 1)
        positif = len(ju) >= MIN_JUGES and (l0 - l1) >= MARGE
        out[c] = {'appris': len(av), 'juges': len(ju), 'beta_vieux_par_an': round(b[0], 4), 'beta_jeune_par_an': round(b[1], 4),
                  'log_loss_sans': round(l0, 5), 'log_loss_avec': round(l1, 5), 'gain': round(l0 - l1, 5),
                  'positif': bool(positif),
                  'plus_age_de_4_ans_au_dela_de_30': {'matchs': len(ann), 'elo_pct': pc(ann, 0), 'reel_pct': pc(ann, 1)},
                  'plus_jeune_de_2_ans_sous_23_ans': {'matchs': len(annj), 'elo_pct': pc(annj, 0), 'reel_pct': pc(annj, 1)}}
    return out


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    rows = lignes(archive, racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'definition': f'vieux = années au-delà de {VIEUX:g} ans, jeune = années sous {JEUNE:g} ans ; écart entre les deux joueurs',
           'regle': "β appris 2016–2022, jugé 2023 → ; positif si −0,001 de log loss sur ≥ 1 000 matchs jugés, par circuit",
           'circuits': juger(rows)}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
