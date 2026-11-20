#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ablation des cinq pistes d'amélioration, sans marché ni activation automatique.

Usage : python simulateur/etude_pistes.py /tmp/sackmann . --maximum 16000
Découverte : 2024. Confirmation : à partir du 1er janvier 2025. La combinaison
n'utilise que des familles dont le gain est positif sur la découverte ; elle est
ensuite jugée une fois sur la confirmation. Aucun résultat ne promeut le champion.
"""
import argparse
import datetime as dt
import json
import math
import os
import random
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees  # noqa: E402
import elo_recherche as ER  # noqa: E402
import pistes_observations as PO  # noqa: E402
import profils_robustes as PR  # noqa: E402
import styles_joueurs as ST  # noqa: E402

COUPURE = dt.date(2025, 1, 1)
MARGE_LOG_LOSS = .001
FAMILLES = {
    'calendrier_fatigue_absence': [
        'fatigue_repos_log', 'fatigue_matchs_7j', 'fatigue_matchs_14j',
        'fatigue_minutes_7j', 'fatigue_minutes_14j', 'fatigue_tournois_14j',
        'fatigue_enchainement_7j', 'fatigue_bo5_30j', 'fatigue_derniere_duree',
        'fatigue_derniers_jeux', 'fatigue_transition_surface',
        'fatigue_retour_absence_30j', 'fatigue_retour_absence_60j',
        'fatigue_retour_absence_90j'],
    'conditions_tournoi': [
        'conditions_aces_x_profil', 'conditions_service_retour',
        'conditions_tiebreak_x_service', 'conditions_longueur_x_endurance',
        'conditions_minutes_x_endurance'],
    'gauchers_et_h2h': [
        'main_gaucher_contre_droitier', 'main_bilan_contre_main',
        'main_donnee_manquante', 'h2h_global', 'h2h_surface_increment'],
    'matchs_serres_pression': [
        'pression_tiebreak', 'pression_decisif', 'pression_proche',
        'pression_bp_service', 'pression_bp_retour'],
}
NOMS_CONTROLE = ['constante', 'elo', 'service_retour', 'terre', 'gazon', 'wta', 'challenger', 'itf',
                 'documentation_balles', 'documentation_matchs', 'moins_500_balles']


def _variables(r, ajouts=(), elo=None):
    base = dict(r)
    if elo is not None:
        base['elo'] = elo
    return ST._variables(base) + [float(r[nom]) for nom in ajouts]


def _fit(dec, ajouts=(), elo=None):
    return ST._ajuster([_variables(r, ajouts, elo) for r in dec], [r['y'] for r in dec])


def _predire(modele, rows, ajouts=(), predictions_elo=None):
    X = []
    for r in rows:
        p_elo = predictions_elo.get(r['uid']) if predictions_elo else None
        X.append(_variables(r, ajouts, p_elo))
    return ST._predire(modele, X)


def _gains_bruts(y, sans, avec):
    ll = brier = 0.0
    for cible, p0, p1 in zip(y, sans, avec):
        p0 = min(max(p0, 1e-12), 1 - 1e-12)
        p1 = min(max(p1, 1e-12), 1 - 1e-12)
        ll += -math.log(p0 if cible else 1 - p0) + math.log(p1 if cible else 1 - p1)
        brier += (p0 - cible) ** 2 - (p1 - cible) ** 2
    return {'log_loss': round(ll / len(y), 6) if y else None,
            'brier': round(brier / len(y), 6) if y else None,
            'sens': 'positif = apport du challenger'}


def _ic_gains(rows, sans, avec, repetitions, graine):
    """Bootstrap par semaine ISO, agrégé pour ne pas recalculer chaque régression."""
    semaines = sorted({r['semaine'] for r in rows})
    if repetitions <= 0 or len(semaines) < 2:
        return {'log_loss': None, 'brier': None}
    groupes = {s: [] for s in semaines}
    for i, r in enumerate(rows):
        groupes[r['semaine']].append(i)
    agregats = {}
    for semaine, indices in groupes.items():
        n = len(indices)
        ll = brier = 0.0
        for i in indices:
            cible, p0, p1 = rows[i]['y'], sans[i], avec[i]
            p0 = min(max(p0, 1e-12), 1 - 1e-12)
            p1 = min(max(p1, 1e-12), 1 - 1e-12)
            ll += -math.log(p0 if cible else 1 - p0) + math.log(p1 if cible else 1 - p1)
            brier += (p0 - cible) ** 2 - (p1 - cible) ** 2
        agregats[semaine] = (n, ll, brier)
    rnd = random.Random(graine)
    valeurs = {'log_loss': [], 'brier': []}
    for _ in range(repetitions):
        n = ll = brier = 0.0
        for semaine in (rnd.choice(semaines) for _ in semaines):
            ni, lli, bi = agregats[semaine]
            n += ni
            ll += lli
            brier += bi
        valeurs['log_loss'].append(ll / n)
        valeurs['brier'].append(brier / n)
    out = {}
    for nom, valeurs_triees in valeurs.items():
        valeurs_triees.sort()
        out[nom] = {'bas': round(valeurs_triees[int(.025 * (repetitions - 1))], 6),
                    'haut': round(valeurs_triees[int(.975 * (repetitions - 1))], 6)}
    return out


def _sous_groupes(rows, y, sans, avec):
    tests = [('global', lambda r: True)]
    tests += [(f'circuit:{c}', lambda r, c=c: r['circuit'] == c) for c in ('ATP', 'WTA', 'CH', 'ITF')]
    tests += [(f'surface:{s}', lambda r, s=s: r['surface'] == s) for s in ('Hard', 'Clay', 'Grass')]
    tests += [(f'annee:{a}', lambda r, a=a: r['date'].year == a) for a in (2025, 2026)]
    tests += [
        ('documentation:moins_500_balles', lambda r: r['documentation_balles'] < 500),
        ('documentation:moins_10_matchs_elo', lambda r: r['documentation_matchs'] < 10),
        ('transition_surface', lambda r: r['transition_surface']),
        ('retour_absence_30j', lambda r: r['retour_absence_30j']),
        ('format:bo5', lambda r: r['bo'] == 5),
    ]
    out = {}
    for nom, test in tests:
        indices = [i for i, r in enumerate(rows) if test(r)]
        if nom != 'global' and len(indices) < 30:
            continue
        yy = [y[i] for i in indices]
        p0 = [sans[i] for i in indices]
        p1 = [avec[i] for i in indices]
        gains = _gains_bruts(yy, p0, p1)
        out[nom] = {'controle': ST._metriques(yy, p0), 'challenger': ST._metriques(yy, p1), 'gains': gains}
    # Diagnostic des surprises : groupe défini après résultat, jamais utilisé pour choisir un réglage.
    indices = [i for i in range(len(rows)) if (sans[i] > .5) != bool(y[i])]
    if len(indices) >= 30:
        yy = [y[i] for i in indices]
        p0, p1 = [sans[i] for i in indices], [avec[i] for i in indices]
        out['defaite_favori_controle'] = {
            'controle': ST._metriques(yy, p0), 'challenger': ST._metriques(yy, p1),
            'gains': _gains_bruts(yy, p0, p1),
            'definition': 'issue contraire au favori du contrôle ; diagnostic descriptif seulement'}
    return out


def _controles_robustesse(sous_groupes):
    out = {}
    for nom in ('circuit:CH', 'documentation:moins_500_balles', 'documentation:moins_10_matchs_elo'):
        bloc = sous_groupes.get(nom)
        if not bloc:
            out[nom] = {'n': 0, 'ok': None, 'raison': 'moins de 30 matchs'}
            continue
        gains = bloc['gains']
        # Tolérance de 0,001 pour ne pas échanger un gain global contre une perte ciblée.
        ok = gains['log_loss'] >= -.001 and gains['brier'] >= -.001
        out[nom] = {'n': bloc['challenger']['n'], 'ok': bool(ok),
                    'gain_log_loss': gains['log_loss'], 'gain_brier': gains['brier'],
                    'tolerance': .001}
    return out


def _couverture(rows):
    """Couverture descriptive ; un zéro légitime n'est pas présenté comme une donnée manquante."""
    sources = {
        'deux_mains_connues': lambda r: r['main_deux_joueurs_connue'],
        'duree_des_deux_derniers_matchs_connue': lambda r: r['fatigue_duree_derniers_matchs_connue'],
        'historique_calendrier_des_deux_joueurs': lambda r: r['fatigue_historique_deux_joueurs'],
        'duree_7j_documentee': lambda r: r['fatigue_documentation_duree_7j'] > 0,
        'bilan_contre_main_documente': lambda r: r['main_documentation'] > 0,
        'h2h_global_documente': lambda r: r['h2h_poids_effectif'] > 0,
        'h2h_surface_documente': lambda r: r['h2h_poids_surface'] > 0,
        'editions_anterieures_du_tournoi': lambda r: r['conditions_matchs_editions'] > 0,
        'tiebreaks_anterieurs_documentes': lambda r: r['pression_documentation_tiebreak'] > 0,
        'sets_decisifs_anterieurs_documentes': lambda r: r['pression_documentation_decisif'] > 0,
        'adversaires_proches_anterieurs_documentes': lambda r: r['pression_documentation_proche'] > 0,
        'balles_de_break_anterieures_documentees': lambda r: r['pression_documentation_bp'] > 0,
    }

    def bloc(lignes):
        n = len(lignes)
        src = {}
        for nom, test in sources.items():
            k = sum(bool(test(r)) for r in lignes)
            src[nom] = {'n': k, 'couverture_pct': round(100 * k / n, 2) if n else None,
                        'manquant_pct': round(100 * (n-k) / n, 2) if n else None}
        variables = {}
        for nom in [v for famille in FAMILLES.values() for v in famille]:
            k = sum(math.isfinite(float(r[nom])) and float(r[nom]) != 0 for r in lignes)
            variables[nom] = {'non_nul_n': k, 'non_nul_pct': round(100*k/n, 2) if n else None,
                              'note': 'fréquence descriptive du signal ; zéro peut être une vraie absence d’écart'}
        return {'n': n, 'sources': src, 'variables': variables}

    return {'global': bloc(rows),
            'decouverte': bloc([r for r in rows if r['date'] < COUPURE]),
            'confirmation': bloc([r for r in rows if r['date'] >= COUPURE]),
            'limite_dates': 'tourney_date est la date de début du tournoi : repos et fenêtres 7/14/30 jours sont des proxys, pas des horodatages de match'}


def _rapport_challenger(dec, conf, p_dec, p_conf, p0_dec, p0_conf, bootstrap, graine):
    y_dec, y_conf = [r['y'] for r in dec], [r['y'] for r in conf]
    gains_dec = _gains_bruts(y_dec, p0_dec, p_dec)
    gains = _gains_bruts(y_conf, p0_conf, p_conf)
    ic = _ic_gains(conf, p0_conf, p_conf, bootstrap, graine)
    groupes = _sous_groupes(conf, y_conf, p0_conf, p_conf)
    robustesse = _controles_robustesse(groupes)
    assez = len(dec) >= 100 and len(conf) >= 100
    confirme = bool(assez and gains['log_loss'] >= MARGE_LOG_LOSS and gains['brier'] >= 0
                    and (ic.get('log_loss') or {}).get('bas') is not None and ic['log_loss']['bas'] > 0
                    and all(x['ok'] is not False for x in robustesse.values()))
    positif = bool(gains['log_loss'] > 0 and gains['brier'] >= 0 and not confirme)
    return {
        'decouverte': {'controle': ST._metriques(y_dec, p0_dec), 'challenger': ST._metriques(y_dec, p_dec),
                       'gains': gains_dec},
        'confirmation': {'controle': ST._metriques(y_conf, p0_conf), 'challenger': ST._metriques(y_conf, p_conf),
                         'gains': gains},
        'ic95_bootstrap_semaine': ic,
        'sous_groupes_confirmation': groupes,
        'controles_robustesse': robustesse,
        'apport_confirme': confirme,
        'verdict': ('apport confirmé hors échantillon ; soumission possible à la gouvernance, sans activation automatique'
                    if confirme else 'signal positif mais incertain ; champion inchangé' if positif
                    else 'apport non confirmé ; champion inchangé'),
        'activation': False,
    }


def evaluer(rows, predictions_elo, bootstrap=2000):
    dec = [r for r in rows if r['date'] < COUPURE]
    conf = [r for r in rows if r['date'] >= COUPURE]
    controle = _fit(dec)
    p0_dec, p0_conf = _predire(controle, dec), _predire(controle, conf)
    rapports, eligibles_combinaison = {}, []

    # Elo : chaque variante remplace uniquement la probabilité Elo du contrôle.
    candidats_elo = {}
    for k, nom in enumerate(n for n in ER.VARIANTES if n != 'controle'):
        pe = {uid: valeurs[nom] for uid, valeurs in predictions_elo.items()}
        modele = ST._ajuster([_variables(r, elo=pe[r['uid']]) for r in dec], [r['y'] for r in dec])
        pd = _predire(modele, dec, predictions_elo=pe)
        pc = _predire(modele, conf, predictions_elo=pe)
        bloc = _rapport_challenger(dec, conf, pd, pc, p0_dec, p0_conf, bootstrap, 20261028 + k)
        bloc['convergence'] = bool(modele and modele['converged'])
        bloc['options'] = ER.VARIANTES[nom]
        candidats_elo[nom] = bloc
    meilleur_elo = min(candidats_elo, key=lambda n: candidats_elo[n]['decouverte']['challenger']['log_loss'])
    rapport_elo = dict(candidats_elo[meilleur_elo])
    rapport_elo.update({'variante_choisie_sur_decouverte': meilleur_elo,
                        'toutes_les_variantes': candidats_elo,
                        'regle': 'variantes isolées ; choix sur 2024 seulement ; aucun poids contextuel rejeté rouvert'})
    rapports['elo_dynamique'] = rapport_elo
    if rapport_elo['decouverte']['gains']['log_loss'] > 0 and rapport_elo['decouverte']['gains']['brier'] >= 0:
        eligibles_combinaison.append('elo_dynamique')

    # Autres familles : variables ajoutées séparément au même contrôle.
    for k, (nom, variables) in enumerate(FAMILLES.items()):
        modele = _fit(dec, variables)
        pd, pc = _predire(modele, dec, variables), _predire(modele, conf, variables)
        bloc = _rapport_challenger(dec, conf, pd, pc, p0_dec, p0_conf, bootstrap, 20261100 + k)
        bloc['convergence'] = bool(modele and modele['converged'])
        bloc['variables'] = variables
        bloc['coefficients_standardises_decouverte'] = dict(zip(NOMS_CONTROLE + variables, modele['beta']))
        rapports[nom] = bloc
        if bloc['decouverte']['gains']['log_loss'] > 0 and bloc['decouverte']['gains']['brier'] >= 0:
            eligibles_combinaison.append(nom)

    combinaison = {'testee': False, 'activation': False,
                   'regle': 'familles retenues uniquement si log loss et Brier ne se dégradent pas sur 2024'}
    if len(eligibles_combinaison) >= 2:
        variables = [v for nom in eligibles_combinaison if nom in FAMILLES for v in FAMILLES[nom]]
        pe = None
        if 'elo_dynamique' in eligibles_combinaison:
            pe = {uid: valeurs[meilleur_elo] for uid, valeurs in predictions_elo.items()}
        modele = ST._ajuster([_variables(r, variables, pe.get(r['uid']) if pe else None) for r in dec],
                             [r['y'] for r in dec])
        pd, pc = _predire(modele, dec, variables, pe), _predire(modele, conf, variables, pe)
        combinaison = _rapport_challenger(dec, conf, pd, pc, p0_dec, p0_conf, bootstrap, 20261200)
        combinaison.update({'testee': True, 'composantes': eligibles_combinaison, 'variables_ajoutees': variables,
                            'variante_elo': meilleur_elo if pe else None,
                            'convergence': bool(modele and modele['converged']),
                            'activation': False})
    else:
        combinaison['raison'] = 'moins de deux familles positives sur la découverte ; aucune combinaison justifiée'
        combinaison['composantes_eligibles'] = eligibles_combinaison
    return rapports, combinaison


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('archive')
    parser.add_argument('racine', nargs='?', default='.')
    parser.add_argument('--maximum', type=int, default=16000)
    parser.add_argument('--bootstrap', type=int, default=2000)
    args = parser.parse_args(argv)
    debut = time.time()
    M = donnees.charger(args.archive, 2021)
    if not M:
        raise SystemExit('Aucun match Sackmann lisible.')
    choisis = PR.selection(M, dt.date(2024, 1, 1), args.maximum)
    print(f'Archive : {len(M)} matchs ; échantillon commun : {len(choisis)}', flush=True)
    rows = PO.observations(M, choisis)
    print(f'Observations pré-match : {len(rows)} ; grille Elo en cours', flush=True)
    predictions_elo = ER.predictions(M, choisis)
    rapports, combinaison = evaluer(rows, predictions_elo, args.bootstrap)
    out = {
        'schema': 'pistes_amelioration_v1',
        'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'source': 'archive Jeff Sackmann, CC BY-NC-SA 4.0, usage non commercial et attribution requis',
        'protocole': {
            'n': len(rows), 'n_decouverte': sum(r['date'] < COUPURE for r in rows),
            'n_confirmation': sum(r['date'] >= COUPURE for r in rows), 'coupure': COUPURE.isoformat(),
            'orientation': 'ordre alphabétique des identifiants, indépendant du résultat',
            'controle_elo': PO.ELO_CONTROLE,
            'controles': ['Elo général et surface', 'service–retour pur', 'surface', 'circuit', 'documentation'],
            'temporalite': 'résultats versés au changement de date ; édition de tournoi courante exclue',
            'marge_log_loss': MARGE_LOG_LOSS, 'bootstrap_semaines_iso': args.bootstrap,
            'marche_utilise': False, 'activation_automatique': False,
            'grille_figee_avant_confirmation': True,
            'dates_historiques': 'date de début de tournoi Sackmann ; résultats d’une même date versés seulement à la date suivante',
        },
        'couverture_donnees': _couverture(rows),
        'elo_dynamique': rapports['elo_dynamique'],
        'familles': {nom: rapports[nom] for nom in FAMILLES},
        'combinaison_choisie_sur_decouverte': combinaison,
        'champion_actif_modifie': False,
        'verdict_global': ('au moins un challenger est confirmé, mais aucun n’est activé sans gouvernance'
                           if any(r['apport_confirme'] for r in rapports.values()) or combinaison.get('apport_confirme')
                           else 'aucune amélioration confirmée hors échantillon ; champion inchangé'),
        'duree_s': round(time.time() - debut),
    }
    chemin = os.path.join(args.racine, 'simulateur', 'rapport_pistes_amelioration.json')
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    resume = {'protocole': out['protocole'], 'elo': {
        'variante': out['elo_dynamique']['variante_choisie_sur_decouverte'],
        'gains': out['elo_dynamique']['confirmation']['gains'], 'verdict': out['elo_dynamique']['verdict']},
        'familles': {nom: {'gains': bloc['confirmation']['gains'], 'verdict': bloc['verdict']}
                     for nom, bloc in out['familles'].items()},
        'combinaison': {'testee': combinaison['testee'], 'gains': combinaison.get('confirmation', {}).get('gains'),
                        'verdict': combinaison.get('verdict', combinaison.get('raison'))},
        'verdict_global': out['verdict_global']}
    print(json.dumps(resume, ensure_ascii=False, indent=2))
    return out


if __name__ == '__main__':
    main()
