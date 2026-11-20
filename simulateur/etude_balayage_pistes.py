#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_balayage_pistes.py — reste-t-il un défaut d'étalonnage du % de victoire ? (12/11/2026, audit, paquet 236)

Après les paquets 228 à 234 (format du match, départ ITF, Grand Chelem, qualifications, signaux réappris), cette étude
cherche ce qui reste, SANS toucher à la période de jugement : tout est mesuré sur la période d'apprentissage seulement.
Elle sert aussi de registre : une piste classée ici « sans suite » n'a pas à être rejouée.

DEUX REJEUX
  A. ATP et WTA, archive 2018–2022 : Elo de production corrigé des pentes en place, plus les signaux en place sur le
     circuit (etude_signaux_reappris.py). Le Challenger n'est PAS regardé ici : l'archive n'a pas les résultats ITF
     hommes que le classement utilise, et deux études ont déjà changé de sens à cause de cela (paquets 229 et 230).
  B. Challenger « comme en production » : résultats ITF hommes dans l'Elo, départ ITF en place, du 01/01/2025 au
     30/09/2025 (la période d'apprentissage de etude_depart_itf.py ; les résultats ITF n'existent que depuis juin 2024).

PISTES : une pente (p' = σ(pente · logit p)) par niveau de tournoi, surface, saison, tour, expérience du joueur le moins
vu ; un décalage (logit) pour l'entrée dans le tableau (qualifié, invité, repêché), pour la charge de la semaine
précédente, et en Challenger pour le joueur vu d'abord en ITF.

RÈGLE ÉCRITE LE 12/11/2026, AVANT DE LANCER L'ÉTUDE :
  une piste n'est PORTÉE AU JUGEMENT (étude à part, sur la période jamais vue) que si, sur la période d'apprentissage,
  sa correction gagne au moins 0,001 de log loss sur au moins 1 000 matchs concernés, avec au moins 2 erreurs types.
  Ce seuil est mesuré ici sur les matchs mêmes où la correction est apprise : c'est un MAJORANT. Une piste qui ne
  l'atteint pas même ainsi est classée sans suite, et la période de jugement reste intacte.
  Rien de ce rapport n'entre en production.

Usage : python simulateur/etude_balayage_pistes.py /tmp/sackmann .
"""
import collections
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees as DN  # noqa: E402
import elo as E  # noqa: E402
import etude_age as EA  # noqa: E402
import etude_outsiders as EO  # noqa: E402
import etude_signaux_combines as ESC  # noqa: E402
import etude_signaux_reappris as ER  # noqa: E402

MIN_CONCERNES, MARGE, MIN_ERREURS_TYPES, MIN_CASE = 1000, 0.001, 2.0, 300
SORTIE = os.path.join(ICI, 'rapport_balayage_pistes.json')


def a_juger(b):
    return bool(b.get('matchs', 0) >= MIN_CONCERNES and b.get('gain', -1) >= MARGE and (b.get('erreurs_types') or 0) >= MIN_ERREURS_TYPES)


def piste_pente(famille, circuit, rows, cle):
    """Une pente propre par case de `cle(row)`. rows : [{'zf': logit du vainqueur, …}]."""
    G = collections.defaultdict(list)
    for r in rows:
        c = cle(r)
        if c is not None:
            G[str(c)].append(r['zf'])
    out = []
    for case, Z in sorted(G.items()):
        if len(Z) < MIN_CASE:
            continue
        k = EO.pente(Z)
        b = EO.bilan(Z, [k * z for z in Z])
        out.append({'famille': famille, 'circuit': circuit, 'case': case, 'forme': 'pente', 'valeur': round(k, 3),
                    'matchs': b['matchs'], 'favori_reel_pct': b['favori_reel_pct'], 'favori_annonce_pct': b['favori_annonce_pct'],
                    'gain': b['gain'], 'erreur_type': b['erreur_type'], 'erreurs_types': b['erreurs_types'], 'a_juger': a_juger(b)})
    return out


def piste_decalage(famille, circuit, rows, x):
    """Un décalage β · x, x vu du vainqueur (+1 : le vainqueur seul a le caractère, −1 : le perdant seul)."""
    C = [(r['zf'], float(x(r))) for r in rows]
    C = [(z, v) for z, v in C if v]
    if len(C) < MIN_CASE:
        return []
    b_ = ESC.apprendre([(z, (v,)) for z, v in C], k=1)[0]
    b = EO.bilan([z for z, _ in C], [z + b_ * v for z, v in C])
    return [{'famille': famille, 'circuit': circuit, 'case': 'matchs concernés', 'forme': 'décalage', 'valeur': round(b_, 3),
             'matchs': b['matchs'], 'gain': b['gain'], 'erreur_type': b['erreur_type'], 'erreurs_types': b['erreurs_types'],
             'a_juger': a_juger(b)}]


def saison(r):
    return 'janvier-février' if r['d'].month <= 2 else ('mars-octobre' if r['d'].month <= 10 else 'novembre-décembre')


def experience(r):
    n = r['n_min']
    return 'moins de 30' if n < 30 else ('30 à 99' if n < 100 else '100 et plus')


def pistes_du_circuit(circuit, rows):
    out = []
    for famille, cle in (('niveau du tournoi', lambda r: r.get('niveau')), ('surface', lambda r: r.get('surface')), ('saison', saison),
                         ('tour', lambda r: r.get('tour')), ('expérience du moins vu', experience)):
        out += piste_pente(famille, circuit, rows, cle)
    for e, nom in (('Q', 'qualifié'), ('WC', 'invité'), ('LL', 'repêché')):
        out += piste_decalage(f'entrée : {nom}', circuit, rows, lambda r, e=e: (r.get('entree_g') == e) - (r.get('entree_p') == e))
    out += piste_decalage('charge de la semaine précédente', circuit, rows, lambda r: min(r['charge_g'], 5) - min(r['charge_p'], 5))
    return out


def rejeu_archive(archive, racine):
    """Lignes ATP et WTA de 2018–2022 : zf = logit du vainqueur avec les signaux en place sur le circuit."""
    M = DN.charger(archive, 2012)
    etat = ER._json(racine, 'elo_etat.json')
    alias = dict(E.migrer_etat(etat).get('alias') or {}) if etat else {}
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    charge = collections.defaultdict(collections.Counter)      # joueur → {date de début du tournoi: matchs joués}
    for m in M:
        for n in (m.get('nom_g'), m.get('nom_p')):
            if k(n):
                charge[k(n)][m['date']] += 1
    R = ER._json(racine, 'rapport_signaux_reappris.json').get('circuits') or {}
    rows = []
    for r in ER.lignes(M, racine, EA.naissances(archive, k), k, details=True):
        if r['c'] not in ('ATP', 'WTA') or r['d'] >= ER.COUPURE:
            continue
        v = R.get(r['c']) or {}
        b = v.get('betas') if v.get('adopte') else v.get('betas_en_place')
        r['zf'] = ER._zc(r, [(b or {}).get(n, 0.0) for n in ER.NOMS])
        avant = r['d'] - dt.timedelta(days=7)
        r['charge_g'], r['charge_p'] = charge[r['g']][avant], charge[r['p']][avant]
        rows.append(r)
    return rows


def rejeu_challenger(archive, racine):
    """Challenger du 01/01/2025 au 30/09/2025, résultats ITF hommes dans l'Elo, départs en place."""
    import backtest_pronostic as BP
    import etude_depart_itf as ED
    M, n_itf = ED.matchs(archive, racine)
    el, bas = E.de_production(racine)
    origine, rows = {}, []
    for m in M:
        g, p = E.cle(m.get('nom_g')), E.cle(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m.get('surface')
        for j in (g, p):
            origine.setdefault(j, c)
        if bas and c in BP.BAS:
            el.presenter(g, E.depart_du_niveau(c, bas))
            el.presenter(p, E.depart_du_niveau(c, bas))
        if c == 'CH' and ED.DEBUT <= m['date'] < ED.COUPURE and not m.get('abandon') and m.get('niveau') != 'D':
            rows.append({'d': m['date'], 'zf': EO._lg(el.proba(g, p, s)), 'n_min': min(el.matchs(g), el.matchs(p)), 'niveau': m.get('niveau'),
                         'surface': s, 'itf_g': origine[g] == 'ITFH', 'itf_p': origine[p] == 'ITFH'})
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    return rows, n_itf


def pistes_challenger(rows):
    out = piste_pente('ensemble', 'CH', rows, lambda r: 'tous les matchs')
    out += piste_pente('niveau du tournoi', 'CH', rows, lambda r: r.get('niveau'))
    out += piste_pente('surface', 'CH', rows, lambda r: r.get('surface'))
    out += piste_pente('expérience du moins vu', 'CH', rows, experience)
    out += piste_decalage("joueur vu d'abord en ITF", 'CH', rows, lambda r: r['itf_g'] - r['itf_p'])
    return out


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    A = rejeu_archive(archive, racine)
    C, n_itf = rejeu_challenger(archive, racine)
    pistes = [x for c in ('ATP', 'WTA') for x in pistes_du_circuit(c, [r for r in A if r['c'] == c])] + pistes_challenger(C)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("mesuré sur la période d'apprentissage seulement ; une piste n'est portée au jugement que si sa correction y "
                     "gagne au moins 0,001 sur au moins 1 000 matchs concernés avec au moins 2 erreurs types (majorant : mesuré "
                     "là où la correction est apprise) ; sinon elle est classée sans suite et la période de jugement reste intacte"),
           'rejeux': {'ATP et WTA': {'periode': '2018–2022', 'matchs': len(A),
                                     'base': "Elo de production corrigé des pentes en place, signaux en place sur le circuit"},
                      'Challenger': {'periode': '01/01/2025 → 30/09/2025', 'matchs': len(C), 'itf_hommes_dans_le_rejeu': n_itf,
                                     'base': "Elo de production avec les résultats ITF hommes et les départs en place"}},
           'pistes': pistes,
           'pistes_a_juger': [f"{x['circuit']} · {x['famille']} · {x['case']}" for x in pistes if x['a_juger']],
           'en_production': False}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for x in pistes:
        print(f"  {x['circuit']:4s} {x['famille']:32s} {x['case']:18s} n={x['matchs']:5d} {x['forme']} {x['valeur']:+.3f} "
              f"gain {x['gain']:.4f} ± {x['erreur_type']:.4f}{'   ← À JUGER' if x['a_juger'] else ''}")
    print(f"{len(pistes)} cases mesurées ; à juger : {doc['pistes_a_juger'] or 'aucune'}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
