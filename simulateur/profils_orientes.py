#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Suivi prospectif de deux directions de profils sur les trois branches.

Les six cellules ont été explicitement retenues par l'utilisateur après lecture
de la matrice : serveur_attaquant/contreur et contreur/grand_serveur, sur ATP,
WTA et Challenger/ITF. Le suivi ne crée aucune probabilité corrigée. Il fige le
champion publié et le contrôle partagé avec bilan global, puis mesure sur les
résultats futurs si le profil indiqué gagne plus que prévu.

Aucun résiduel historique n'est transformé en bonus. Même un résiduel futur
confirmé ne peut pas activer automatiquement une correction : il justifiera
seulement l'apprentissage séparé d'un challenger et une nouvelle validation.
"""
import datetime as dt  # noqa: F401  (contrat des modules de suivi)
import json
import math
import os
import random

import contexte_optionnel as CO
import nos_resultats as NR
import styles_global as SG
import styles_joueurs as ST

SCHEMA = 'profils_orientes_signaux_v1'
GEL_UTC = '2026-11-01T00:00:00+00:00'
FICHIER_MODELE = os.path.join('simulateur', 'modele_matrice_profils_orientee.json')
FICHIER_FEATURES = os.path.join('simulateur', 'styles_descriptifs.json')
JOURNAL = os.path.join('simulateur', 'journal_pronostics', 'profils_orientes_signaux_v1.jsonl')
BRANCHES = {'atp': ('ATP',), 'wta': ('WTA',), 'challenger': ('CH', 'ITF')}
DIRECTIONS = {
    'serveur_attaquant_contre_contreur': ('serveur_attaquant', 'contreur'),
    'contreur_contre_grand_serveur': ('contreur', 'grand_serveur'),
}


def branche(circuit):
    for nom, circuits in BRANCHES.items():
        if circuit in circuits:
            return nom
    return None


def direction(styles):
    """Direction figée et sens du profil étudié dans le home réel."""
    if len(styles or []) != 2:
        return None, 0
    for nom, paire in DIRECTIONS.items():
        if tuple(styles) == paire:
            return nom, 1
        if tuple(styles) == paire[::-1]:
            return nom, -1
    return None, 0


def charger_modele(racine='.'):
    with open(os.path.join(racine, FICHIER_MODELE), encoding='utf-8') as f:
        modele = json.load(f)
    if (modele.get('schema') != 'matrice_profils_orientee_v1'
            or modele.get('activation') is not False or modele.get('gel_utc') != GEL_UTC
            or not (modele.get('controle') or {}).get('converged')):
        raise ValueError('Le contrôle partagé figé attendu est absent ou différent.')
    return modele


def observation(m, bloc):
    """Observation home réel, uniquement future et dans une des six cellules."""
    if not m.get('debut_utc') or not bloc:
        return None
    try:
        if CO.instant(m['debut_utc']) <= CO.instant(GEL_UTC):
            return None
    except (TypeError, ValueError):
        return None
    if not bloc.get('challenger_seulement') or bloc.get('schema') != 'statistiques_styles_adverses_v1':
        return None
    nom_direction, sens = direction(bloc.get('styles'))
    nom_branche = branche(m.get('circuit'))
    if not nom_direction or not nom_branche:
        return None
    stats, comb = m.get('stats') or {}, m.get('combinaison') or {}
    simulation = m.get('simulation') or {}
    sim = comb.get('match_simule') or simulation.get('match_simule') or {}
    balles = (sim.get('profil_contexte') or {}).get('n_balles_effectives') or []
    p_service = comb.get('p_simulation', simulation.get('p_home'))
    p_champion = SG.probabilite_champion(m)
    cles = m.get('cles') or []
    if (stats.get('p_home') is None or p_service is None or p_champion is None
            or len(balles) != 2 or len(m.get('matchs_joues') or []) != 2 or len(cles) != 2
            or bloc.get('bilan_global') is None):
        return None
    return {
        'elo': float(stats['p_home']), 'service_retour': float(p_service),
        'surface': m['surface'], 'circuit': m['circuit'],
        'documentation_balles': min(float(balles[0]), float(balles[1])),
        'documentation_matchs': min(int(m['matchs_joues'][0]), int(m['matchs_joues'][1])),
        'bilan_global': float(bloc['bilan_global']), 'champion': p_champion,
        'cles': [str(cles[0]), str(cles[1])], 'direction': nom_direction,
        'sens_profil_home': sens, 'branche': nom_branche,
        'style_home': bloc['styles'][0], 'style_away': bloc['styles'][1],
    }


def predire_controle(modele, row):
    """Contrôle avec bilan, orientation alphabétique puis retour au home réel."""
    inverse = row['cles'][0] > row['cles'][1]
    r = dict(row)
    if inverse:
        r['elo'], r['service_retour'] = 1-r['elo'], 1-r['service_retour']
        r['bilan_global'] = -r['bilan_global']
    x = ST._variables(r)+[r['bilan_global']]
    p = ST._predire(modele['controle'], [x])[0]
    p = 1-p if inverse else p
    if not math.isfinite(p) or not 0 < p < 1:
        raise ValueError('Probabilité du contrôle orienté non finie.')
    return p


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


def _ic_residuel(rows, champ, repetitions=2000, graine=20261101):
    if not rows or repetitions <= 0:
        return None
    semaines = sorted({r['semaine'] for r in rows})
    if len(semaines) < 2:
        return None
    groupes = {s: [i for i, r in enumerate(rows) if r['semaine'] == s] for s in semaines}
    rnd, valeurs = random.Random(graine), []
    for _ in range(repetitions):
        indices = [i for s in (rnd.choice(semaines) for _ in semaines) for i in groupes[s]]
        residus = [rows[i]['sens_profil_home']*(rows[i]['y']-rows[i][champ]) for i in indices]
        valeurs.append(100*sum(residus)/len(residus))
    valeurs.sort()
    return {'bas': round(valeurs[int(.025*(len(valeurs)-1))], 3),
            'haut': round(valeurs[int(.975*(len(valeurs)-1))], 3)}


def _cellule(rows, minimum_matchs, minimum_semaines, bootstrap, graine):
    if not rows:
        return {'n_resolus': 0, 'semaines_iso': 0, 'signal_prospectif_confirme': False,
                'activation': False}
    y = [r['y'] for r in rows]
    champion = [r['champion'] for r in rows]
    controle = [r['controle'] for r in rows]
    victoires = [r['y'] if r['sens_profil_home'] == 1 else 1-r['y'] for r in rows]
    p_champion = [p if r['sens_profil_home'] == 1 else 1-p for r, p in zip(rows, champion)]
    p_controle = [p if r['sens_profil_home'] == 1 else 1-p for r, p in zip(rows, controle)]
    residu_champion = 100*sum(v-p for v, p in zip(victoires, p_champion))/len(rows)
    residu_controle = 100*sum(v-p for v, p in zip(victoires, p_controle))/len(rows)
    semaines = len({r['semaine'] for r in rows})
    ic_champion = _ic_residuel(rows, 'champion', bootstrap, graine)
    ic_controle = _ic_residuel(rows, 'controle', bootstrap, graine+1)
    assez = len(rows) >= minimum_matchs and semaines >= minimum_semaines
    confirme = bool(assez and residu_champion > 0 and residu_controle > 0
                    and ic_champion and ic_controle
                    and ic_champion['bas'] > 0 and ic_controle['bas'] > 0)
    return {
        'n_resolus': len(rows), 'semaines_iso': semaines,
        'victoires_profil_pct': round(100*sum(victoires)/len(rows), 2),
        'probabilite_champion_profil_pct': round(100*sum(p_champion)/len(rows), 2),
        'probabilite_controle_profil_pct': round(100*sum(p_controle)/len(rows), 2),
        'residuel_champion_points': round(residu_champion, 3),
        'residuel_controle_points': round(residu_controle, 3),
        'ic95_residuel_champion_bootstrap_semaine': ic_champion,
        'ic95_residuel_controle_bootstrap_semaine': ic_controle,
        'metriques_home': {'champion': ST._metriques(y, champion), 'controle_avec_bilan': ST._metriques(y, controle)},
        'minimum_matchs': minimum_matchs, 'minimum_semaines_iso': minimum_semaines,
        'signal_prospectif_confirme': confirme,
        'suite_si_confirme': 'apprendre séparément un challenger sur une nouvelle découverte, puis le revalider ; aucune activation directe',
        'activation': False,
    }


def evaluer_confirmation(rows, minimum_matchs=200, minimum_semaines=8, bootstrap=2000):
    resolus = []
    for r in rows:
        if CO.instant(r.get('debut_utc')) <= CO.instant(GEL_UTC):
            raise ValueError('Un pronostic antérieur ou égal au gel ne peut pas entrer dans ce suivi.')
        if not r.get('resultat_resolu'):
            continue
        if (not r.get('pronostic_fige') or not r.get('apparie_champion')
                or r.get('y') not in (0, 1) or r.get('direction') not in DIRECTIONS
                or r.get('branche') not in BRANCHES or r.get('sens_profil_home') not in (-1, 1)):
            raise ValueError('Observation résolue non figée, non appariée ou hors cellules figées.')
        r = dict(r, semaine=r.get('semaine') or ST._semaine(CO.instant(r['debut_utc']).date()))
        resolus.append(r)
    cellules = {}
    for k, nom_branche in enumerate(BRANCHES):
        for j, nom_direction in enumerate(DIRECTIONS):
            part = [r for r in resolus if r['branche'] == nom_branche and r['direction'] == nom_direction]
            cellules[f'{nom_branche}|{nom_direction}'] = _cellule(
                part, minimum_matchs, minimum_semaines, bootstrap, 20262000+10*k+j)
    return {'n_resolus': len(resolus), 'cellules': cellules,
            'cellules_fixees_avant_future_collecte': True, 'correction_active': False,
            'activation': False, 'confirmation_manuelle_requise': True,
            'regle': 'résiduel futur du profil contre champion et contrôle ; aucun bonus historique injecté'}


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
        controle = predire_controle(modele, row)
        variables = {k: v for k, v in row.items()
                     if k not in ('champion', 'cles', 'direction', 'sens_profil_home', 'branche', 'style_home', 'style_away')}
        r = {'schema': SCHEMA, 'uid': m['uid'], 'debut_utc': m['debut_utc'],
             'pronostique_le': doc['genere_le'], 'home': m['home'], 'away': m['away'],
             'cles': row['cles'], 'circuit': m['circuit'], 'surface': m['surface'],
             'branche': row['branche'], 'direction': row['direction'],
             'sens_profil_home': row['sens_profil_home'],
             'style_home': row['style_home'], 'style_away': row['style_away'],
             'champion': row['champion'], 'controle': controle, 'variables': variables,
             'modele_empreinte': SG.empreinte(modele), 'styles_empreinte': SG.empreinte(bloc),
             'pronostic_fige': True, 'resultat_resolu': False, 'apparie_champion': True,
             'descriptif_prospectif_seulement': True, 'activation': False}
        nouveaux.append(r)
    if nouveaux:
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with open(chemin, 'a', encoding='utf-8') as f:
            for r in nouveaux:
                f.write(json.dumps(r, ensure_ascii=False, separators=(',', ':'))+'\n')
    confirmation = evaluer_confirmation(observations_resolues(racine), bootstrap=0)
    return {'schema': SCHEMA, 'n_matchs': len(doc.get('matchs') or []), 'n_eligibles': eligibles,
            'nouveaux_figes': len(nouveaux), 'deja_figes': eligibles-len(nouveaux), 'journal': JOURNAL,
            'cellules_suivies': 6, 'correction_active': False, 'activation': False,
            'confirmation': confirmation}
