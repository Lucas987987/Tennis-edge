#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_signaux_combines.py — les quatre signaux positifs de l'archive appris ENSEMBLE (04/11/2026, décision de Lucas :
les appliquer directement à l'algo plutôt qu'attendre deux semaines de fantôme). Chacun a été mesuré seul contre l'Elo ;
ils se recoupent (un vétéran qui revient de blessure et change de surface…) : les additionner tels quels compterait
deux fois. Ici, une seule correction à 6 paramètres par circuit :
    z = logit p_elo + β_surface·x_surface + β_abs_court·x_court + β_abs_long·x_long
                    + β_vieux·x_vieux + β_jeune·x_jeune + β_role·x_role
(définitions : etude_changement_surface, etude_retour_absence, etude_age, etude_profils_contexte). Aucune cote.

RÈGLE FIXÉE LE 04/11/2026, AVANT DE REGARDER LE RÉSULTAT, pour chaque circuit :
  β appris ENSEMBLE sur 2016–2022, jugé sur 2023 → 2026 (jamais vu), sur tous les matchs ;
  ADOPTÉ DIRECTEMENT sur un circuit si la log loss du vainqueur y baisse d'au moins 0,001 sur au moins 1 000 matchs ;
  les β combinés remplacent alors les β séparés dans le pronostic du jour (signaux appliqués sur ce circuit).
  RETRAIT : fantomes_circuits.py suit en direct « avec contre sans » ; deux semaines de suite sans gain → retiré.
Usage : python simulateur/etude_signaux_combines.py /tmp/sackmann .
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
import etude_profils_contexte as EPC  # noqa: E402
import etude_retour_absence as ERA  # noqa: E402

COUPURE, DEBUT = dt.date(2023, 1, 1), dt.date(2016, 1, 1)
MIN_JUGES, MARGE = 1000, 0.001
NOMS = ('changement_surface', 'retour_absence_court', 'retour_absence_long', 'age_vieux', 'age_jeune', 'favori_outsider')
SORTIE = os.path.join(ICI, 'rapport_signaux_combines.json')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def ll(z):
    return -math.log(min(max(_sg(z), 1e-9), 1 - 1e-9))


def apprendre(R, k=6, ridge=1.0, iterations=40):
    """Régression logistique décalée (vainqueur = A) : Newton avec ridge, k paramètres."""
    b = [0.0] * k
    for _ in range(iterations):
        g = [ridge * v for v in b]
        H = [[ridge if i == j else 0.0 for j in range(k)] for i in range(k)]
        for z, x in R:
            q = _sg(z + sum(bi * xi for bi, xi in zip(b, x)))
            for i in range(k):
                if x[i]:
                    g[i] += (q - 1) * x[i]
                    w = q * (1 - q) * x[i]
                    for j in range(k):
                        if x[j]:
                            H[i][j] += w * x[j]
        A = [row[:] + [g[i]] for i, row in enumerate(H)]
        for col in range(k):                                   # élimination de Gauss
            piv = max(range(col, k), key=lambda r: abs(A[r][col]))
            A[col], A[piv] = A[piv], A[col]
            for r in range(k):
                if r != col and abs(A[col][col]) > 1e-12:
                    f = A[r][col] / A[col][col]
                    A[r] = [a - f * c for a, c in zip(A[r], A[col])]
        d = [A[i][k] / A[i][i] if abs(A[i][i]) > 1e-12 else 0.0 for i in range(k)]
        b = [bi - di for bi, di in zip(b, d)]
        if max(abs(v) for v in d) < 1e-9:
            break
    return b


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
        role_g, role_p = ('fav', 'out') if pe >= 0.5 else ('out', 'fav')
        if c in ('ATP', 'WTA', 'CH') and d >= DEBUT and not m.get('abandon') and el.matchs(g) >= 10 and el.matchs(p) >= 10:
            xs = su.nouveau(g, d, s) - su.nouveau(p, d, s)
            xa = ERA.variables(rt.etat(g, d), rt.etat(p, d))
            xg = EA.variables(EA.age_au(naiss, g, d), EA.age_au(naiss, p, d)) or (0.0, 0.0)
            xr = RS.moy(g, role_g) - RS.moy(p, role_p)
            rows.append({'d': d, 'c': c, 'z': _lg(pe), 'x': (float(xs), xa[0], xa[1], xg[0], xg[1], xr)})
        su.jouer(g, d, s)
        su.jouer(p, d, s)
        rt.jouer(g, d)
        rt.jouer(p, d)
        if not m.get('abandon'):
            RS.ajouter(g, role_g, 1 - pe)
            RS.ajouter(p, role_p, -(1 - pe))
        attente.append((g, p, s, m.get('niveau') == 'G'))
    return rows


def juger(rows):
    out = {}
    for c in ('ATP', 'WTA', 'CH'):
        R = [r for r in rows if r['c'] == c]
        av = [(r['z'], r['x']) for r in R if r['d'] < COUPURE]
        ju = [r for r in R if r['d'] >= COUPURE]
        b = apprendre(av)
        cor = lambda r: r['z'] + sum(bi * xi for bi, xi in zip(b, r['x']))
        l0 = sum(ll(r['z']) for r in ju) / max(1, len(ju))
        l1 = sum(ll(cor(r)) for r in ju) / max(1, len(ju))
        gains_seuls = {}
        for i, nom in enumerate(NOMS):                         # chaque signal retiré du modèle combiné : sa part
            b_i = [v if j != i else 0.0 for j, v in enumerate(b)]
            l_i = sum(ll(r['z'] + sum(bj * xj for bj, xj in zip(b_i, r['x']))) for r in ju) / max(1, len(ju))
            gains_seuls[nom] = round(l_i - l1, 5)
        out[c] = {'appris': len(av), 'juges': len(ju), 'betas': {n: round(v, 4) for n, v in zip(NOMS, b)},
                  'log_loss_sans': round(l0, 5), 'log_loss_avec': round(l1, 5), 'gain': round(l0 - l1, 5),
                  'perte_si_on_retire': gains_seuls,
                  'adopte': bool(len(ju) >= MIN_JUGES and (l0 - l1) >= MARGE)}
    return out


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("β appris ensemble 2016–2022, jugé 2023 → ; adopté directement sur un circuit si −0,001 de log loss "
                     "sur ≥ 1 000 matchs ; retiré après deux semaines de suite sans gain en direct"),
           'circuits': juger(lignes(archive, racine))}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
