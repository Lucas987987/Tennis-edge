#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Correction orientée des duels de profils serveurs, branche par branche.

Le socle reste commun : Elo, surface, circuit, service–retour pur, documentation
et bilan global contre les styles. Chaque candidat ajoute une seule variable,
active uniquement dans sa branche (ATP, WTA ou Challenger/ITF). Ce ne sont donc
pas trois algorithmes autonomes. Tous les coefficients sont ajustés sur 2024,
puis figés pour le diagnostic historique réutilisé 2025–2026.

Les quatre duels sont ceux fournis avant l'étude pour l'hypothèse WTA :
serveur_attaquant/contreur, serveur_attaquant/equilibre,
grand_serveur/contreur et grand_serveur/retourneur_pressant. La variable vaut
+1 si le profil serveur est home, -1 s'il est away et 0 sinon. Aucun bonus de
points de victoire n'est injecté et aucun marché n'est lu.

Usage : python simulateur/etude_serveurs_circuits.py /tmp/archive . --maximum 8000
Sorties : rapport_serveurs_circuits.json et modele_serveurs_circuits.json.
"""
import argparse
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees  # noqa: E402
import profils_robustes as PR  # noqa: E402
import styles_joueurs as ST  # noqa: E402
import styles_valeur as SV  # noqa: E402

SCHEMA = 'serveurs_styles_circuits_v1'
GEL_UTC = '2026-11-01T00:00:00+00:00'
COUPURE = dt.date(2025, 1, 1)
BRANCHES = {'atp': ('ATP',), 'wta': ('WTA',), 'challenger': ('CH', 'ITF')}
DUELS = {
    'serveur_attaquant_contre_contreur': ('serveur_attaquant', 'contreur'),
    'serveur_attaquant_contre_equilibre': ('serveur_attaquant', 'equilibre'),
    'grand_serveur_contre_contreur': ('grand_serveur', 'contreur'),
    'grand_serveur_contre_retourneur_pressant': ('grand_serveur', 'retourneur_pressant'),
}
PAIRES_DUELS = {v: k for k, v in DUELS.items()}
NOMS_BASE = ['constante', 'elo', 'service_retour', 'terre', 'gazon', 'wta', 'challenger', 'itf',
             'documentation_balles', 'documentation_matchs', 'moins_500_balles', 'bilan_global',
             'duel_serveur_branche']


def duel_serveur(style_h, style_a):
    """Orientation indépendante du résultat ; zéro hors des quatre duels figés."""
    if (style_h, style_a) in PAIRES_DUELS:
        return 1.0
    if (style_a, style_h) in PAIRES_DUELS:
        return -1.0
    return 0.0


def nom_duel(style_h, style_a):
    if (style_h, style_a) in PAIRES_DUELS:
        return PAIRES_DUELS[(style_h, style_a)], 1
    if (style_a, style_h) in PAIRES_DUELS:
        return PAIRES_DUELS[(style_a, style_h)], -1
    return None, 0


def branche(circuit):
    for nom, circuits in BRANCHES.items():
        if circuit in circuits:
            return nom
    raise ValueError(f'Circuit non couvert : {circuit}')


def variable_branche(row, nom_branche):
    return (duel_serveur(row['style_home'], row['style_away'])
            if branche(row['circuit']) == nom_branche else 0.0)


def _variables(row, nom_branche=None, bilan=True):
    x = ST._variables(row)
    if bilan:
        x.append(row['bilan_global'])
    if nom_branche:
        x.append(variable_branche(row, nom_branche))
    return x


def _metriques(rows, predictions):
    return ST._metriques([r['y'] for r in rows], predictions)


def _gains(rows, sans, avec):
    return ST._gains([r['y'] for r in rows], sans, avec)


def _couverture(rows):
    n = sum(duel_serveur(r['style_home'], r['style_away']) != 0 for r in rows)
    return {'n': len(rows), 'duels_serveurs': n,
            'pct_duels_serveurs': round(100*n/len(rows), 2) if rows else None}


def _duels_wta(rows, controle, challenger):
    """Résidus et métriques des quatre duels, sans sélection du meilleur."""
    out = {}
    for nom in DUELS:
        indices = [i for i, r in enumerate(rows)
                   if r['circuit'] == 'WTA' and nom_duel(r['style_home'], r['style_away'])[0] == nom]
        if not indices:
            out[nom] = {'n': 0}
            continue
        rr = [rows[i] for i in indices]
        p0, p1 = [controle[i] for i in indices], [challenger[i] for i in indices]
        residus0, residus1 = [], []
        for r, a, b in zip(rr, p0, p1):
            sens = nom_duel(r['style_home'], r['style_away'])[1]
            y_serveur = r['y'] if sens == 1 else 1-r['y']
            p0_serveur = a if sens == 1 else 1-a
            p1_serveur = b if sens == 1 else 1-b
            residus0.append(y_serveur-p0_serveur)
            residus1.append(y_serveur-p1_serveur)
        n = len(rr)
        moyenne = sum(residus0)/n
        variance = sum((x-moyenne)**2 for x in residus0)/(n-1) if n > 1 else 0.0
        demi_ic = 1.96*(variance/n)**.5
        out[nom] = {
            'n': n,
            'victoires_serveur_pct': round(100*sum(r['y'] if nom_duel(r['style_home'], r['style_away'])[1] == 1
                                                   else 1-r['y'] for r in rr)/n, 2),
            'residuel_controle_points': round(100*moyenne, 3),
            'ic95_residuel_controle_points': [round(100*(moyenne-demi_ic), 3),
                                               round(100*(moyenne+demi_ic), 3)],
            'residuel_challenger_points': round(100*sum(residus1)/n, 3),
            'controle_avec_bilan': _metriques(rr, p0), 'challenger': _metriques(rr, p1),
            'gains_incrementaux': _gains(rr, p0, p1),
            'note': 'résiduel après Elo/service–retour/bilan, pas effet causal ni bonus à injecter',
        }
    return out


def evaluer(rows, coupure=COUPURE, bootstrap=2000):
    dec = [r for r in rows if r['date'] < coupure]
    conf = [r for r in rows if r['date'] >= coupure]
    y_dec = [r['y'] for r in dec]
    controle = ST._ajuster([_variables(r) for r in dec], y_dec)
    p0_dec = ST._predire(controle, [_variables(r) for r in dec])
    p0_conf = ST._predire(controle, [_variables(r) for r in conf])
    modeles = {'controle': controle}
    rapport_branches = {}
    for k, (nom, circuits) in enumerate(BRANCHES.items()):
        d = [r for r in dec if r['circuit'] in circuits]
        c = [r for r in conf if r['circuit'] in circuits]
        challenger = ST._ajuster([_variables(r, nom) for r in dec], y_dec)
        modeles[nom] = challenger
        p1_dec = ST._predire(challenger, [_variables(r, nom) for r in dec])
        p1_conf = ST._predire(challenger, [_variables(r, nom) for r in conf])
        indices_d = [i for i, r in enumerate(dec) if r['circuit'] in circuits]
        indices_c = [i for i, r in enumerate(conf) if r['circuit'] in circuits]
        b0_dec = [p0_dec[i] for i in indices_d]
        b0_conf = [p0_conf[i] for i in indices_c]
        b1_dec = [p1_dec[i] for i in indices_d]
        b1_conf = [p1_conf[i] for i in indices_c]
        gains_dec = _gains(d, b0_dec, b1_dec)
        gains_conf = _gains(c, b0_conf, b1_conf)
        ic = ST._ic_gains(c, b0_conf, b1_conf, bootstrap, graine=20261101+k)
        coefficient = (challenger['beta'][-1]/challenger['ecarts'][-1]
                       if challenger and challenger['ecarts'][-1] else 0.0)
        n_duel_dec = _couverture(d)['duels_serveurs']
        n_duel_conf = _couverture(c)['duels_serveurs']
        diagnostique_positif = bool(len(c) >= 100 and n_duel_conf >= 30
                                    and gains_conf['log_loss'] is not None and gains_conf['log_loss'] > 0
                                    and gains_conf['brier'] is not None and gains_conf['brier'] >= 0)
        suivi = bool(diagnostique_positif and len(d) >= 100 and n_duel_dec >= 30
                     and gains_dec['log_loss'] is not None and gains_dec['log_loss'] > 0
                     and gains_dec['brier'] is not None and gains_dec['brier'] >= 0
                     and coefficient > 0)
        rapport_branches[nom] = {
            'circuits': list(circuits), 'couverture_decouverte': _couverture(d),
            'couverture_diagnostic': _couverture(c),
            'decouverte': {'controle_avec_bilan': _metriques(d, b0_dec),
                           'challenger': _metriques(d, b1_dec), 'gains_incrementaux': gains_dec},
            'diagnostic': {'controle_avec_bilan': _metriques(c, b0_conf),
                           'challenger': _metriques(c, b1_conf), 'gains_incrementaux': gains_conf,
                           'ic95_bootstrap_semaine': ic},
            'coefficient_duel_non_standardise': round(coefficient, 8),
            'direction_attendue_sur_decouverte': coefficient > 0,
            'diagnostic_positif': diagnostique_positif,
            'suivi_prospectif_justifie': suivi,
            'activation': False,
            'verdict': ('signal cohérent sur découverte et diagnostic ; suivi prospectif seulement'
                        if suivi else 'signal positif au diagnostic mais insuffisamment cohérent pour un suivi'
                        if diagnostique_positif else 'apport incrémental non démontré ; aucun suivi de cette branche'),
        }
        if nom == 'wta':
            rapport_branches[nom]['duels_diagnostic'] = _duels_wta(c, b0_conf, b1_conf)
    suivies = [nom for nom, b in rapport_branches.items() if b['suivi_prospectif_justifie']]
    return {
        'schema': SCHEMA, 'n': len(rows), 'n_decouverte': len(dec), 'n_diagnostic': len(conf),
        'coupure': coupure.isoformat(),
        'orientation': 'identifiants alphabétiques ; +1 serveur home, -1 serveur away, 0 hors duel',
        'socle_partage': True, 'algorithmes_autonomes_par_circuit': False,
        'reference_incrementale': 'contrôles Elo/service–retour + bilan global ; une correction de branche seulement',
        'branches': rapport_branches, 'branches_avec_suivi_prospectif': suivies,
        'duels': {nom: list(styles) for nom, styles in DUELS.items()},
        'decouverte_globale_controle': _metriques(dec, p0_dec),
        'diagnostic_global_controle': _metriques(conf, p0_conf),
        'convergence': {nom: bool(m and m['converged']) for nom, m in modeles.items()},
        'coefficients_standardises_decouverte': {
            nom: dict(zip(NOMS_BASE, modele['beta'])) for nom, modele in modeles.items() if nom != 'controle' and modele},
        'modeles_complets_decouverte': modeles,
        'nature_diagnostic': '2025–2026 historique réutilisé ; jamais une confirmation prospective nouvelle',
        'selection': 'quatre duels et trois branches fixés avant le calcul ; aucun duel ni meilleur circuit choisi après le diagnostic',
        'marche_utilise': False, 'activation': False, 'champion_actif_modifie': False,
        'regle': 'ridge 1.0 ajusté sur 2024 uniquement ; coefficients figés ; aucune activation automatique',
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('archive')
    parser.add_argument('racine', nargs='?', default='.')
    parser.add_argument('--maximum', type=int, default=8000)
    parser.add_argument('--bootstrap', type=int, default=2000)
    args = parser.parse_args(argv)
    matchs = donnees.charger(args.archive, 2021)
    choisis = PR.selection(matchs, dt.date(2024, 1, 1), args.maximum)
    rows = SV.observations(matchs, choisis)
    out = evaluer(rows, bootstrap=args.bootstrap)
    dossier = os.path.join(args.racine, 'simulateur')
    with open(os.path.join(dossier, 'rapport_serveurs_circuits.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    modele = {
        'schema': SCHEMA, 'gel_utc': GEL_UTC, 'activation': False,
        'ajustement': 'régression logistique ridge 1.0 sur découverte 2024 uniquement',
        'orientation_apprentissage': 'identifiants joueurs par ordre alphabétique',
        'reference': 'socle partagé Elo/service–retour + bilan global ; correction serveur propre à la branche',
        'duels': {nom: list(styles) for nom, styles in DUELS.items()},
        'branches': {nom: list(circuits) for nom, circuits in BRANCHES.items()},
        'branches_suivies': out['branches_avec_suivi_prospectif'],
        'controle': out['modeles_complets_decouverte']['controle'],
        'challengers': {nom: out['modeles_complets_decouverte'][nom] for nom in BRANCHES},
        'nature_diagnostic': out['nature_diagnostic'],
        'confirmation_future': 'nouveaux pronostics figés, appariés au champion et au contrôle partagé ; aucune activation automatique',
    }
    with open(os.path.join(dossier, 'modele_serveurs_circuits.json'), 'w', encoding='utf-8') as f:
        json.dump(modele, f, ensure_ascii=False, indent=2)
    resume = {'n': out['n'], 'branches_avec_suivi_prospectif': out['branches_avec_suivi_prospectif'], 'branches': {
        nom: {'diagnostic': b['diagnostic']['gains_incrementaux'],
              'ic95': b['diagnostic']['ic95_bootstrap_semaine'],
              'coefficient': b['coefficient_duel_non_standardise'],
              'verdict': b['verdict']} for nom, b in out['branches'].items()}}
    print(json.dumps(resume, ensure_ascii=False, indent=2))
    return out


if __name__ == '__main__':
    main()
