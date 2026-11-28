#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_grand_chelem_feuilles.py — paquet 533 (28/11/2026). Repérer les Grands Chelems dans nos feuilles ?

Constat : le classement Elo met plus de poids sur un match de Grand Chelem (× 1,1 sur K, elo.Elo.maj). L'archive Sackmann
le dit (niveau « G ») ; nos feuilles non : depuis juin 2026, un match de Wimbledon ou de l'US Open venu des feuilles est
compté comme un tournoi ordinaire (backtest_pronostic.py, source « fe »). La feuille donne pourtant les points du tournoi
(2 000 = Grand Chelem).

RÈGLE ÉCRITE LE 28/11/2026, AVANT TOUT CALCUL :
  1. Détecteur : une feuille est de Grand Chelem si le tournoi vaut 2 000 points. Contrôlé sur les feuilles anciennes
     retrouvées dans l'archive (2023 → mai 2026, même paire, feuille dans les 16 jours du début du tournoi) :
       • tableau final : il faut ≥ 99 % d'accord dans les deux sens (détecté → « G » chez Sackmann, « G » → détecté),
         sinon l'étude s'arrête (détecteur pas fiable) ;
       • qualifications : comptées comme Grand Chelem seulement si ≥ 90 % des qualifications retrouvées sont « G » chez
         Sackmann (on fait comme l'archive).
  2. Effet, même moteur (réglages de production, elo_etat.json, départ bas), historique Sackmann depuis 2016 puis nos
     feuilles après la fin de l'archive + 3 jours (comme le classement de production ; sans nos matchs suivis ni
     tennis-data, pour isoler le drapeau). Pronostic avant chaque match, mise à jour juste après.
       • Période 1 (archive, 2023-01-01 → fin) : A sans le drapeau, B avec le drapeau de l'archive — ce que vaut le
         drapeau ;
       • Période 2 (feuilles, après fin + 3 j) : A sans le drapeau (en place), B avec le drapeau du détecteur.
     Matchs jugés : ATP et WTA, joués du premier jour d'un Grand Chelem (qualifications comprises) aux 8 semaines qui
     suivent, chaque joueur avec au moins 5 matchs. Mesure : log loss, ATP et WTA séparément.
  3. Décision : B retenu si sa log loss est plus basse d'au moins 0,001 sur au moins 1 000 matchs, dans les DEUX périodes,
     pour l'ATP ET pour la WTA. Sinon rien ne change (et si le drapeau n'aide pas même en période 1, c'est noté).
Aucune cote. Le journal n'affiche que des comptes et des log loss.

Usage : python simulateur/etude_grand_chelem_feuilles.py /tmp/sackmann [racine]
"""
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

import donnees  # noqa: E402
import elo as E  # noqa: E402
import feuilles as FE  # noqa: E402

D = dt.date
POINTS_GC = 2000
ACCORD_MIN, QUALIF_MIN = 0.99, 0.90
SEUIL, N_MIN, CONNU_MIN = 0.001, 1000, 5
FENETRE, APRES_GC = 16, dt.timedelta(weeks=8)
DEBUT_P1 = D(2023, 1, 1)
BAS = ('CH', 'ITF', 'ITFH')
SORTIE = os.path.join(ICI, 'rapport_grand_chelem_feuilles.json')


def qualif(r):
    return 'qualif' in str(r.get('tournoi') or '').lower()


def detecte(r, avec_qualifs):
    return r.get('points_tournoi') == POINTS_GC and (avec_qualifs or not qualif(r))


def feuilles_avec_gc(brutes, P=None):
    """[(match au format donnees, fiche brute)] sans forfaits, triés par date."""
    out = []
    for r in brutes:
        if 'walkover' in str((r.get('statut') or {}).get('texte') or '').lower():
            continue
        m = FE.en_match(r, r.get('jeux') or (P or {}).get(r.get('id')))
        if m and m['nom_g'] and m['nom_p']:
            out.append((m, r))
    out.sort(key=lambda x: (x[0]['date'], x[0].get('tour', 0), x[0]['id'] or 0))
    return out


def controler(S, A, cle):
    """Accord du détecteur avec le niveau « G » de l'archive, sur les feuilles anciennes retrouvées."""
    index = collections.defaultdict(list)
    for s in S:
        if s['date'] >= DEBUT_P1 - dt.timedelta(days=FENETRE):
            index[frozenset((cle(s['nom_g']), cle(s['nom_p'])))].append(s)
    c = collections.Counter()
    for m, r in A:
        t = [s for s in index.get(frozenset((cle(m['nom_g']), cle(m['nom_p']))), ())
             if s['date'] <= m['date'] <= s['date'] + dt.timedelta(days=FENETRE)]
        if not t:
            continue
        g = t[0].get('niveau') == 'G'
        p = r.get('points_tournoi') == POINTS_GC
        q = 'qualif' if qualif(r) else 'tableau'
        c[f'{q}_retrouves'] += 1
        c[f'{q}_detecte'] += p
        c[f'{q}_G'] += g
        c[f'{q}_detecte_et_G'] += p and g
    def part(a, b):
        return c[a] / c[b] if c[b] else None
    return {'comptes': dict(c),
            'tableau_detecte_vers_G': part('tableau_detecte_et_G', 'tableau_detecte'),
            'tableau_G_vers_detecte': part('tableau_detecte_et_G', 'tableau_G'),
            'qualifs_G': part('qualif_G', 'qualif_detecte')}


def fenetres_gc(debuts):
    """Jours des Grands Chelems (premier jour vu, qualifications comprises) → [(début, début + 8 semaines)]."""
    out = []
    for d in sorted(debuts):
        if out and d <= out[-1][0] + dt.timedelta(days=30):
            continue
        out.append((d, d + APRES_GC))
    return out


def dans(fen, d):
    return any(a <= d < b for a, b in fen)


def rejouer(evts, racine):
    """evts : [(jour, gagnant, perdant, circuit, surface, grand chelem, part des jeux, jugé ?)] dans l'ordre.
    Renvoie {(période, circuit): [log loss]} des matchs jugés."""
    el, bas = E.de_production(racine)
    out = collections.defaultdict(list)
    for d, g, p, c, s, gc, part, per in evts:
        if bas and c in BAS:
            for k in (g, p):
                el.presenter(k, E.depart_du_niveau(c, bas))
        if per and min(el.matchs(g), el.matchs(p)) >= CONNU_MIN:
            q = min(max(el.proba(g, p, s), 1e-6), 1 - 1e-6)
            out[(per, c)].append(-math.log(q))
        el.maj(g, p, s, gc, part)
    return out


def evenements(S, F3, fen1, fen2, cle, drapeau_archive, drapeau_feuilles, avec_qualifs):
    ev = []
    for s in S:
        g, p = cle(s['nom_g']), cle(s['nom_p'])
        if not g or not p or g == p:
            continue
        per = 'periode_1' if (s['date'] >= DEBUT_P1 and s['circuit'] in ('ATP', 'WTA') and dans(fen1, s['date'])) else None
        ev.append((s['date'], g, p, s['circuit'], s['surface'], drapeau_archive and s.get('niveau') == 'G',
                   E.part_jeux(s['sets']) if s.get('complet') else None, per))
    for m, r in F3:
        g, p = cle(m['nom_g']), cle(m['nom_p'])
        if not g or not p or g == p:
            continue
        per = 'periode_2' if (m['circuit'] in ('ATP', 'WTA') and dans(fen2, m['date'])) else None
        ev.append((m['date'], g, p, m['circuit'], m['surface'], drapeau_feuilles and detecte(r, avec_qualifs),
                   E.part_jeux(m['sets']) if m.get('complet') else None, per))
    return ev                                           # S puis F3, chacun déjà dans l'ordre (F3 après l'archive)


def bilan(la, lb):
    out = {}
    for k in sorted(set(la) | set(lb)):
        a, b = la.get(k, []), lb.get(k, [])
        if len(a) != len(b) or not a:
            continue
        n = len(a)
        d = [y - x for x, y in zip(a, b)]
        md = sum(d) / n
        et = math.sqrt(sum((x - md) ** 2 for x in d) / max(n - 1, 1) / n) if n > 1 else 0.0
        out[f'{k[0]} {k[1]}'] = {'n': n, 'll_A': round(sum(a) / n, 5), 'll_B': round(sum(b) / n, 5),
                                 'gain': round(-md, 5), 'erreur_type': round(et, 5)}
    return out


def decider(res):
    cases = [res.get(f'{p} {c}') for p in ('periode_1', 'periode_2') for c in ('ATP', 'WTA')]
    if any(x is None or x['n'] < N_MIN for x in cases):
        return 'pas assez de matchs : rien ne change'
    if all(x['gain'] >= SEUIL for x in cases):
        return 'retenu : drapeau Grand Chelem sur nos feuilles'
    if any(res[f'periode_1 {c}']['gain'] < SEUIL for c in ('ATP', 'WTA')):
        return "non retenu : rien ne change (le drapeau n'aide pas assez même sur l'archive)"
    return 'non retenu : rien ne change'


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    archive = args[0] if args else '/tmp/sackmann'
    racine = args[1] if len(args) > 1 else os.path.join(ICI, '..')
    S = donnees.charger(archive, 2016)
    if not S:
        print('::error::archive absente')
        return 1
    fin = max(s['date'] for s in S)
    P = FE.points(racine)
    recentes = feuilles_avec_gc(FE.lire(racine), P)
    anciennes = feuilles_avec_gc(FE.lire_archive(racine))
    try:
        with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
            alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    connus = {}
    for s in S:
        for n in (s['nom_g'], s['nom_p']):
            connus.setdefault(E.cle(n), n)
    for k, v in E.unifier(connus, {n for m, _ in recentes + anciennes for n in (m['nom_g'], m['nom_p'])}).items():
        alias.setdefault(k, v)
    cle = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None  # noqa: E731

    ctl = controler(S, anciennes, cle)
    print(f"Archive jusqu'au {fin} · feuilles anciennes {len(anciennes)} · feuilles récentes {len(recentes)}", flush=True)
    print(f"Détecteur (feuilles anciennes retrouvées dans l'archive) : {ctl['comptes']}")
    print(f"  tableau final : détecté → G {ctl['tableau_detecte_vers_G']} · G → détecté {ctl['tableau_G_vers_detecte']}"
          f" · qualifications détectées qui sont G : {ctl['qualifs_G']}")
    rap = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'paquet': 533,
           'archive_jusqu_au': fin.isoformat(), 'detecteur': ctl}
    fiable = all((x or 0) >= ACCORD_MIN for x in (ctl['tableau_detecte_vers_G'], ctl['tableau_G_vers_detecte']))
    if not fiable:
        rap['verdict'] = 'détecteur pas fiable : étude arrêtée, rien ne change'
        print('Verdict :', rap['verdict'])
        with open(SORTIE, 'w', encoding='utf-8') as f:
            json.dump(rap, f, ensure_ascii=False, indent=1)
        return 0
    avec_qualifs = (ctl['qualifs_G'] or 0) >= QUALIF_MIN
    rap['qualifications_comptees'] = avec_qualifs
    print(f"Qualifications comptées comme Grand Chelem : {'oui' if avec_qualifs else 'non'}")

    F3 = [(m, r) for m, r in recentes if m['date'] > fin + dt.timedelta(days=3)]
    fen1 = fenetres_gc(s['date'] for s in S if s.get('niveau') == 'G' and s['date'] >= DEBUT_P1)
    fen2 = fenetres_gc(m['date'] for m, r in F3 if r.get('points_tournoi') == POINTS_GC)
    rap['grands_chelems'] = {'periode_1': [a.isoformat() for a, _ in fen1], 'periode_2': [a.isoformat() for a, _ in fen2]}
    rap['feuilles_gc_periode_2'] = sum(1 for m, r in F3 if detecte(r, avec_qualifs))
    print(f"Grands Chelems jugés : période 1 {len(fen1)} · période 2 {len(fen2)} "
          f"({rap['feuilles_gc_periode_2']} feuilles de Grand Chelem après l'archive)", flush=True)

    sans = rejouer(evenements(S, F3, fen1, fen2, cle, False, False, avec_qualifs), racine)
    avec = rejouer(evenements(S, F3, fen1, fen2, cle, True, True, avec_qualifs), racine)
    # période 2 : A = l'archive avec son drapeau (comme la production) et nos feuilles sans ; B = les deux avec
    en_place = rejouer(evenements(S, F3, fen1, fen2, cle, True, False, avec_qualifs), racine)
    res = bilan({k: v for k, v in sans.items() if k[0] == 'periode_1'}, {k: v for k, v in avec.items() if k[0] == 'periode_1'})
    res.update(bilan({k: v for k, v in en_place.items() if k[0] == 'periode_2'},
                     {k: v for k, v in avec.items() if k[0] == 'periode_2'}))
    for k, x in res.items():
        print(f"  {k:13s} n={x['n']:6d}  {x['ll_A']:.4f} → {x['ll_B']:.4f}  (gain {x['gain']:+.4f} ± {x['erreur_type']:.4f})")
    rap['resultats'] = res
    rap['verdict'] = decider(res)
    print('Verdict :', rap['verdict'])
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
