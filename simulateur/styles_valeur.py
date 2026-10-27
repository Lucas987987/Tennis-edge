#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Valeur prédictive incrémentale des bilans contre les styles adverses.

Le challenger ajoute aux contrôles de styles_joueurs.py des taux pré-match
contractés vers 50 % : bilan global seul, ou bilan global + bilan de surface.
Apprentissage sur 2024, confirmation disjointe à partir de 2025. Aucun marché,
aucun résultat futur et aucune activation automatique.

Usage : python simulateur/styles_valeur.py /tmp/sackmann . [--maximum 8000]
Sortie : simulateur/rapport_valeur_styles_descriptifs.json
"""
import argparse
import datetime as dt
import heapq
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees  # noqa: E402
import elo as E  # noqa: E402
import match_simule as MS  # noqa: E402
import profils_robustes as PR  # noqa: E402
import profils_service as PS  # noqa: E402
import styles_descriptifs as SD  # noqa: E402
import styles_joueurs as ST  # noqa: E402

PRIOR_MATCHS = 20.0
MARGE_LOG_LOSS = .001
CANDIDATS = ('global', 'global_surface')


def _lg(p):
    return math.log(p/(1-p))


def _taux(acc, joueur, style, scope):
    """Taux disponible avant le match, contracté vers 50 % avec 20 matchs de prior."""
    ligne = acc.get((joueur, style, scope)) or {'n': 0, 'v': 0}
    n, v = ligne['n'], ligne['v']
    return (v + PRIOR_MATCHS/2) / (n + PRIOR_MATCHS), n


def _ajouter_resultat(acc, gagnant, perdant, style_g, style_p, surface):
    if style_p != 'indetermine':
        for scope in ('global', surface):
            ligne = acc.setdefault((gagnant, style_p, scope), {'n': 0, 'v': 0})
            ligne['n'] += 1
            ligne['v'] += 1
    if style_g != 'indetermine':
        for scope in ('global', surface):
            ligne = acc.setdefault((perdant, style_g, scope), {'n': 0, 'v': 0})
            ligne['n'] += 1


def _features(acc, h, a, style_h, style_a, surface):
    ph, nh = _taux(acc, h, style_a, 'global')
    pa, na = _taux(acc, a, style_h, 'global')
    ps_h, ns_h = _taux(acc, h, style_a, surface)
    ps_a, ns_a = _taux(acc, a, style_h, surface)
    return {
        'bilan_global': _lg(ph)-_lg(pa),
        'bilan_surface': _lg(ps_h)-_lg(ps_a),
        'documentation_bilans': min(nh, na),
        'documentation_surface': min(ns_h, ns_a),
        'taux_global_home': ph,
        'taux_global_away': pa,
    }


def observations(M, choisis, demi_vie=PS.DEMI_VIE, prior_mult=1.0, sigma=.15):
    """Mêmes contrôles que styles_joueurs, plus les bilans disponibles la veille.

    Les résultats sont versés aux bilans seulement au changement de date : sans
    heure historique fiable, un match du même jour n'est jamais supposé connu.
    """
    P, elo = PS.Profils(demi_vie, prior_mult), E.Elo()
    attente, serial, acc, out = [], 0, {}, []
    resultats_veille, jour_courant = [], None
    for m in sorted(M, key=lambda x: (x['date'], x.get('tour', 0), x.get('num', 0))):
        if jour_courant != m['date']:
            for ancien in resultats_veille:
                _ajouter_resultat(acc, *ancien)
            resultats_veille, jour_courant = [], m['date']
        debut = dt.datetime.combine(m['date'], dt.time())
        while attente and attente[0][0] < debut:
            _, _, ancien = heapq.heappop(attente)
            P.ajouter(ancien)
        gagnant, perdant = m['gagnant'], m['perdant']
        if m['circuit'] in ('CH', 'ITF'):
            elo.presenter(gagnant, 1200.0)
            elo.presenter(perdant, 1200.0)
        h, a = sorted((gagnant, perdant))
        ih = ST.instantane(P, h, m['circuit'], m['surface'], m['date'])
        ia = ST.instantane(P, a, m['circuit'], m['surface'], m['date'])
        mu = P.moyenne(m['circuit'], m['surface'])
        style_h = SD.classifier(ih['profil'], ih['balles_effectives'], mu)
        style_a = SD.classifier(ia['profil'], ia['balles_effectives'], mu)
        if id(m) in choisis:
            ch = MS.composantes(ih['profil'], ia['profil'], mu)
            ca = MS.composantes(ia['profil'], ih['profil'], mu)
            row = {
                'date': m['date'], 'semaine': ST._semaine(m['date']), 'y': int(gagnant == h),
                'elo': elo.proba(h, a, m['surface']),
                'service_retour': MS.victoire_pure(ch, ca, m['bo']//2+1, sigma),
                'style': ST.interaction(ih['profil'], ia['profil'], mu),
                'surface': m['surface'], 'circuit': m['circuit'],
                'documentation_balles': min(ih['balles_effectives'], ia['balles_effectives']),
                'documentation_matchs': min(elo.matchs(h), elo.matchs(a)),
                'paire_styles': '|'.join(sorted((style_h, style_a))),
            }
            row.update(_features(acc, h, a, style_h, style_a, m['surface']))
            out.append(row)
        if m.get('complet') and not m.get('abandon'):
            # Ordre attendu : gagnant, perdant, style du gagnant, style du perdant, surface.
            resultats_veille.append((gagnant, perdant, style_h if h == gagnant else style_a,
                                     style_a if h == gagnant else style_h, m['surface']))
        heapq.heappush(attente, (dt.datetime.combine(m['fin'], dt.time()), serial, m))
        serial += 1
        elo.maj(gagnant, perdant, m['surface'], m.get('niveau') == 'G',
                E.part_jeux(m['sets']) if m.get('complet') else None)
    return out


def _variables(r, candidat=None):
    x = ST._variables(r)
    if candidat in CANDIDATS:
        x.append(r['bilan_global'])
    if candidat == 'global_surface':
        x.append(r['bilan_surface'])
    return x


def _noms_variables(candidat=None):
    noms = ['constante', 'elo', 'service_retour', 'terre', 'gazon', 'wta', 'challenger', 'itf',
            'documentation_balles', 'documentation_matchs', 'moins_500_balles']
    if candidat in CANDIDATS:
        noms.append('bilan_global')
    if candidat == 'global_surface':
        noms.append('bilan_surface')
    return noms


def _bloc(y, rows, modele, candidat, bootstrap=0):
    p = ST._predire(modele, [_variables(r, candidat) for r in rows])
    return {'predictions': p, 'metriques': ST._metriques(y, p)}


def evaluer(rows, coupure=dt.date(2025, 1, 1), bootstrap=2000):
    dec = [r for r in rows if r['date'] < coupure]
    conf = [r for r in rows if r['date'] >= coupure]
    y_dec, y_conf = [r['y'] for r in dec], [r['y'] for r in conf]
    modeles, blocs_dec, blocs_conf = {}, {}, {}
    for candidat in (None,) + CANDIDATS:
        nom = candidat or 'controle'
        modele = ST._ajuster([_variables(r, candidat) for r in dec], y_dec)
        modeles[nom] = modele
        blocs_dec[nom] = _bloc(y_dec, dec, modele, candidat)
        blocs_conf[nom] = _bloc(y_conf, conf, modele, candidat)
    choisi = min(CANDIDATS, key=lambda c: blocs_dec[c]['metriques'].get('log_loss', float('inf')))
    base = blocs_conf['controle']['predictions']
    avec = blocs_conf[choisi]['predictions']
    gains = ST._gains(y_conf, base, avec)
    ic = ST._ic_gains(conf, base, avec, bootstrap)
    sous_groupes = {'global': list(range(len(conf)))}
    for surface in ('Hard', 'Clay', 'Grass'):
        sous_groupes[f'surface:{surface}'] = [i for i, r in enumerate(conf) if r['surface'] == surface]
    for nom, test in (
            ('bilans:0_match', lambda r: r['documentation_bilans'] == 0),
            ('bilans:1-9_matchs', lambda r: 1 <= r['documentation_bilans'] < 10),
            ('bilans:10-29_matchs', lambda r: 10 <= r['documentation_bilans'] < 30),
            ('bilans:>=30_matchs', lambda r: r['documentation_bilans'] >= 30)):
        sous_groupes[nom] = [i for i, r in enumerate(conf) if test(r)]
    paires = sorted({r['paire_styles'] for r in conf})
    for paire in paires:
        sous_groupes[f'paire:{paire}'] = [i for i, r in enumerate(conf) if r['paire_styles'] == paire]
    details = {}
    for nom, indices in sous_groupes.items():
        if nom == 'global' or len(indices) < 30:
            continue
        yy = [y_conf[i] for i in indices]
        sans_i, avec_i = [base[i] for i in indices], [avec[i] for i in indices]
        details[nom] = {'controle': ST._metriques(yy, sans_i), 'challenger': ST._metriques(yy, avec_i),
                        'gains': ST._gains(yy, sans_i, avec_i)}
    assez = len(dec) >= 100 and len(conf) >= 100
    ic_ll = (ic.get('log_loss') or {})
    confirme = bool(assez and gains['log_loss'] is not None and gains['brier'] is not None
                    and gains['log_loss'] >= MARGE_LOG_LOSS and gains['brier'] >= 0
                    and ic_ll.get('bas') is not None and ic_ll['bas'] > 0)
    positif_incertitude = bool(assez and gains['log_loss'] is not None and gains['log_loss'] > 0
                               and gains['brier'] is not None and gains['brier'] >= 0 and not confirme)
    return {
        'schema': 'valeur_styles_descriptifs_v1',
        'n': len(rows), 'n_decouverte': len(dec), 'n_confirmation': len(conf),
        'coupure': coupure.isoformat(), 'prior_matchs_par_bilan': PRIOR_MATCHS,
        'orientation': 'ordre alphabétique des identifiants, indépendant du résultat',
        'controles': ['Elo général et surface', 'surface', 'circuit', 'service–retour pur',
                      'balles effectives minimales', 'matchs Elo minimaux', 'indicateur moins de 500 balles'],
        'candidats': {'global': 'écart des logits des taux globaux contractés',
                      'global_surface': 'écarts des logits des taux globaux et de surface contractés'},
        'candidat_choisi_sur_decouverte': choisi,
        'convergence': {nom: bool(m and m['converged']) for nom, m in modeles.items()},
        'coefficients_standardises_decouverte': dict(zip(_noms_variables(choisi), modeles[choisi]['beta'])),
        'decouverte': {nom: b['metriques'] for nom, b in blocs_dec.items()},
        'confirmation': {nom: b['metriques'] for nom, b in blocs_conf.items()},
        'gains_du_candidat_choisi': gains,
        'ic95_bootstrap_semaine': ic,
        'sous_groupes_confirmation': details,
        'activation': False,
        'champion_actif_modifie': False,
        'verdict': ('apport confirmé hors échantillon ; challenger à soumettre à la gouvernance, sans activation automatique'
                    if confirme else 'signal positif mais incertain ; champion inchangé' if positif_incertitude
                    else 'apport non confirmé ; champion inchangé'),
        'regle': 'résultats versés après la date seulement ; aucune cote ; aucune modification du modèle actif',
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('archive')
    parser.add_argument('racine', nargs='?', default='.')
    parser.add_argument('--maximum', type=int, default=8000)
    parser.add_argument('--bootstrap', type=int, default=2000)
    args = parser.parse_args(argv)
    M = donnees.charger(args.archive, 2021)
    choisis = PR.selection(M, dt.date(2024, 1, 1), args.maximum)
    rows = observations(M, choisis)
    out = evaluer(rows, bootstrap=args.bootstrap)
    path = os.path.join(args.racine, 'simulateur', 'rapport_valeur_styles_descriptifs.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: out[k] for k in ('n', 'n_decouverte', 'n_confirmation',
          'candidat_choisi_sur_decouverte', 'gains_du_candidat_choisi', 'ic95_bootstrap_semaine', 'verdict')},
          ensure_ascii=False, indent=2))
    return out


if __name__ == '__main__':
    main()
