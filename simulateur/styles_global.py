#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Second avis « bilans de styles globaux seuls » et journal prospectif.

Le modèle est celui figé sur 2024. La matrice des paires reste descriptive :
aucun bonus par duel et aucune modification du champion. Le journal conserve le
champion réellement publié et le second avis sur le même match, puis rattache le
résultat par la chaîne normale. La comparaison de deux modèles indépendants ne
prouve pas, à elle seule, un apport incrémental des styles au champion.
"""
import hashlib
import json
import math
import os

import contexte_optionnel as CO
import nos_resultats as NR
import styles_joueurs as ST

SCHEMA = 'styles_adverses_global_v1'
GEL_UTC = '2026-10-28T00:00:00+00:00'
PRIOR_MATCHS = 20.0
FICHIER_MODELE = os.path.join('simulateur', 'modele_styles_global.json')
FICHIER_FEATURES = os.path.join('simulateur', 'styles_descriptifs.json')
JOURNAL = os.path.join('simulateur', 'journal_pronostics', 'styles_global_v1.jsonl')


def empreinte(objet):
    brut = json.dumps(objet, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(brut).hexdigest()


def _lg(p):
    return math.log(p/(1-p))


def _taux(acc, joueur, style):
    ligne = acc.get((joueur, style, 'global')) or {'n': 0, 'v': 0}
    n, v = ligne['n'], ligne['v']
    return (v + PRIOR_MATCHS/2)/(n + PRIOR_MATCHS), n


def variables(acc, h, a, style_h, style_a):
    """Bilans bruts contractés disponibles avant le match, sans autre covariable."""
    ph, nh = _taux(acc, h, style_a)
    pa, na = _taux(acc, a, style_h)
    return {
        'bilan_global': _lg(ph)-_lg(pa),
        'taux_global_home': ph, 'taux_global_away': pa,
        'documentation_global_home': nh, 'documentation_global_away': na,
        'documentation_bilans': min(nh, na),
    }


def charger_modele(racine='.'):
    with open(os.path.join(racine, FICHIER_MODELE), encoding='utf-8') as f:
        modele = json.load(f)
    if (modele.get('schema') != SCHEMA or modele.get('activation') is not False
            or modele.get('gel_utc') != GEL_UTC or modele.get('variables') != ['bilan_global']
            or not (modele.get('modele') or {}).get('converged')):
        raise ValueError('Le modèle global de styles n’est pas le candidat figé attendu.')
    return modele


def probabilite_champion(m):
    """Probabilité home réellement publiée, sans la recalculer ni la modifier."""
    for nom in ('combinaison', 'simulation', 'stats'):
        bloc = m.get(nom) or {}
        if bloc.get('p_home') is not None:
            p = float(bloc['p_home'])
            if math.isfinite(p) and 0 < p < 1:
                return p
    return None


def observation(m, bloc):
    if not m.get('debut_utc') or not bloc:
        return None
    try:
        if CO.instant(m['debut_utc']) <= CO.instant(GEL_UTC):
            return None
    except (TypeError, ValueError):
        return None
    if (not bloc.get('challenger_seulement') or bloc.get('schema') != SCHEMA
            or len(bloc.get('styles') or []) != 2):
        return None
    p_champion = probabilite_champion(m)
    cles = m.get('cles') or []
    if p_champion is None or len(cles) != 2:
        return None
    noms = ('bilan_global', 'taux_global_home', 'taux_global_away',
            'documentation_global_home', 'documentation_global_away', 'documentation_bilans')
    if any(nom not in bloc for nom in noms):
        return None
    row = {nom: float(bloc[nom]) for nom in noms}
    row.update({'cles': [str(cles[0]), str(cles[1])], 'champion': p_champion,
                'paire_styles': '|'.join(sorted(bloc.get('styles') or []))})
    return row


def predire(modele, row):
    """Reproduit l'orientation alphabétique de 2024 puis revient au home réel."""
    h, a = row['cles']
    inverse = h > a
    bilan = -row['bilan_global'] if inverse else row['bilan_global']
    p = ST._predire(modele['modele'], [[1.0, bilan]])[0]
    p_home = 1-p if inverse else p
    if not math.isfinite(p_home) or not 0 < p_home < 1:
        raise ValueError('Probabilité globale de styles non finie.')
    return p_home


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
    resolus = []
    for r in rows:
        if CO.instant(r.get('debut_utc')) <= CO.instant(GEL_UTC):
            raise ValueError('Un pronostic antérieur ou égal au gel ne peut pas entrer dans ce suivi.')
        if not r.get('resultat_resolu'):
            continue
        if (not r.get('pronostic_fige') or not r.get('apparie_champion') or r.get('y') not in (0, 1)):
            raise ValueError('Observation résolue non figée, non appariée ou sans issue binaire.')
        r = dict(r, semaine=r.get('semaine') or ST._semaine(CO.instant(r['debut_utc']).date()))
        resolus.append(r)
    if resolus:
        y = [r['y'] for r in resolus]
        p0, p1 = [r['champion'] for r in resolus], [r['styles_global'] for r in resolus]
        metriques = {'champion': ST._metriques(y, p0), 'styles_global': ST._metriques(y, p1)}
        gains = ST._gains(y, p0, p1)
        gains['sens'] = 'positif = second avis styles meilleur que le champion ; pas une preuve incrémentale'
        ic = ST._ic_gains(resolus, p0, p1, bootstrap)
    else:
        metriques, gains = {}, {'log_loss': None, 'brier': None}
        ic = {'log_loss': None, 'brier': None}
    semaines = len({CO.instant(r['debut_utc']).date().isocalendar()[:2] for r in resolus})
    paires = {}
    for cle in sorted({r.get('paire_styles') for r in resolus}):
        part = [r for r in resolus if r.get('paire_styles') == cle]
        if len(part) < 30:
            continue
        yy = [r['y'] for r in part]
        paires[cle] = {'n': len(part), 'gains_styles_moins_champion': ST._gains(
            yy, [r['champion'] for r in part], [r['styles_global'] for r in part])}
    return {
        'n_resolus': len(resolus), 'semaines_iso': semaines, 'metriques': metriques,
        'gains_styles_moins_champion': gains, 'ic95_bootstrap_semaine': ic,
        'paires_avec_au_moins_30': paires,
        'minimum_matchs': minimum_matchs, 'minimum_semaines_iso': minimum_semaines,
        'fenêtre_suffisante': len(resolus) >= minimum_matchs and semaines >= minimum_semaines,
        'comparaison_independante_pas_preuve_incrementale': True,
        'activation': False, 'confirmation_manuelle_requise': True,
    }


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
    existants = _lire_journal(chemin)
    nouveaux, eligibles = [], 0
    for m in doc.get('matchs') or []:
        bloc = (blocs.get(m.get('uid')) or {}).get('styles_global')
        row = observation(m, bloc)
        if row is None:
            continue
        eligibles += 1
        if m['uid'] in existants:
            continue
        p_styles = predire(modele, row)
        variables_figees = {k: v for k, v in row.items() if k not in ('cles', 'champion', 'paire_styles')}
        r = {
            'schema': SCHEMA, 'uid': m['uid'], 'debut_utc': m['debut_utc'],
            'pronostique_le': doc['genere_le'], 'home': m['home'], 'away': m['away'],
            'cles': row['cles'], 'circuit': m['circuit'], 'surface': m['surface'],
            'paire_styles': row['paire_styles'], 'champion': row['champion'], 'styles_global': p_styles,
            'variables': variables_figees, 'modele_empreinte': empreinte(modele),
            'styles_empreinte': empreinte(bloc), 'pronostic_fige': True,
            'resultat_resolu': False, 'apparie_champion': True, 'activation': False,
        }
        nouveaux.append(r)
    if nouveaux:
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with open(chemin, 'a', encoding='utf-8') as f:
            for r in nouveaux:
                f.write(json.dumps(r, ensure_ascii=False, separators=(',', ':'))+'\n')
    confirmation = evaluer_confirmation(observations_resolues(racine), bootstrap=0)
    return {
        'schema': SCHEMA, 'n_matchs': len(doc.get('matchs') or []), 'n_eligibles': eligibles,
        'nouveaux_figes': len(nouveaux), 'deja_figes': eligibles-len(nouveaux), 'journal': JOURNAL,
        'modele_empreinte': empreinte(modele), 'activation': False, 'confirmation': confirmation,
    }
