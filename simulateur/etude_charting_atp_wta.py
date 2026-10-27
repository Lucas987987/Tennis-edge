#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gel du challenger Match Charting ATP/WTA après repérage post hoc.

Le modèle est ajusté sur la découverte 2024 seulement. Les résultats 2025–2026
sont rappelés comme origine du candidat, jamais comme confirmation. L'exécution
ne modifie aucun réglage actif et n'active pas le challenger.
"""
import argparse
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import charting as CH  # noqa: E402
import charting_atp_wta as CAW  # noqa: E402
import donnees  # noqa: E402
import etude_pistes as EP  # noqa: E402
import pistes_observations as PO  # noqa: E402
import profils_robustes as PR  # noqa: E402
import styles_joueurs as ST  # noqa: E402


def construire(rows):
    couverts = [r for r in rows if r['date'] < EP.COUPURE and r['circuit'] in CAW.CIRCUITS
                and r['mcp_deux_joueurs_couverts']]
    if len(couverts) < 100:
        raise ValueError(f'Moins de 100 matchs ATP/WTA couverts dans la découverte : {len(couverts)}')
    controle = EP._fit(couverts)
    challenger = EP._fit(couverts, CAW.VARIABLES)
    if not controle or not challenger or not controle['converged'] or not challenger['converged']:
        raise ValueError('La régression de découverte n’a pas convergé ; aucun modèle figé.')
    y = [r['y'] for r in couverts]
    p0, p1 = EP._predire(controle, couverts), EP._predire(challenger, couverts, CAW.VARIABLES)
    modele = {'schema': CAW.SCHEMA, 'gel_utc': CAW.GEL_UTC, 'activation': False,
              'selection_sous_groupe': 'post hoc sur le diagnostic 2025–2026 ; nouvelle confirmation obligatoire',
              'ajustement': 'régression logistique ridge 1.0 sur ATP/WTA couverts de 2024 uniquement',
              'variables': CAW.VARIABLES, 'priors_charting': {'service': 300.0, 'retour': 300.0, 'echanges': 600.0},
              'controle': controle, 'challenger': challenger}
    rapport = {'schema': CAW.SCHEMA, 'n_decouverte_atp_wta_couvert': len(couverts),
               'controle_decouverte': ST._metriques(y, p0), 'challenger_decouverte': ST._metriques(y, p1),
               'gains_decouverte_dans_echantillon': EP._gains_bruts(y, p0, p1),
               'activation': False, 'champion_actif_modifie': False,
               'confirmation_future': {'minimum_matchs': 1000, 'minimum_semaines_iso': 8,
                                       'debut_apres': CAW.GEL_UTC, '2025_2026_exclus': True}}
    return modele, rapport


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('archive')
    ap.add_argument('mcp')
    ap.add_argument('racine', nargs='?', default='.')
    ap.add_argument('--maximum', type=int, default=16000)
    args = ap.parse_args(argv)
    M_tout = donnees.charger(args.archive, 2021)
    # Même tirage déterministe que l'étude initiale ; les années ultérieures ne
    # servent qu'à reproduire sa sélection, jamais à ajuster le candidat.
    choisis = PR.selection(M_tout, dt.date(2024, 1, 1), args.maximum)
    M = [m for m in M_tout if m['date'] < EP.COUPURE]
    donnees_mcp = CH.charger(args.mcp)
    if not donnees_mcp:
        raise SystemExit('Aucune donnée Match Charting : aucun modèle et aucune imputation.')
    rows = PO.observations(M, choisis, charting=CH.Charting(donnees_mcp))
    modele, rapport = construire(rows)
    declencheur = {}
    try:
        ancien = json.load(open(os.path.join(args.racine, 'simulateur', 'rapport_charting_couverture.json'),
                                encoding='utf-8'))
        groupes = ancien['resultat']['challenger']['sous_groupes_confirmation']
        declencheur = {c: groupes.get(f'circuit:{c}') for c in CAW.CIRCUITS}
    except (OSError, ValueError, KeyError):
        pass
    rapport.update({'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                    'diagnostic_declencheur_post_hoc': declencheur,
                    'avertissement': 'Le diagnostic déclencheur est réutilisé et ne constitue pas une confirmation.',
                    'source': 'Match Charting Project, Jeff Sackmann et contributeurs, CC BY-NC-SA 4.0 ; archive Sackmann, même licence',
                    'marche_utilise': False})
    for nom, objet in ((CAW.FICHIER_MODELE, modele),
                       (os.path.join('simulateur', 'rapport_charting_atp_wta.json'), rapport)):
        chemin = os.path.join(args.racine, nom)
        with open(chemin, 'w', encoding='utf-8') as f:
            json.dump(objet, f, ensure_ascii=False, indent=2)
    print(json.dumps(rapport, ensure_ascii=False, indent=2))
    return modele, rapport


if __name__ == '__main__':
    main()
