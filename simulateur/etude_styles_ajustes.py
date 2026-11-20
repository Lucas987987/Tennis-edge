#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gel du challenger de bilans de styles ajustés au niveau Elo pré-match.

Ajustement sur 2024 seulement. Le diagnostic 2025–2026 est rappelé à titre
historique, jamais comme confirmation : celle-ci utilise uniquement le journal
des pronostics réellement nouveaux postérieurs au gel.
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
import styles_ajustes as SA  # noqa: E402
import styles_joueurs as ST  # noqa: E402
import styles_valeur as SV  # noqa: E402

COUPURE_DECOUVERTE = dt.date(2025, 1, 1)
FIN_HISTORIQUE = dt.date(2026, 10, 28)


def _x(row, challenger=False):
    x = ST._variables(row)
    return x + [float(row[nom]) for nom in SA.VARIABLES] if challenger else x


def construire(rows, bootstrap=2000):
    eligibles = [r for r in rows if 'indetermine' not in r['paire_styles']]
    dec = [r for r in eligibles if r['date'] < COUPURE_DECOUVERTE]
    diagnostic = [r for r in eligibles if r['date'] >= COUPURE_DECOUVERTE]
    if len(dec) < 100:
        raise ValueError(f'Moins de 100 matchs documentés dans la découverte : {len(dec)}')
    y = [r['y'] for r in dec]
    controle = ST._ajuster([_x(r) for r in dec], y)
    challenger = ST._ajuster([_x(r, True) for r in dec], y)
    if not all(m and m['converged'] for m in (controle, challenger)):
        raise ValueError('La régression de découverte n’a pas convergé ; aucun modèle figé.')
    modele = {'schema': SA.SCHEMA, 'gel_utc': SA.GEL_UTC, 'activation': False,
              'ajustement': 'régression logistique ridge 1.0 sur découverte 2024 uniquement',
              'variables': SA.VARIABLES, 'reference_residu': 'résultat moins probabilité Elo pré-match',
              'demi_vie_jours': SA.DEMI_VIE_J, 'prior_matchs_equivalents': SA.PRIOR_MATCHS,
              'controle': controle, 'challenger': challenger}
    p0, p1 = ST._predire(controle, [_x(r) for r in dec]), ST._predire(challenger, [_x(r, True) for r in dec])
    rapport = {'schema': SA.SCHEMA, 'n_decouverte': len(dec),
               'controle_decouverte': ST._metriques(y, p0), 'challenger_decouverte': ST._metriques(y, p1),
               'gains_decouverte_dans_echantillon': ST._gains(y, p0, p1),
               'activation': False, 'champion_actif_modifie': False, 'marche_utilise': False,
               'confirmation_future': {'minimum_matchs': 1000, 'minimum_semaines_iso': 8,
                                       'debut_apres': SA.GEL_UTC, '2025_2026_exclus': True}}
    if diagnostic:
        yy = [r['y'] for r in diagnostic]
        q0 = ST._predire(controle, [_x(r) for r in diagnostic])
        q1 = ST._predire(challenger, [_x(r, True) for r in diagnostic])
        rapport['diagnostic_historique_reutilise'] = {
            'n': len(diagnostic), 'controle': ST._metriques(yy, q0), 'challenger': ST._metriques(yy, q1),
            'gains': ST._gains(yy, q0, q1), 'ic95_bootstrap_semaine': ST._ic_gains(diagnostic, q0, q1, bootstrap),
            'confirmation': False,
            'avertissement': 'Période historique réutilisée : ni activation ni confirmation prospective.'}
    return modele, rapport


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('archive')
    ap.add_argument('racine', nargs='?', default='.')
    ap.add_argument('--maximum', type=int, default=8000)
    ap.add_argument('--bootstrap', type=int, default=2000)
    args = ap.parse_args(argv)
    M_tout = donnees.charger(args.archive, 2021)
    # Reproduit l’échantillon de styles_valeur avant de limiter l’étude au passé.
    choisis = PR.selection(M_tout, dt.date(2024, 1, 1), args.maximum)
    M = [m for m in M_tout if m['date'] < FIN_HISTORIQUE]
    rows = SV.observations(M, choisis)
    modele, rapport = construire(rows, args.bootstrap)
    rapport.update({'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                    'controles': ['Elo général et surface', 'service–retour pur', 'surface', 'circuit',
                                  'documentation service et Elo'],
                    'source': 'Archive Sackmann et feuilles pré-match, CC BY-NC-SA 4.0',
                    'regle': 'résidus Elo figés avant chaque résultat ; aucune cote ; aucune activation automatique'})
    for nom, objet in ((SA.FICHIER_MODELE, modele),
                       (os.path.join('simulateur', 'rapport_styles_ajustes.json'), rapport)):
        with open(os.path.join(args.racine, nom), 'w', encoding='utf-8') as f:
            json.dump(objet, f, ensure_ascii=False, indent=2)
    print(json.dumps(rapport, ensure_ascii=False, indent=2))
    return modele, rapport


if __name__ == '__main__':
    main()
