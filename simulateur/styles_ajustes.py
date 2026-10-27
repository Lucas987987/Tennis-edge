#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bilans de styles ajustés au niveau attendu et challenger prospectif.

Pour chaque match ancien, le résidu est « résultat − probabilité Elo pré-match ».
Il est agrégé contre le style adverse, avec décroissance temporelle, filtre de
surface et contraction vers zéro. Le champion public n'utilise jamais ces variables.
"""
import datetime as dt
import hashlib
import json
import math
import os

import contexte_optionnel as CO
import nos_resultats as NR
import styles_joueurs as ST

SCHEMA = 'styles_adverses_ajustes_v1'
GEL_UTC = '2026-10-28T00:00:00+00:00'
DEMI_VIE_J = 365.0
PRIOR_MATCHS = 20.0
VARIABLES = ['style_residu_global_ecart', 'style_residu_surface_ecart']
FICHIER_MODELE = os.path.join('simulateur', 'modele_styles_ajustes.json')
FICHIER_FEATURES = os.path.join('simulateur', 'styles_descriptifs.json')
JOURNAL = os.path.join('simulateur', 'journal_pronostics', 'styles_ajustes_v1.jsonl')


def empreinte(objet):
    brut = json.dumps(objet, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(brut).hexdigest()


class Accumulateur:
    """Résidus disponibles la veille ; aucune probabilité de marché."""

    def __init__(self, demi_vie=DEMI_VIE_J, prior=PRIOR_MATCHS):
        self.demi_vie = float(demi_vie)
        self.prior = float(prior)
        self.events = {}

    def ajouter(self, gagnant, perdant, style_g, style_p, surface, jour, p_elo_gagnant):
        """Enregistre les deux points de vue avec l'Elo connu AVANT ce match."""
        p = min(max(float(p_elo_gagnant), 1e-6), 1 - 1e-6)
        residu = 1.0 - p
        if style_p != 'indetermine':
            self.events.setdefault((gagnant, style_p), []).append((jour, surface, residu))
        if style_g != 'indetermine':
            self.events.setdefault((perdant, style_g), []).append((jour, surface, -residu))

    def mesure(self, joueur, style_adverse, surface, jour, meme_surface=False):
        poids = somme = 0.0
        for date, surf, residu in self.events.get((joueur, style_adverse), []):
            age = (jour - date).days
            if age < 0 or (meme_surface and surf != surface):
                continue
            w = .5 ** (age / self.demi_vie)
            poids += w
            somme += w * residu
        # Le prior est exprimé en matchs équivalents et contracte vers aucun effet.
        return {'residu': somme / (poids + self.prior), 'n_effectif': poids}

    def variables(self, h, a, style_h, style_a, surface, jour):
        gh = self.mesure(h, style_a, surface, jour)
        ga = self.mesure(a, style_h, surface, jour)
        sh = self.mesure(h, style_a, surface, jour, True)
        sa = self.mesure(a, style_h, surface, jour, True)
        return {
            'style_residu_global_ecart': gh['residu'] - ga['residu'],
            'style_residu_surface_ecart': sh['residu'] - sa['residu'],
            'style_residu_global_home': gh['residu'], 'style_residu_global_away': ga['residu'],
            'style_residu_surface_home': sh['residu'], 'style_residu_surface_away': sa['residu'],
            'documentation_residu_global': min(gh['n_effectif'], ga['n_effectif']),
            'documentation_residu_surface': min(sh['n_effectif'], sa['n_effectif']),
        }


def charger_modele(racine='.'):
    with open(os.path.join(racine, FICHIER_MODELE), encoding='utf-8') as f:
        modele = json.load(f)
    if (modele.get('schema') != SCHEMA or modele.get('activation') is not False
            or modele.get('gel_utc') != GEL_UTC or modele.get('variables') != VARIABLES):
        raise ValueError('Le modèle de styles ajustés n’est pas le candidat figé attendu.')
    for nom in ('controle', 'challenger'):
        if not modele.get(nom) or not modele[nom].get('converged'):
            raise ValueError(f'Modèle {nom} absent ou non convergé.')
    return modele


def observation(m, bloc):
    """Ligne pré-match appariée ; None si le candidat n'est pas documenté."""
    if not m.get('debut_utc') or not bloc:
        return None
    try:
        if CO.instant(m['debut_utc']) <= CO.instant(GEL_UTC):
            return None
    except (TypeError, ValueError):
        return None
    if not bloc.get('challenger_seulement') or 'indetermine' in (bloc.get('styles') or []):
        return None
    stats, comb = m.get('stats') or {}, m.get('combinaison') or {}
    simulation = m.get('simulation') or {}
    sim = comb.get('match_simule') or simulation.get('match_simule') or {}
    balles = (sim.get('profil_contexte') or {}).get('n_balles_effectives') or []
    p_service = comb.get('p_simulation', simulation.get('p_home'))
    if (stats.get('p_home') is None or p_service is None or len(balles) != 2
            or len(m.get('matchs_joues') or []) != 2):
        return None
    if any(nom not in bloc for nom in VARIABLES):
        return None
    row = {'elo': float(stats['p_home']), 'service_retour': float(p_service),
           'surface': m['surface'], 'circuit': m['circuit'],
           'documentation_balles': min(float(balles[0]), float(balles[1])),
           'documentation_matchs': min(int(m['matchs_joues'][0]), int(m['matchs_joues'][1]))}
    for nom in VARIABLES + ['documentation_residu_global', 'documentation_residu_surface']:
        row[nom] = float(bloc[nom])
    return row


def predire(modele, row):
    base = ST._variables(row)
    ajouts = base + [float(row[nom]) for nom in VARIABLES]
    p0 = ST._predire(modele['controle'], [base])[0]
    p1 = ST._predire(modele['challenger'], [ajouts])[0]
    if not all(math.isfinite(p) and 0 < p < 1 for p in (p0, p1)):
        raise ValueError('Probabilité du challenger de styles non finie.')
    return p0, p1


def _lire_journal(chemin):
    out = {}
    try:
        with open(chemin, encoding='utf-8') as f:
            for ligne in f:
                try:
                    r = json.loads(ligne)
                except ValueError:
                    continue
                if r.get('uid'):
                    out[r['uid']] = r
    except OSError:
        pass
    return out


def observations_resolues(racine):
    """Rattache les résultats par la chaîne normale, sans réécrire le pronostic figé."""
    rows = list(_lire_journal(os.path.join(racine, JOURNAL)).values())
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
    """Évalue seulement le futur résolu ; ne promeut jamais automatiquement."""
    resolus = []
    for r in rows:
        if CO.instant(r.get('debut_utc')) <= CO.instant(GEL_UTC):
            raise ValueError('Un pronostic antérieur ou égal au gel ne peut pas confirmer ce candidat.')
        if not r.get('resultat_resolu'):
            continue
        if (not r.get('pronostic_fige') or not r.get('apparie_champion')
                or r.get('y') not in (0, 1)):
            raise ValueError('Observation résolue non figée, non appariée ou sans issue binaire.')
        r = dict(r, semaine=r.get('semaine') or ST._semaine(CO.instant(r['debut_utc']).date()))
        resolus.append(r)
    if resolus:
        y = [r['y'] for r in resolus]
        p0, p1 = [r['controle'] for r in resolus], [r['challenger'] for r in resolus]
        gains = ST._gains(y, p0, p1)
        ic = ST._ic_gains(resolus, p0, p1, bootstrap)
    else:
        gains = {'log_loss': None, 'brier': None}
        ic = {'log_loss': None, 'brier': None}
    semaines = len({CO.instant(r['debut_utc']).date().isocalendar()[:2] for r in resolus})
    assez = len(resolus) >= minimum_matchs and semaines >= minimum_semaines
    bas = (ic.get('log_loss') or {}).get('bas')
    seuil = bool(assez and gains['log_loss'] is not None and gains['log_loss'] >= .001
                 and gains['brier'] is not None and gains['brier'] >= 0 and bas is not None and bas > 0)
    sous_groupes = {}
    for nom, test in (
            ('surface:Hard', lambda r: r.get('surface') == 'Hard'),
            ('surface:Clay', lambda r: r.get('surface') == 'Clay'),
            ('surface:Grass', lambda r: r.get('surface') == 'Grass'),
            ('documentation:<10_matchs_equivalents', lambda r: min(
                (r.get('variables') or {}).get('documentation_residu_global', 0),
                (r.get('variables') or {}).get('documentation_residu_surface', 0)) < 10)):
        part = [r for r in resolus if test(r)]
        if len(part) >= 30:
            yy = [r['y'] for r in part]
            sous_groupes[nom] = {'n': len(part), 'gains': ST._gains(
                yy, [r['controle'] for r in part], [r['challenger'] for r in part])}
    return {'n_resolus': len(resolus), 'semaines_iso': semaines, 'gains': gains,
            'ic95_bootstrap_semaine': ic, 'sous_groupes': sous_groupes,
            'minimum_matchs': minimum_matchs, 'minimum_semaines_iso': minimum_semaines,
            'criteres_numeriques_atteints': seuil, 'activation': False,
            'confirmation_manuelle_requise': True,
            'regle': 'contrôles ciblés obligatoires ; aucun diagnostic historique ne peut activer le challenger'}


def journaliser(racine, doc):
    modele = charger_modele(racine)
    chemin_features = os.path.join(racine, FICHIER_FEATURES)
    try:
        with open(chemin_features, encoding='utf-8') as f:
            features = json.load(f)
    except FileNotFoundError:
        return {'schema': SCHEMA, 'statut': 'features_non_disponibles', 'nouveaux_figes': 0,
                'activation': False}
    blocs = (features.get('matchs') or {})
    chemin = os.path.join(racine, JOURNAL)
    existants = _lire_journal(chemin)
    nouveaux, eligibles = [], 0
    for m in doc.get('matchs') or []:
        bloc = (blocs.get(m.get('uid')) or {}).get('styles_ajustes')
        row = observation(m, bloc)
        if row is None:
            continue
        eligibles += 1
        if m['uid'] in existants:
            continue
        p0, p1 = predire(modele, row)
        r = {'schema': SCHEMA, 'uid': m['uid'], 'debut_utc': m['debut_utc'],
             'pronostique_le': doc['genere_le'], 'home': m['home'], 'away': m['away'],
             'circuit': m['circuit'], 'surface': m['surface'], 'controle': p0, 'challenger': p1,
             'variables': row, 'modele_empreinte': empreinte(modele), 'styles_empreinte': empreinte(bloc),
             'pronostic_fige': True, 'resultat_resolu': False, 'apparie_champion': True, 'activation': False}
        nouveaux.append(r)
    if nouveaux:
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with open(chemin, 'a', encoding='utf-8') as f:
            for r in nouveaux:
                f.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
    confirmation = evaluer_confirmation(observations_resolues(racine), bootstrap=0)
    return {'schema': SCHEMA, 'n_matchs': len(doc.get('matchs') or []), 'n_eligibles': eligibles,
            'nouveaux_figes': len(nouveaux), 'deja_figes': eligibles - len(nouveaux), 'journal': JOURNAL,
            'modele_empreinte': empreinte(modele), 'activation': False, 'confirmation': confirmation}
