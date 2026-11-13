#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_styles_jeu.py — les styles de jeu (styles_jeu.py) prédisent-ils le vainqueur au-delà de l'Elo ? (13/11/2026,
paquet 252)

Matchs ATP et WTA de l'archive Sackmann où les DEUX joueurs ont un style de jeu à la date du match (au moins 10 matchs
relevés coup par coup dans les 3 ans d'avant). Base : Elo réglé comme la production, mis à jour après chaque match.

DEUX VARIABLES, ÉCRITES LE 13/11/2026 AVANT TOUT CALCUL (style = la première étiquette, la plus marquée) :
  paire     un écart par paire de styles, appris sur 2018–2022 : t(a, b) = moyenne rétrécie (n + 20) du résultat moins
            l'Elo pour le style a contre le style b, rendue antisymétrique (t(a, b) − t(b, a)) / 2 ; x = t(style A, style B)
  joueur    effet propre au joueur (comme etude_profils_individuels.py) : son résidu contre ce style d'adversaire moins
            son résidu contre tous, rétrécis (n + 20), sur ses seuls matchs passés ; x = effet(A, style B) − effet(B, style A)
RÈGLE (celle du dépôt) : par variable et par circuit, β appris sur 2018–2022, jugé sur 2023 → juin 2026, sur les matchs
concernés (x ≠ 0) : RETENU si −0,001 de log loss sur au moins 1 000 matchs concernés ET β de même signe sur 2023 →.
Variable divisée par sa moyenne quadratique d'apprentissage, jamais centrée (paquet 250). Rien en production ici.

Usage : python simulateur/etude_styles_jeu.py /tmp/sackmann . /tmp/mcp
"""
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_profils_individuels as PI  # noqa: E402

SORTIE = os.path.join(ICI, 'rapport_styles_jeu.json')
DEBUT, COUPURE, FIN = dt.date(2018, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
CIRCUITS = ('ATP', 'WTA')
K = 20.0


def lignes(archive, racine, mcp):
    import coups_joueurs as CJ
    import donnees as DN
    import elo as E
    import styles_jeu as SJ
    with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
        alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None  # noqa: E731
    P = SJ.Profils(CJ.charger(mcp), k)
    el, bas = E.de_production(racine)
    RS, rows = PI.Residus(), []
    for m in sorted(DN.charger(archive, 2012), key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0))):
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s, d = m['circuit'], m['surface'], m['date']
        if bas and c in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        pe = el.proba(g, p, s)
        sg = sp = None
        if c in CIRCUITS and DEBUT <= d < FIN:
            sg, sp = P.style(g, d)[0], P.style(p, d)[0]
            sg, sp = (sg or [None])[0], (sp or [None])[0]
            if sg and sp and not m.get('abandon') and m.get('niveau') != 'D' and el.matchs(g) >= 10 and el.matchs(p) >= 10:
                eg, ep = RS.effet(g, sp), RS.effet(p, sg)
                rows.append({'d': d, 'c': c, 'z': PI._lg(pe), 'sg': sg, 'sp': sp, 'y': 1 - pe,
                             'joueur': (eg - ep) if eg is not None and ep is not None else 0.0})
        if not m.get('abandon') and c != 'ITF':
            RS.ajouter(g, 'tous', 1 - pe)
            RS.ajouter(p, 'tous', -(1 - pe))
            if sp:
                RS.ajouter(g, sp, 1 - pe)
            if sg:
                RS.ajouter(p, sg, -(1 - pe))
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    return rows


def table_paires(rows):
    """t(a, b) antisymétrique, apprise sur 2018–2022 (résultat − Elo, vu du vainqueur, rétréci)."""
    s, n = collections.Counter(), collections.Counter()
    for r in rows:
        if r['d'] < COUPURE:
            s[(r['sg'], r['sp'])] += r['y']
            n[(r['sg'], r['sp'])] += 1
            s[(r['sp'], r['sg'])] -= r['y']
            n[(r['sp'], r['sg'])] += 1
    m = {kk: s[kk] / (n[kk] + K) for kk in n}
    return {kk: (m.get(kk, 0.0) - m.get((kk[1], kk[0]), 0.0)) / 2 for kk in m}


def juger(rows, c, cle):
    import etude_outsiders as EO
    import etude_signaux_combines as ESC
    R = [r for r in rows if r['c'] == c and r[cle]]
    av, ju = [r for r in R if r['d'] < COUPURE], [r for r in R if r['d'] >= COUPURE]
    out = {'matchs_concernes': {'2018–2022': len(av), '2023 → juin 2026': len(ju)}}
    if len(av) < 200 or not ju:
        return dict(out, retenu=False, note='trop peu de matchs concernés')
    rms = math.sqrt(sum(r[cle] ** 2 for r in av) / len(av)) or 1.0
    b1 = ESC.apprendre([(r['z'], (r[cle] / rms,)) for r in av], k=1)[0]
    b2 = ESC.apprendre([(r['z'], (r[cle] / rms,)) for r in ju], k=1)[0]
    b = EO.bilan([r['z'] for r in ju], [r['z'] + b1 * r[cle] / rms for r in ju])
    ok = len(ju) >= PI.MIN_JUGES and b['gain'] >= PI.MARGE and b1 * b2 > 0
    return dict(out, beta_2018_2022=round(b1, 3), beta_2023=round(b2, 3), gain=b['gain'], erreur_type=b['erreur_type'],
                erreurs_types=b['erreurs_types'], retenu=bool(ok))


def main(argv):
    archive = argv[1] if len(argv) > 1 else '/tmp/sackmann'
    racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    mcp = argv[3] if len(argv) > 3 else '/tmp/mcp'
    rows = lignes(archive, racine, mcp)
    T = table_paires(rows)
    for r in rows:
        r['paire'] = T.get((r['sg'], r['sp']), 0.0)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 252, 'statut': 'etude',
           'regle': ("par variable (paire de styles, effet propre au joueur) et par circuit : β appris sur 2018–2022, jugé "
                     "sur 2023 → juin 2026 ; retenu si −0,001 de log loss sur au moins 1 000 matchs concernés et β de même "
                     "signe"),
           'matchs_avec_deux_styles': {c: sum(1 for r in rows if r['c'] == c) for c in CIRCUITS},
           'repartition': dict(collections.Counter(s for r in rows for s in (r['sg'], r['sp']))),
           'variables': {v: {c: juger(rows, c, v) for c in CIRCUITS} for v in ('paire', 'joueur')}}
    doc['retenus'] = [f"{v} · {c}" for v, d in doc['variables'].items() for c, x in d.items() if x.get('retenu')]
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps({x: doc[x] for x in ('matchs_avec_deux_styles', 'retenus', 'variables')}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
