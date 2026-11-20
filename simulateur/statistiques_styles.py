#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Challenger dur des statistiques détaillées contre les styles adverses.

Le diagnostic global est non confirmant. Seul le sous-groupe dur, repéré après
coup, est journalisé ici sur de futurs pronostics figés. Le champion publié et
le contrôle avec bilan global sont conservés sur le même UID. Aucun historique
ne peut activer ce challenger et rien n'est injecté dans la probabilité publique.
"""
import datetime as dt  # noqa: F401  (contrat des modules de suivi)
import json
import math
import os

import contexte_optionnel as CO
import nos_resultats as NR
import styles_global as SG
import styles_joueurs as ST

SCHEMA = 'statistiques_styles_adverses_v1'
GEL_UTC = '2026-10-28T00:00:00+00:00'
FICHIER_MODELE = os.path.join('simulateur', 'modele_statistiques_styles.json')
FICHIER_FEATURES = os.path.join('simulateur', 'styles_descriptifs.json')
JOURNAL = os.path.join('simulateur', 'journal_pronostics', 'statistiques_styles_dur_v1.jsonl')


def charger_modele(racine='.'):
    with open(os.path.join(racine, FICHIER_MODELE), encoding='utf-8') as f:
        modele = json.load(f)
    if (modele.get('schema') != SCHEMA or modele.get('activation') is not False
            or modele.get('gel_utc') != GEL_UTC or modele.get('surface_cible') != 'Hard'
            or not modele.get('variables_statistiques')):
        raise ValueError('Le modèle détaillé de styles n’est pas le challenger dur figé attendu.')
    for nom in ('controle', 'bilan', 'challenger'):
        if not (modele.get(nom) or {}).get('converged'):
            raise ValueError(f'Modèle {nom} absent ou non convergé.')
    return modele


def observation(m, bloc):
    """Variables home réel, seulement sur dur et strictement après le gel."""
    if not m.get('debut_utc') or not bloc or m.get('surface') != 'Hard':
        return None
    try:
        if CO.instant(m['debut_utc']) <= CO.instant(GEL_UTC):
            return None
    except (TypeError, ValueError):
        return None
    if (not bloc.get('challenger_seulement') or bloc.get('schema') != SCHEMA
            or 'indetermine' in (bloc.get('styles') or [])):
        return None
    stats, comb = m.get('stats') or {}, m.get('combinaison') or {}
    simulation = m.get('simulation') or {}
    sim = comb.get('match_simule') or simulation.get('match_simule') or {}
    balles = (sim.get('profil_contexte') or {}).get('n_balles_effectives') or []
    p_service = comb.get('p_simulation', simulation.get('p_home'))
    p_champion = SG.probabilite_champion(m)
    cles = m.get('cles') or []
    if (stats.get('p_home') is None or p_service is None or p_champion is None
            or len(balles) != 2 or len(m.get('matchs_joues') or []) != 2 or len(cles) != 2):
        return None
    row = {'elo': float(stats['p_home']), 'service_retour': float(p_service),
           'surface': m['surface'], 'circuit': m['circuit'],
           'documentation_balles': min(float(balles[0]), float(balles[1])),
           'documentation_matchs': min(int(m['matchs_joues'][0]), int(m['matchs_joues'][1])),
           'champion': p_champion, 'cles': [str(cles[0]), str(cles[1])]}
    noms = ['bilan_global', 'documentation_stats'] + [f'stats_{nom}' for nom in (
        'points_gagnes_pct', 'service_gagnes_pct', 'retour_gagnes_pct', 'gagnes_2e_pct',
        'balles_break_sauvees_pct', 'balles_break_converties_pct')]
    if any(nom not in bloc for nom in noms):
        return None
    for nom in noms:
        row[nom] = float(bloc[nom])
    return row


def predire(modele, row):
    """Rétablit l'orientation alphabétique de 2024 puis revient au home réel."""
    inverse = row['cles'][0] > row['cles'][1]
    r = dict(row)
    if inverse:
        r['elo'], r['service_retour'] = 1-r['elo'], 1-r['service_retour']
        r['bilan_global'] = -r['bilan_global']
        for nom in modele['variables_statistiques']:
            r[f'stats_{nom}'] = -r[f'stats_{nom}']
    base = ST._variables(r)
    avec_bilan = base + [r['bilan_global']]
    detaille = avec_bilan + [r[f'stats_{nom}'] for nom in modele['variables_statistiques']]
    p0 = ST._predire(modele['bilan'], [avec_bilan])[0]
    p1 = ST._predire(modele['challenger'], [detaille])[0]
    if not all(math.isfinite(p) and 0 < p < 1 for p in (p0, p1)):
        raise ValueError('Probabilité du challenger détaillé non finie.')
    return (1-p0 if inverse else p0), (1-p1 if inverse else p1)


def observations_resolues(racine):
    rows = list(SG._lire_journal(os.path.join(racine, JOURNAL)).values())
    try:
        with open(os.path.join(racine, 'set_results.json'), encoding='utf-8') as f:
            resultats = json.load(f)
    except (OSError, ValueError):
        resultats = {}
    out = []
    for original in rows:
        r = dict(original)
        res, sens = NR.resultat(resultats, CO.instant(r['debut_utc']).date(), r['home'], r['away'])
        if res and res.get('match') in ('home', 'away'):
            gagnant = res['match']
            if sens == -1:
                gagnant = 'away' if gagnant == 'home' else 'home'
            r['y'] = int(gagnant == 'home')
            r['resultat_resolu'] = True
            r['semaine'] = ST._semaine(CO.instant(r['debut_utc']).date())
        out.append(r)
    return out


def evaluer_confirmation(rows, minimum_matchs=1000, minimum_semaines=8, bootstrap=2000):
    resolus = []
    for r in rows:
        if CO.instant(r.get('debut_utc')) <= CO.instant(GEL_UTC):
            raise ValueError('Un pronostic antérieur ou égal au gel ne peut pas confirmer ce challenger.')
        if not r.get('resultat_resolu'):
            continue
        if (not r.get('pronostic_fige') or not r.get('apparie_champion')
                or r.get('surface') != 'Hard' or r.get('y') not in (0, 1)):
            raise ValueError('Observation résolue non figée, non appariée, hors dur ou sans issue binaire.')
        r = dict(r, semaine=r.get('semaine') or ST._semaine(CO.instant(r['debut_utc']).date()))
        resolus.append(r)
    if resolus:
        y = [r['y'] for r in resolus]
        champion = [r['champion'] for r in resolus]
        controle = [r['controle'] for r in resolus]
        challenger = [r['challenger'] for r in resolus]
        metriques = {'champion': ST._metriques(y, champion), 'controle_avec_bilan': ST._metriques(y, controle),
                     'challenger': ST._metriques(y, challenger)}
        gains_champion = ST._gains(y, champion, challenger)
        gains_controle = ST._gains(y, controle, challenger)
        ic_champion = ST._ic_gains(resolus, champion, challenger, bootstrap)
        ic_controle = ST._ic_gains(resolus, controle, challenger, bootstrap)
    else:
        metriques = {}
        gains_champion = gains_controle = {'log_loss': None, 'brier': None}
        ic_champion = ic_controle = {'log_loss': None, 'brier': None}
    semaines = len({CO.instant(r['debut_utc']).date().isocalendar()[:2] for r in resolus})
    assez = len(resolus) >= minimum_matchs and semaines >= minimum_semaines
    bas = (ic_controle.get('log_loss') or {}).get('bas')
    criteres = bool(assez and bas is not None and bas > 0
                    and all(g.get('log_loss') is not None and g['log_loss'] >= .001
                            and g.get('brier') is not None and g['brier'] >= 0
                            for g in (gains_champion, gains_controle)))
    return {'n_resolus': len(resolus), 'semaines_iso': semaines, 'surface': 'Hard',
            'metriques': metriques, 'gains_contre_champion': gains_champion,
            'gains_incrementaux_au_bilan': gains_controle,
            'ic95_contre_champion_bootstrap_semaine': ic_champion,
            'ic95_incrementaux_bootstrap_semaine': ic_controle,
            'minimum_matchs': minimum_matchs, 'minimum_semaines_iso': minimum_semaines,
            'criteres_numeriques_atteints': criteres, 'activation': False,
            'confirmation_manuelle_requise': True,
            'regle': 'futur figé sur dur uniquement ; le diagnostic historique post hoc ne peut pas activer le challenger'}


def journaliser(racine, doc):
    modele = charger_modele(racine)
    try:
        with open(os.path.join(racine, FICHIER_FEATURES), encoding='utf-8') as f:
            features = json.load(f)
    except FileNotFoundError:
        return {'schema': SCHEMA, 'statut': 'features_non_disponibles', 'nouveaux_figes': 0,
                'activation': False}
    blocs = features.get('matchs') or {}
    chemin = os.path.join(racine, JOURNAL)
    existants = SG._lire_journal(chemin)
    nouveaux, eligibles = [], 0
    for m in doc.get('matchs') or []:
        bloc = (blocs.get(m.get('uid')) or {}).get('statistiques_styles')
        row = observation(m, bloc)
        if row is None:
            continue
        eligibles += 1
        if m['uid'] in existants:
            continue
        p0, p1 = predire(modele, row)
        variables = {k: v for k, v in row.items() if k not in ('champion', 'cles')}
        r = {'schema': SCHEMA, 'uid': m['uid'], 'debut_utc': m['debut_utc'],
             'pronostique_le': doc['genere_le'], 'home': m['home'], 'away': m['away'],
             'cles': row['cles'], 'circuit': m['circuit'], 'surface': m['surface'],
             'champion': row['champion'], 'controle': p0, 'challenger': p1,
             'variables': variables, 'modele_empreinte': SG.empreinte(modele),
             'styles_empreinte': SG.empreinte(bloc), 'pronostic_fige': True,
             'resultat_resolu': False, 'apparie_champion': True, 'activation': False,
             'sous_groupe_post_hoc': True}
        nouveaux.append(r)
    if nouveaux:
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with open(chemin, 'a', encoding='utf-8') as f:
            for r in nouveaux:
                f.write(json.dumps(r, ensure_ascii=False, separators=(',', ':'))+'\n')
    confirmation = evaluer_confirmation(observations_resolues(racine), bootstrap=0)
    return {'schema': SCHEMA, 'n_matchs': len(doc.get('matchs') or []), 'n_eligibles': eligibles,
            'nouveaux_figes': len(nouveaux), 'deja_figes': eligibles-len(nouveaux), 'journal': JOURNAL,
            'modele_empreinte': SG.empreinte(modele), 'activation': False, 'confirmation': confirmation}
