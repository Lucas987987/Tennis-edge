#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnostic du challenger pression V2, sans marché ni activation.

Ajustement sur 2024 seulement. La période 2025–2026 est un diagnostic historique
réutilisé, jamais une nouvelle confirmation prospective.
"""
import argparse
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees  # noqa: E402
import pistes_observations as PO  # noqa: E402
import pression_v2 as PV2  # noqa: E402
import profils_robustes as PR  # noqa: E402
import styles_joueurs as ST  # noqa: E402

COUPURE_DECOUVERTE = dt.date(2025, 1, 1)
FIN_HISTORIQUE = dt.date(2026, 10, 28)
FICHIER_MODELE = os.path.join('simulateur', 'modele_pression_v2.json')
FICHIER_RAPPORT = os.path.join('simulateur', 'rapport_pression_v2.json')


def _x(row, ajouts=()):
    return ST._variables(row) + [float(row[nom]) for nom in ajouts]


def _fit(rows, ajouts=()):
    return ST._ajuster([_x(r, ajouts) for r in rows], [r['y'] for r in rows])


def _gains(y, sans, avec):
    out = ST._gains(y, sans, avec)
    out['sens'] = 'positif = apport du second modèle'
    return out


def _predire(modele, rows, ajouts=()):
    return ST._predire(modele, [_x(r, ajouts) for r in rows])


def _sous_groupes(rows, p0, p1):
    tests = [('global', lambda r: True)]
    tests += [(f'circuit:{c}', lambda r, c=c: r['circuit'] == c) for c in ('ATP', 'WTA', 'CH', 'ITF')]
    tests += [(f'surface:{s}', lambda r, s=s: r['surface'] == s) for s in ('Hard', 'Clay', 'Grass')]
    tests += [('annee:2025', lambda r: r['date'].year == 2025),
              ('annee:2026', lambda r: r['date'].year == 2026),
              ('documentation:moins_500_balles', lambda r: r['documentation_balles'] < 500),
              ('documentation:moins_10_matchs_elo', lambda r: r['documentation_matchs'] < 10)]
    out = {}
    for nom, test in tests:
        part = [(r, a, b) for r, a, b in zip(rows, p0, p1) if test(r)]
        if nom != 'global' and len(part) < 30:
            continue
        y = [r['y'] for r, _, _ in part]
        sans = [a for _, a, _ in part]
        avec = [b for _, _, b in part]
        out[nom] = {'controle': ST._metriques(y, sans), 'challenger': ST._metriques(y, avec),
                    'gains': _gains(y, sans, avec)}
    return out


def construire(rows, bootstrap=2000):
    dec = [r for r in rows if r['date'] < COUPURE_DECOUVERTE]
    diagnostic = [r for r in rows if COUPURE_DECOUVERTE <= r['date'] < FIN_HISTORIQUE]
    if len(dec) < 100:
        raise ValueError(f'Moins de 100 matchs dans la découverte : {len(dec)}')
    modeles = {
        'controle': _fit(dec),
        'pression_v1': _fit(dec, PV2.VARIABLES_V1),
        'pression_v2': _fit(dec, PV2.VARIABLES),
    }
    if not all(m and m['converged'] for m in modeles.values()):
        raise ValueError('Une régression de découverte n’a pas convergé ; aucun modèle figé.')
    modele = {
        'schema': PV2.SCHEMA, 'gel_utc': PV2.GEL_UTC, 'activation': False,
        'ajustement': 'régressions logistiques ridge 1.0 sur découverte 2024 uniquement',
        'variables': PV2.VARIABLES, 'variables_v1': PV2.VARIABLES_V1,
        'demi_vie_jours': PV2.DEMI_VIE_J, 'priors': PV2.PRIORS,
        'definition': 'résidus Elo pour tie-breaks, sets décisifs et matchs serrés ; résidus aux points ordinaires pour les balles de break',
        'hierarchie': 'global, puis surface et circuit contractés vers le global',
        'modeles': modeles,
    }
    y = [r['y'] for r in dec]
    predictions_dec = {
        'controle': _predire(modeles['controle'], dec),
        'pression_v1': _predire(modeles['pression_v1'], dec, PV2.VARIABLES_V1),
        'pression_v2': _predire(modeles['pression_v2'], dec, PV2.VARIABLES),
    }
    rapport = {
        'schema': PV2.SCHEMA, 'n_decouverte': len(dec),
        'decouverte_dans_echantillon': {
            nom: ST._metriques(y, p) for nom, p in predictions_dec.items()},
        'gains_decouverte': {
            'v1_moins_controle': _gains(y, predictions_dec['controle'], predictions_dec['pression_v1']),
            'v2_moins_controle': _gains(y, predictions_dec['controle'], predictions_dec['pression_v2']),
            'v2_moins_v1': _gains(y, predictions_dec['pression_v1'], predictions_dec['pression_v2']),
        },
        'activation': False, 'champion_actif_modifie': False, 'marche_utilise': False,
        'confirmation_future': {
            'minimum_matchs': 1000, 'minimum_semaines_iso': 8,
            'debut_apres': PV2.GEL_UTC, '2025_2026_exclus': True,
            'statut': 'requise_avant_toute_activation'},
        'limite_controle': 'contrôle de recherche Elo, service–retour, surface, circuit et documentation ; pas le champion complet',
    }
    if diagnostic:
        yy = [r['y'] for r in diagnostic]
        predictions = {
            'controle': _predire(modeles['controle'], diagnostic),
            'pression_v1': _predire(modeles['pression_v1'], diagnostic, PV2.VARIABLES_V1),
            'pression_v2': _predire(modeles['pression_v2'], diagnostic, PV2.VARIABLES),
        }
        rapport['diagnostic_historique_reutilise'] = {
            'n': len(diagnostic),
            'metriques': {nom: ST._metriques(yy, p) for nom, p in predictions.items()},
            'gains': {
                'v1_moins_controle': _gains(yy, predictions['controle'], predictions['pression_v1']),
                'v2_moins_controle': _gains(yy, predictions['controle'], predictions['pression_v2']),
                'v2_moins_v1': _gains(yy, predictions['pression_v1'], predictions['pression_v2']),
            },
            'v2_contre_controle': {
                'ic95_bootstrap_semaine': ST._ic_gains(
                    diagnostic, predictions['controle'], predictions['pression_v2'], bootstrap),
                'sous_groupes': _sous_groupes(diagnostic, predictions['controle'], predictions['pression_v2']),
            },
            'v2_contre_v1': {
                'ic95_bootstrap_semaine': ST._ic_gains(
                    diagnostic, predictions['pression_v1'], predictions['pression_v2'], bootstrap),
            },
            'confirmation': False,
            'avertissement': 'Période historique déjà utilisée par la recherche : ni confirmation vierge ni activation.',
        }
    return modele, rapport


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('archive')
    ap.add_argument('racine', nargs='?', default='.')
    ap.add_argument('--maximum', type=int, default=16000)
    ap.add_argument('--bootstrap', type=int, default=2000)
    args = ap.parse_args(argv)
    M_tout = donnees.charger(args.archive, 2021)
    choisis = PR.selection(M_tout, dt.date(2024, 1, 1), args.maximum)
    M = [m for m in M_tout if m['date'] < FIN_HISTORIQUE]
    rows = PO.observations(M, choisis, avec_pression_v2=True)
    modele, rapport = construire(rows, args.bootstrap)
    rapport.update({
        'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'source': 'Archive Jeff Sackmann, CC BY-NC-SA 4.0, usage non commercial et attribution requis',
        'protocole': {
            'n': len(rows), 'n_decouverte': len([r for r in rows if r['date'] < COUPURE_DECOUVERTE]),
            'n_diagnostic_reutilise': len([r for r in rows if COUPURE_DECOUVERTE <= r['date'] < FIN_HISTORIQUE]),
            'orientation': 'ordre alphabétique des identifiants, indépendant du résultat',
            'temporalite': 'résultats versés au changement de date ; aucun résultat du même jour',
            'controles': ['Elo général et surface', 'service–retour pur', 'surface', 'circuit', 'documentation'],
            'marche_utilise': False, 'activation_automatique': False,
        },
    })
    for nom, objet in ((FICHIER_MODELE, modele), (FICHIER_RAPPORT, rapport)):
        with open(os.path.join(args.racine, nom), 'w', encoding='utf-8') as f:
            json.dump(objet, f, ensure_ascii=False, indent=2)
    print(json.dumps(rapport, ensure_ascii=False, indent=2))
    return modele, rapport


if __name__ == '__main__':
    main()
