#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Valeur ATP/WTA de la fréquence et de la réussite par tranche d'échange.

Ajustement sur 2024 seulement ; 2025–2026 est un diagnostic réutilisé. Aucun
marché, aucune activation et aucune modification du champion.
"""
import argparse
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import charting as CH  # noqa: E402
import charting_echanges as CE  # noqa: E402
import donnees  # noqa: E402
import etude_charting as EC  # noqa: E402
import etude_pistes as EP  # noqa: E402
import pistes_observations as PO  # noqa: E402
import profils_robustes as PR  # noqa: E402
import styles_joueurs as ST  # noqa: E402

FIN_HISTORIQUE = dt.date(2026, 10, 28)
FICHIER_MODELE = os.path.join('simulateur', 'modele_echanges_atp_wta.json')
FICHIER_RAPPORT = os.path.join('simulateur', 'rapport_echanges_atp_wta.json')
CIRCUITS = ('ATP', 'WTA')


def construire(rows, bootstrap=2000):
    couverts = [r for r in rows if r['circuit'] in CIRCUITS and r.get('echanges_deux_joueurs_couverts')]
    dec = [r for r in couverts if r['date'] < EP.COUPURE]
    diagnostic = [r for r in couverts if EP.COUPURE <= r['date'] < FIN_HISTORIQUE]
    if len(dec) < 100:
        raise ValueError(f'Moins de 100 matchs ATP/WTA couverts dans la découverte : {len(dec)}')
    ajouts = {'controle': [], 'mcp_existant': EC.VARIABLES,
              'tranches_echanges': CE.VARIABLES,
              'mcp_plus_tranches': EC.VARIABLES + CE.VARIABLES}
    modeles = {nom: EP._fit(dec, vars_) for nom, vars_ in ajouts.items()}
    if not all(m and m['converged'] for m in modeles.values()):
        raise ValueError('Une régression de découverte n’a pas convergé ; aucun modèle figé.')
    modele = {'schema': CE.SCHEMA, 'gel_utc': CE.GEL_UTC, 'activation': False,
              'ajustement': 'régressions logistiques ridge 1.0 sur ATP/WTA couverts de 2024 uniquement',
              'variables_tranches': CE.VARIABLES, 'variables_mcp_existant': EC.VARIABLES,
              'tranches': CE.TRANCHES, 'demi_vie_jours': CE.DEMI_VIE_J,
              'prior_reussite_points': CE.PRIOR_REUSSITE, 'prior_frequence_points': CE.PRIOR_FREQUENCE,
              'selection': 'deux joueurs ayant des relevés Rally strictement antérieurs',
              'modeles': modeles}

    def predictions(part):
        return {nom: EP._predire(modeles[nom], part, vars_) for nom, vars_ in ajouts.items()}

    def gains(y, p):
        return {'tranches_moins_controle': EP._gains_bruts(y, p['controle'], p['tranches_echanges']),
                'combine_moins_controle': EP._gains_bruts(y, p['controle'], p['mcp_plus_tranches']),
                'combine_moins_mcp_existant': EP._gains_bruts(y, p['mcp_existant'], p['mcp_plus_tranches']),
                'combine_moins_tranches': EP._gains_bruts(y, p['tranches_echanges'], p['mcp_plus_tranches'])}

    p_dec = predictions(dec)
    y_dec = [r['y'] for r in dec]
    rapport = {
        'schema': CE.SCHEMA, 'activation': False, 'champion_actif_modifie': False, 'marche_utilise': False,
        'n_decouverte_atp_wta_couvert': len(dec),
        'decouverte_dans_echantillon': {nom: ST._metriques(y_dec, p) for nom, p in p_dec.items()},
        'gains_decouverte': gains(y_dec, p_dec),
        'couverture_atp_wta': {
            'n': len([r for r in rows if r['circuit'] in CIRCUITS]),
            'deux_joueurs_couverts': len(couverts),
            'couverture_pct': round(100 * len(couverts) / len([r for r in rows if r['circuit'] in CIRCUITS]), 2)
                              if any(r['circuit'] in CIRCUITS for r in rows) else None,
            'avertissement': 'relevés non aléatoires ; résultats limités aux matchs couverts'},
        'confirmation_future': {'minimum_matchs': 1000, 'minimum_semaines_iso': 8,
                                'debut_apres': CE.GEL_UTC, '2025_2026_exclus': True},
        'limite_controle': 'contrôle de recherche, pas le champion complet',
    }
    if diagnostic:
        p = predictions(diagnostic)
        y = [r['y'] for r in diagnostic]
        rapport['diagnostic_historique_reutilise'] = {
            'n': len(diagnostic), 'metriques': {nom: ST._metriques(y, pred) for nom, pred in p.items()},
            'gains': gains(y, p),
            'combine_contre_controle': {
                'ic95_bootstrap_semaine': EP._ic_gains(diagnostic, p['controle'], p['mcp_plus_tranches'], bootstrap, 20261110),
                'sous_groupes': EP._sous_groupes(diagnostic, y, p['controle'], p['mcp_plus_tranches'])},
            'combine_contre_mcp_existant': {
                'ic95_bootstrap_semaine': EP._ic_gains(diagnostic, p['mcp_existant'], p['mcp_plus_tranches'], bootstrap, 20261111)},
            'confirmation': False,
            'avertissement': 'Diagnostic historique réutilisé : ni confirmation prospective ni activation.'}
    return modele, rapport


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('archive')
    ap.add_argument('mcp')
    ap.add_argument('racine', nargs='?', default='.')
    ap.add_argument('--maximum', type=int, default=16000)
    ap.add_argument('--bootstrap', type=int, default=2000)
    args = ap.parse_args(argv)
    M_tout = donnees.charger(args.archive, 2021)
    choisis = PR.selection(M_tout, dt.date(2024, 1, 1), args.maximum)
    M = [m for m in M_tout if m['date'] < FIN_HISTORIQUE]
    donnees_mcp = CH.charger(args.mcp)
    donnees_echanges = CE.charger(args.mcp)
    if not donnees_mcp or not donnees_echanges:
        raise SystemExit('Données Match Charting incomplètes : aucune imputation.')
    rows = PO.observations(M, choisis, charting=CH.Charting(donnees_mcp),
                           echanges=CE.Echanges(donnees_echanges))
    modele, rapport = construire(rows, args.bootstrap)
    rapport.update({'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                    'source': 'Match Charting Project, Jeff Sackmann et contributeurs, CC BY-NC-SA 4.0 ; archive Sackmann, même licence',
                    'protocole': {'orientation': 'ordre alphabétique, indépendant du résultat',
                                  'temporalite': 'relevés strictement antérieurs ; résultats versés au changement de date',
                                  'decouverte': '2024', 'diagnostic_reutilise': '2025–2026',
                                  'marche_utilise': False, 'activation_automatique': False}})
    for nom, objet in ((FICHIER_MODELE, modele), (FICHIER_RAPPORT, rapport)):
        with open(os.path.join(args.racine, nom), 'w', encoding='utf-8') as f:
            json.dump(objet, f, ensure_ascii=False, indent=2)
    print(json.dumps(rapport, ensure_ascii=False, indent=2))
    return modele, rapport


if __name__ == '__main__':
    main()
