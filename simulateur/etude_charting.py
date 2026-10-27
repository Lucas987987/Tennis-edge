#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Valeur prédictive Match Charting sur les seuls matchs réellement couverts.

La couverture non aléatoire est mesurée et le contrôle est réestimé sur le même
sous-échantillon. Aucun zéro de repli n'est interprété comme une observation
tactique. 2025–2026 reste un diagnostic réutilisé, sans activation.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import charting as CH  # noqa: E402
import donnees  # noqa: E402
import etude_pistes as EP  # noqa: E402
import pistes_observations as PO  # noqa: E402
import profils_robustes as PR  # noqa: E402
import styles_joueurs as ST  # noqa: E402

VARIABLES = ['mcp_premier_coup_ecart', 'mcp_retour_ecart', 'mcp_duel_ecart', 'mcp_echanges_ecart']


def _couverture(rows):
    def bloc(part):
        n = len(part)
        k = sum(r['mcp_deux_joueurs_couverts'] for r in part)
        return {'n': n, 'deux_joueurs_couverts': k,
                'couverture_pct': round(100 * k / n, 2) if n else None}
    return {'global': bloc(rows), 'decouverte_2024': bloc([r for r in rows if r['date'] < EP.COUPURE]),
            'diagnostic_2025_2026': bloc([r for r in rows if r['date'] >= EP.COUPURE]),
            'par_circuit': {c: bloc([r for r in rows if r['circuit'] == c]) for c in ('ATP', 'WTA', 'CH', 'ITF')},
            'avertissement': 'Les matchs chartés ne sont pas un échantillon aléatoire ; le gain couvert ne se généralise pas automatiquement.'}


def evaluer(rows, bootstrap=2000):
    couverts = [r for r in rows if r['mcp_deux_joueurs_couverts']]
    dec = [r for r in couverts if r['date'] < EP.COUPURE]
    conf = [r for r in couverts if r['date'] >= EP.COUPURE]
    out = {'couverture': _couverture(rows), 'activation': False, 'confirmation_future_requise': True}
    if len(dec) < 100 or len(conf) < 100:
        out.update({'evalue': False, 'raison': f'moins de 100 matchs couverts par période ({len(dec)}, {len(conf)})',
                    'verdict': 'données insuffisantes ; champion inchangé'})
        return out
    controle = EP._fit(dec)
    p0d, p0c = EP._predire(controle, dec), EP._predire(controle, conf)
    modele = EP._fit(dec, VARIABLES)
    pd, pc = EP._predire(modele, dec, VARIABLES), EP._predire(modele, conf, VARIABLES)
    bloc = EP._rapport_challenger(dec, conf, pd, pc, p0d, p0c, bootstrap, 20261031)
    bloc['criteres_historiques_satisfaits'] = bloc['apport_confirme']
    bloc['apport_confirme'] = False
    bloc['verdict'] = ('signal historique sur le sous-échantillon couvert ; confirmation future et contrôle de couverture requis'
                       if bloc['criteres_historiques_satisfaits'] else 'apport tactique non établi ; champion inchangé')
    bloc['coefficients_standardises_decouverte'] = dict(zip(EP.NOMS_CONTROLE + VARIABLES, modele['beta']))
    out.update({'evalue': True, 'n_decouverte_couvert': len(dec), 'n_diagnostic_couvert': len(conf),
                'controle_diagnostic': ST._metriques([r['y'] for r in conf], p0c), 'challenger': bloc})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('archive')
    ap.add_argument('mcp')
    ap.add_argument('racine', nargs='?', default='.')
    ap.add_argument('--maximum', type=int, default=16000)
    ap.add_argument('--bootstrap', type=int, default=2000)
    ap.add_argument('--sortie')
    args = ap.parse_args(argv)
    debut = time.time()
    donnees_mcp = CH.charger(args.mcp)
    if not donnees_mcp:
        raise SystemExit('Aucune donnée Match Charting lisible : aucune évaluation et aucune imputation.')
    M = donnees.charger(args.archive, 2021)
    choisis = PR.selection(M, dt.date(2024, 1, 1), args.maximum)
    charting = CH.Charting(donnees_mcp)
    rows = PO.observations(M, choisis, charting=charting)
    resultat = evaluer(rows, args.bootstrap)
    out = {'schema': 'charting_couverture_v1', 'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'source': 'Match Charting Project, Jeff Sackmann et contributeurs, CC BY-NC-SA 4.0 ; archive Sackmann, même licence',
           'joueurs_chartes': len(donnees_mcp), 'variables': VARIABLES,
           'temporalite': 'relevés strictement antérieurs à la date du match ; aucun résultat courant',
           'marche_utilise': False, 'diagnostic_reutilise': True, 'resultat': resultat,
           'champion_actif_modifie': False, 'duree_s': round(time.time() - debut)}
    chemin = os.path.join(args.racine, 'simulateur', 'rapport_charting_couverture.json')
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    if args.sortie:
        with open(args.sortie, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


if __name__ == '__main__':
    main()
