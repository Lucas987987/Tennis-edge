#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apport incrémental des statistiques détaillées contre les styles adverses.

Les écarts sont ceux du joueur contre le style adverse par rapport à ses matchs
contre tous les adversaires, sur le périmètre global. Ils s'ajoutent au bilan
global déjà connu et aux contrôles Elo/service–retour. Trois candidats compactes
sont choisis sur 2024 seulement, puis figés pour le diagnostic 2025–2026.
Cette période ayant déjà été réutilisée, elle ne permet aucune activation.

Usage : python simulateur/etude_statistiques_styles.py /tmp/sackmann . --maximum 8000
Sorties : rapport_statistiques_styles.json et modele_statistiques_styles.json.
"""
import argparse
import datetime as dt
import heapq
import json
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
import styles_valeur as SV  # noqa: E402

SCHEMA = 'statistiques_styles_adverses_v1'
GEL_UTC = '2026-10-28T00:00:00+00:00'
CANDIDATS = {
    'points': ('points_gagnes_pct',),
    'service_retour': ('service_gagnes_pct', 'retour_gagnes_pct'),
    'pression': ('service_gagnes_pct', 'retour_gagnes_pct', 'gagnes_2e_pct',
                 'balles_break_sauvees_pct', 'balles_break_converties_pct'),
}
NOMS_BASE = ['constante', 'elo', 'service_retour', 'terre', 'gazon', 'wta', 'challenger', 'itf',
             'documentation_balles', 'documentation_matchs', 'moins_500_balles', 'bilan_global']


def _ajouter_resultat(acc, m, style_g, style_p):
    """Verse V/D et feuilles après la date, y compris à la référence tous styles."""
    g, p, surface = m['gagnant'], m['perdant'], m['surface']
    sg = SD._stats_match(m, True)
    sp = SD._stats_match(m, False)
    if style_p != 'indetermine':
        SD._ajouter(acc, g, style_p, surface, {}, True, sg)
    SD._ajouter(acc, g, SD.TOUS_STYLES, surface, {}, True, sg)
    if style_g != 'indetermine':
        SD._ajouter(acc, p, style_g, surface, {}, False, sp)
    SD._ajouter(acc, p, SD.TOUS_STYLES, surface, {}, False, sp)


def features_stats(acc, h, a, style_h, style_a):
    """Même construction que la production, centralisée dans styles_descriptifs."""
    return SD.variables_statistiques(acc, h, a, style_h, style_a)


def observations(M, choisis, demi_vie=PS.DEMI_VIE, prior_mult=1.0, sigma=.15):
    """Variables strictement pré-match, avec résultats et feuilles versés après la date."""
    P, elo = PS.Profils(demi_vie, prior_mult), E.Elo()
    attente, serial, acc, out = [], 0, {}, []
    resultats_veille, jour_courant = [], None
    for m in sorted(M, key=lambda x: (x['date'], x.get('tour', 0), x.get('num', 0))):
        if jour_courant != m['date']:
            for ancien, sg, sp in resultats_veille:
                _ajouter_resultat(acc, ancien, sg, sp)
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
                'surface': m['surface'], 'circuit': m['circuit'],
                'documentation_balles': min(ih['balles_effectives'], ia['balles_effectives']),
                'documentation_matchs': min(elo.matchs(h), elo.matchs(a)),
            }
            row.update(SV._features(acc, h, a, style_h, style_a, m['surface']))
            row.update(features_stats(acc, h, a, style_h, style_a))
            out.append(row)
        if m.get('complet') and not m.get('abandon'):
            style_g = style_h if h == gagnant else style_a
            style_p = style_a if h == gagnant else style_h
            resultats_veille.append((m, style_g, style_p))
        heapq.heappush(attente, (dt.datetime.combine(m['fin'], dt.time()), serial, m))
        serial += 1
        elo.maj(gagnant, perdant, m['surface'], m.get('niveau') == 'G',
                E.part_jeux(m['sets']) if m.get('complet') else None)
    return out


def _variables(r, candidat=None, bilan=True):
    x = ST._variables(r)
    if bilan:
        x.append(r['bilan_global'])
    if candidat:
        x.extend(r[f'stats_{nom}'] for nom in CANDIDATS[candidat])
    return x


def _noms(candidat):
    return NOMS_BASE + [f'ecart_{nom}' for nom in CANDIDATS[candidat]]


def _couverture(rows):
    n = len(rows)
    documentes = sum(r['documentation_stats'] > 0 for r in rows)
    return {'n': n, 'deux_joueurs_documentes': documentes,
            'pct': round(100 * documentes / n, 2) if n else None}


def evaluer(rows, coupure=dt.date(2025, 1, 1), bootstrap=2000):
    dec = [r for r in rows if r['date'] < coupure]
    conf = [r for r in rows if r['date'] >= coupure]
    y_dec, y_conf = [r['y'] for r in dec], [r['y'] for r in conf]
    modeles = {'controle': ST._ajuster([_variables(r, bilan=False) for r in dec], y_dec),
               'bilan': ST._ajuster([_variables(r) for r in dec], y_dec)}
    predictions_dec = {
        'controle': ST._predire(modeles['controle'], [_variables(r, bilan=False) for r in dec]),
        'bilan': ST._predire(modeles['bilan'], [_variables(r) for r in dec])}
    predictions_conf = {
        'controle': ST._predire(modeles['controle'], [_variables(r, bilan=False) for r in conf]),
        'bilan': ST._predire(modeles['bilan'], [_variables(r) for r in conf])}
    for candidat in CANDIDATS:
        modeles[candidat] = ST._ajuster([_variables(r, candidat) for r in dec], y_dec)
        predictions_dec[candidat] = ST._predire(modeles[candidat], [_variables(r, candidat) for r in dec])
        predictions_conf[candidat] = ST._predire(modeles[candidat], [_variables(r, candidat) for r in conf])
    choisi = min(CANDIDATS, key=lambda c: ST._metriques(y_dec, predictions_dec[c])['log_loss'])
    base_bilan, base_controle = predictions_conf['bilan'], predictions_conf['controle']
    avec = predictions_conf[choisi]
    gains_bilan = ST._gains(y_conf, base_bilan, avec)
    gains_controle = ST._gains(y_conf, base_controle, avec)
    ic_bilan = ST._ic_gains(conf, base_bilan, avec, bootstrap)
    ic_controle = ST._ic_gains(conf, base_controle, avec, bootstrap)
    sous_groupes = {}
    groupes = {f'surface:{s}': [i for i, r in enumerate(conf) if r['surface'] == s]
               for s in ('Hard', 'Clay', 'Grass')}
    groupes.update({
        'stats:0_match': [i for i, r in enumerate(conf) if r['documentation_stats'] == 0],
        'stats:1-9_matchs': [i for i, r in enumerate(conf) if 1 <= r['documentation_stats'] < 10],
        'stats:10-29_matchs': [i for i, r in enumerate(conf) if 10 <= r['documentation_stats'] < 30],
        'stats:>=30_matchs': [i for i, r in enumerate(conf) if r['documentation_stats'] >= 30],
    })
    for nom, indices in groupes.items():
        if len(indices) < 30:
            continue
        yy = [y_conf[i] for i in indices]
        sans_i = [base_bilan[i] for i in indices]
        avec_i = [avec[i] for i in indices]
        sous_groupes[nom] = {'controle_avec_bilan': ST._metriques(yy, sans_i),
                             'challenger': ST._metriques(yy, avec_i),
                             'gains_incrementaux': ST._gains(yy, sans_i, avec_i)}
    bas = (ic_bilan.get('log_loss') or {}).get('bas')
    assez = len(dec) >= 100 and len(conf) >= 100
    diagnostic_positif = bool(assez and gains_bilan['log_loss'] is not None and gains_bilan['log_loss'] > 0
                              and gains_bilan['brier'] is not None and gains_bilan['brier'] >= 0)
    franchit_gardes = bool(diagnostic_positif and gains_bilan['log_loss'] >= SV.MARGE_LOG_LOSS
                           and bas is not None and bas > 0)
    modele = modeles[choisi]
    return {
        'schema': SCHEMA, 'n': len(rows), 'n_decouverte': len(dec), 'n_confirmation': len(conf),
        'coupure': coupure.isoformat(), 'orientation': 'ordre alphabétique, indépendant du résultat',
        'reference_incrementale': 'mêmes contrôles + bilan global ; les statistiques sont le seul ajout',
        'candidats': {nom: list(variables) for nom, variables in CANDIDATS.items()},
        'candidat_choisi_sur_decouverte': choisi,
        'couverture': {'decouverte': _couverture(dec), 'diagnostic': _couverture(conf)},
        'convergence': {nom: bool(m and m['converged']) for nom, m in modeles.items()},
        'decouverte': {nom: ST._metriques(y_dec, p) for nom, p in predictions_dec.items()},
        'diagnostic': {nom: ST._metriques(y_conf, p) for nom, p in predictions_conf.items()},
        'gains_incrementaux_au_bilan': gains_bilan,
        'ic95_incrementaux_bootstrap_semaine': ic_bilan,
        'gains_contre_controle_sans_bilan': gains_controle,
        'ic95_contre_controle_bootstrap_semaine': ic_controle,
        'sous_groupes_diagnostic': sous_groupes,
        'coefficients_standardises_decouverte': dict(zip(_noms(choisi), modele['beta'])) if modele else None,
        'modele_complet_decouverte': modele,
        'modeles_complets_decouverte': modeles,
        'nature_diagnostic': '2025–2026 historique réutilisé ; jamais une confirmation prospective nouvelle',
        'marche_utilise': False, 'activation': False, 'champion_actif_modifie': False,
        'diagnostic_positif': diagnostic_positif, 'gardes_historiques_franchies': franchit_gardes,
        'verdict': ('apport incrémental positif dans le diagnostic ; challenger figé à journaliser prospectivement, champion inchangé'
                    if diagnostic_positif else 'apport incrémental non démontré ; statistiques conservées pour recherche, champion inchangé'),
        'regle': 'résultats et feuilles versés après la date ; trois candidats choisis sur 2024 ; aucune activation automatique',
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
    dossier = os.path.join(args.racine, 'simulateur')
    with open(os.path.join(dossier, 'rapport_statistiques_styles.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    choisi = out['candidat_choisi_sur_decouverte']
    modele = {
        'schema': SCHEMA, 'gel_utc': GEL_UTC, 'activation': False,
        'ajustement': 'régression logistique ridge 1.0 sur découverte 2024 uniquement',
        'candidat': choisi, 'variables': _noms(choisi)[1:],
        'variables_statistiques': list(CANDIDATS[choisi]),
        'reference': 'contrôles Elo/service–retour + bilan global + écarts détaillés à tous styles',
        'orientation_apprentissage': 'identifiants joueurs par ordre alphabétique',
        'controle': out['modeles_complets_decouverte']['controle'],
        'bilan': out['modeles_complets_decouverte']['bilan'],
        'challenger': out['modeles_complets_decouverte'][choisi],
        'surface_cible': 'Hard',
        'selection_surface': 'signal dur repéré post hoc ; aucune validation historique nouvelle',
        'nature_diagnostic': out['nature_diagnostic'],
        'confirmation_future': 'apport incrémental apparié au champion réellement publié, sur nouveaux pronostics figés uniquement',
    }
    with open(os.path.join(dossier, 'modele_statistiques_styles.json'), 'w', encoding='utf-8') as f:
        json.dump(modele, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: out[k] for k in ('n', 'n_decouverte', 'n_confirmation',
          'candidat_choisi_sur_decouverte', 'gains_incrementaux_au_bilan',
          'ic95_incrementaux_bootstrap_semaine', 'gains_contre_controle_sans_bilan', 'verdict')},
          ensure_ascii=False, indent=2))
    return out


if __name__ == '__main__':
    main()
