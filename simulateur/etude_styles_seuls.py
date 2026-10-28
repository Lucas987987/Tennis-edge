#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Valeur prédictive des bilans de styles seuls, sans autre variable.

Trois petits modèles sont ajustés sur 2024 puis figés : bilan global, bilan de
surface, ou les deux. Leur seule référence est une prévision neutre à 50 %.
Aucun Elo, service–retour, circuit, marché ou réglage du champion n'entre dans
les variables explicatives. La période 2025–2026 est un diagnostic historique
réutilisé, pas une nouvelle confirmation prospective.

Usage : python simulateur/etude_styles_seuls.py /tmp/sackmann . [--maximum 8000]
Sortie : simulateur/rapport_styles_seuls.json
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

CANDIDATS = {
    'global': ('bilan_global',),
    'surface': ('bilan_surface',),
    'global_surface': ('bilan_global', 'bilan_surface'),
}


def _variables(r, candidat):
    """Constante et bilans de styles uniquement : aucune covariable extérieure."""
    return [1.0] + [float(r[nom]) for nom in CANDIDATS[candidat]]


def _couverture(rows):
    n = len(rows)
    globaux = sum(r['documentation_bilans'] > 0 for r in rows)
    surfaces = sum(r['documentation_surface'] > 0 for r in rows)
    return {
        'n': n,
        'deux_bilans_globaux_documentes': {
            'n': globaux, 'pct': round(100 * globaux / n, 2) if n else None},
        'deux_bilans_surface_documentes': {
            'n': surfaces, 'pct': round(100 * surfaces / n, 2) if n else None},
        'regle': 'documentation positive pour chacun des deux joueurs ; sinon contraction vers 50 %',
    }


def _bloc(y, rows, predictions, neutres):
    return {
        'neutre_50': ST._metriques(y, neutres),
        'profils_seuls': ST._metriques(y, predictions),
        'gains_contre_neutre': ST._gains(y, neutres, predictions),
    }


def evaluer(rows, coupure=dt.date(2025, 1, 1), bootstrap=2000):
    dec = [r for r in rows if r['date'] < coupure]
    conf = [r for r in rows if r['date'] >= coupure]
    y_dec, y_conf = [r['y'] for r in dec], [r['y'] for r in conf]
    neutre_dec, neutre_conf = [.5] * len(dec), [.5] * len(conf)
    resultats, modeles, predictions_conf = {}, {}, {}
    for candidat in CANDIDATS:
        modele = ST._ajuster([_variables(r, candidat) for r in dec], y_dec)
        modeles[candidat] = modele
        p_dec = ST._predire(modele, [_variables(r, candidat) for r in dec])
        p_conf = ST._predire(modele, [_variables(r, candidat) for r in conf])
        predictions_conf[candidat] = p_conf
        bloc = _bloc(y_conf, conf, p_conf, neutre_conf)
        bloc['ic95_bootstrap_semaine'] = ST._ic_gains(conf, neutre_conf, p_conf, bootstrap)
        sous_groupes = {}
        for surface in ('Hard', 'Clay', 'Grass'):
            indices = [i for i, r in enumerate(conf) if r['surface'] == surface]
            if len(indices) < 30:
                continue
            yy = [y_conf[i] for i in indices]
            pp = [p_conf[i] for i in indices]
            nn = [neutre_conf[i] for i in indices]
            sous_groupes[surface] = _bloc(yy, [conf[i] for i in indices], pp, nn)
        resultats[candidat] = {
            'variables': list(CANDIDATS[candidat]),
            'convergence': bool(modele and modele['converged']),
            'coefficients_standardises_decouverte': dict(
                zip(('constante',) + CANDIDATS[candidat], modele['beta'])) if modele else None,
            'modele_complet_decouverte': {
                'beta': modele['beta'], 'moyennes': modele['moyennes'],
                'ecarts': modele['ecarts'], 'converged': modele['converged'],
            } if modele else None,
            'decouverte': _bloc(y_dec, dec, p_dec, neutre_dec),
            'confirmation': bloc,
            'surfaces_confirmation': sous_groupes,
        }
    return {
        'schema': 'styles_seuls_v1',
        'n': len(rows), 'n_decouverte': len(dec), 'n_confirmation': len(conf),
        'coupure': coupure.isoformat(),
        'orientation': 'ordre alphabétique des identifiants, indépendant du résultat',
        'reference': 'probabilité neutre de 50 % pour chaque match',
        'variables_explicatives_autorisees': ['bilan_global', 'bilan_surface'],
        'variables_exclues': [
            'Elo', 'service–retour pur', 'interaction service–retour', 'circuit',
            'marché et cotes', 'documentation comme prédicteur', 'autres facteurs du champion'],
        'surface_utilisation': 'bilan de surface dans les candidats surface et global_surface ; jamais comme covariable extérieure',
        'ajustement': 'régression logistique ridge 1.0 sur 2024 seulement ; coefficients figés ensuite',
        'prior_matchs_par_bilan': SV.PRIOR_MATCHS,
        'couverture': {
            'global': _couverture(rows), 'decouverte': _couverture(dec), 'confirmation': _couverture(conf)},
        'resultats': resultats,
        'comparaison_surface_incrementale_dans_profils': {
            'reference': 'global', 'challenger': 'global_surface',
            'gains': ST._gains(y_conf, predictions_conf['global'], predictions_conf['global_surface']),
            'ic95_bootstrap_semaine': ST._ic_gains(
                conf, predictions_conf['global'], predictions_conf['global_surface'], bootstrap),
            'sens': 'positif = apport du bilan de surface en plus du bilan global ; profils uniquement',
        },
        'nature_confirmation': 'diagnostic historique 2025–2026 réutilisé ; pas une confirmation prospective nouvelle',
        'marche_utilise': False,
        'activation': False,
        'champion_actif_modifie': False,
        'verdict': 'diagnostic des profils seuls terminé ; aucune activation automatique et champion inchangé',
        'regle': 'résultats versés après la date seulement ; aucun résultat futur ; aucune modification du modèle actif',
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
    rows = SV.observations(M, choisis)
    out = evaluer(rows, bootstrap=args.bootstrap)
    path = os.path.join(args.racine, 'simulateur', 'rapport_styles_seuls.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps({
        'n': out['n'], 'n_decouverte': out['n_decouverte'], 'n_confirmation': out['n_confirmation'],
        'confirmation': {nom: {
            'profils_seuls': bloc['confirmation']['profils_seuls'],
            'gains_contre_neutre': bloc['confirmation']['gains_contre_neutre'],
            'ic95_log_loss': bloc['confirmation']['ic95_bootstrap_semaine']['log_loss'],
        } for nom, bloc in out['resultats'].items()},
        'verdict': out['verdict'],
    }, ensure_ascii=False, indent=2))
    return out


if __name__ == '__main__':
    main()
