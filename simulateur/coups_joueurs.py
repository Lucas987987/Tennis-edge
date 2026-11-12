#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
coups_joueurs.py — comment chaque joueur marque ses points, d'après le Match Charting Project (12/11/2026, paquet 249,
demande de Lucas : tiroir « Points marqués » de la fiche).

Le Match Charting Project (Jeff Sackmann et ses bénévoles, CC BY-NC-SA 4.0) relève point par point ~1 300 matchs par
an, surtout le haut du classement. Pour chaque match relevé et chaque joueur, ses points gagnés se décomposent
EXACTEMENT (vérifié sur 6 000 joueurs-matchs : 96 % à l'unité près) en :
  aces · services non retournés (non retournés + retours en faute forcée) · coups gagnants du coup droit (coup droit et
  slice de coup droit) · du revers (revers et slice de revers) · au filet (volées, demi-volées, volées de fond, smashes)
  · amortis · lobs · fautes provoquées chez l'adversaire · fautes directes de l'adversaire · doubles fautes adverses.
  (Les coups « T », trick shots, rarissimes, sont laissés de côté.)
Plus les montées au filet (points joués au filet, points gagnés).

Ce fichier garde, pour chaque joueur relevé au moins MIN_MATCHS fois dans les FENETRE_J derniers jours, la SOMME de ces
comptes. La fiche du match (vitrine.ajouter_points_marques) applique ses habitudes au total de points prévu par la
simulation. INFORMATION DESCRIPTIVE : rien de ceci n'entre dans le calcul du % de victoire.

Fichiers lus (dossier du dépôt cloné) : charting-{m,w}-matches.csv, -stats-Overview.csv, -stats-ShotTypes.csv,
-stats-ServeBasics.csv, -stats-NetPoints.csv.
Usage : python simulateur/coups_joueurs.py /tmp/mcp .
"""
import collections
import csv
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

SORTIE = os.path.join('simulateur', 'coups_joueurs.json')
MIN_MATCHS, FENETRE_J = 10, 3 * 365
CATEGORIES = ('aces', 'services_non_retournes', 'coup_droit', 'revers', 'filet', 'amorti', 'lob',
              'fautes_provoquees', 'fautes_directes_adverses', 'doubles_fautes_adverses')
CODES = {'coup_droit': 'FR', 'revers': 'BS', 'filet': 'VZOPHIJK', 'amorti': 'UY', 'lob': 'LM'}


def _lire(chemin):
    try:
        with open(chemin, encoding='utf-8', errors='replace', newline='') as f:
            yield from csv.DictReader(f)
    except OSError:
        return


def _i(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def comptes_du_match(ov, ov_adv, st, st_adv, sb, net):
    """Comptes d'UN joueur dans UN match (dictionnaires bruts des fichiers ; st : {ligne: dict})."""
    tot = st.get('Total') or {}
    c = {'aces': _i(sb.get('aces')),
         'services_non_retournes': _i(sb.get('unret')) + _i(sb.get('forced_err')),
         'fautes_provoquees': _i(tot.get('induced_forced')),
         'fautes_directes_adverses': _i((st_adv.get('Total') or {}).get('unforced')),
         'doubles_fautes_adverses': _i(ov_adv.get('dfs'))}
    for cat, codes in CODES.items():
        c[cat] = sum(_i((st.get(k) or {}).get('winners')) for k in codes)
    c['points_gagnes'] = _i(ov.get('first_won')) + _i(ov.get('second_won')) + _i(ov.get('return_pts_won'))
    c['points_joues'] = _i(ov.get('serve_pts')) + _i(ov.get('return_pts'))
    c['montees'] = _i((net or {}).get('net_pts'))
    c['montees_gagnees'] = _i((net or {}).get('pts_won'))
    return c


def charger(dossier):
    """{nom du joueur: [(date, comptes)]} sur tous les matchs relevés complets des deux circuits."""
    out = collections.defaultdict(list)
    for g in ('m', 'w'):
        f = lambda n: os.path.join(dossier, f'charting-{g}-{n}.csv')  # noqa: E731
        dates = {}
        for r in _lire(f('matches')):
            try:
                d = str(r.get('Date') or '')
                dates[r['match_id']] = dt.date(int(d[:4]), int(d[4:6]), int(d[6:8]))
            except (KeyError, ValueError):
                continue
        ov = {(r['match_id'], r['player']): r for r in _lire(f('stats-Overview')) if r.get('set') == 'Total'}
        sb = {(r['match_id'], r['player']): r for r in _lire(f('stats-ServeBasics')) if r.get('row') == 'Total'}
        net = {(r['match_id'], r['player']): r for r in _lire(f('stats-NetPoints')) if r.get('row') == 'NetPoints'}
        st = collections.defaultdict(dict)
        for r in _lire(f('stats-ShotTypes')):
            st[(r['match_id'], r['player'])][r['row']] = r
        par_match = collections.defaultdict(list)
        for (mid, p) in ov:
            par_match[mid].append(p)
        for mid, ps in par_match.items():
            if len(ps) != 2 or mid not in dates:
                continue
            for i in (0, 1):
                p, q = ps[i], ps[1 - i]
                if (mid, p) not in st or (mid, q) not in st or (mid, p) not in sb:
                    continue
                c = comptes_du_match(ov[(mid, p)], ov[(mid, q)], st[(mid, p)], st[(mid, q)], sb[(mid, p)], net.get((mid, p)))
                if c['points_gagnes'] <= 0 or sum(c[k] for k in CATEGORIES) <= 0:
                    continue
                out[p].append((dates[mid], c))
    return out


def exporter(par_joueur, jour, cle):
    """{clé: {matchs, depuis, jusqu_au, comptes}} des joueurs relevés au moins MIN_MATCHS fois sur la fenêtre (deux
    graphies d'un même joueur sont additionnées)."""
    debut = jour - dt.timedelta(days=FENETRE_J)
    par_cle = collections.defaultdict(list)
    for nom, L in par_joueur.items():
        k = cle(nom)
        if k:
            par_cle[k] += [(d, c) for d, c in L if debut <= d <= jour]
    out = {}
    for k, L in par_cle.items():
        if len(L) < MIN_MATCHS:
            continue
        s = collections.Counter()
        for _, c in L:
            s.update(c)
        out[k] = {'matchs': len(L), 'depuis': min(d for d, _ in L).isoformat(), 'jusqu_au': max(d for d, _ in L).isoformat(),
                  'comptes': {x: s[x] for x in CATEGORIES + ('points_gagnes', 'points_joues', 'montees', 'montees_gagnees')}}
    return out


def main(argv):
    dossier = argv[1] if len(argv) > 1 else '/tmp/mcp'
    racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    import elo as E
    try:
        with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
            alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    cle = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None  # noqa: E731
    P = charger(dossier)
    if not P:
        print("::warning::Match Charting Project absent : coups_joueurs.json inchangé")
        return 0
    jour = dt.date.today()
    J = exporter(P, jour, cle)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'descriptif_seulement': True,
           'source': 'Match Charting Project (Jeff Sackmann et bénévoles, CC BY-NC-SA 4.0)',
           'regle': (f"comptes additionnés des matchs relevés coup par coup des {FENETRE_J // 365} dernières années ; "
                     f"joueur gardé à partir de {MIN_MATCHS} matchs relevés"),
           'categories': list(CATEGORIES), 'joueurs': J}
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print(f"Coups des joueurs : {len(J)} joueurs relevés au moins {MIN_MATCHS} fois ({sum(len(v) for v in P.values())} "
          f"joueurs-matchs lus)")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
