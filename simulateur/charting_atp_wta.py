#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Candidat Match Charting ATP/WTA figé et cohorte strictement prospective.

Le sous-groupe ayant été repéré après analyse de 2025–2026, ces années ne
peuvent pas le confirmer. Ce module journalise le premier contrôle et le premier
challenger de chaque nouveau match, sans modifier le champion de production.
"""
import datetime as dt
import hashlib
import json
import math
import os

import charting as CH
import contexte_optionnel as CO
import styles_joueurs as ST

SCHEMA = 'charting_atp_wta_v1'
VERSION = 'charting_atp_wta_v1'
GEL_UTC = '2026-10-28T00:00:00+00:00'
CIRCUITS = ('ATP', 'WTA')
VARIABLES = ['mcp_premier_coup_ecart', 'mcp_retour_ecart', 'mcp_duel_ecart', 'mcp_echanges_ecart']
FICHIER_MODELE = os.path.join('simulateur', 'modele_charting_atp_wta.json')
JOURNAL = os.path.join('simulateur', 'charting_atp_wta_journal.jsonl')


def empreinte(modele):
    brut = json.dumps(modele, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(brut).hexdigest()


def charger_modele(racine='.'):
    with open(os.path.join(racine, FICHIER_MODELE), encoding='utf-8') as f:
        modele = json.load(f)
    if (modele.get('schema') != SCHEMA or modele.get('activation') is not False
            or modele.get('gel_utc') != GEL_UTC):
        raise ValueError('Le modèle Match Charting ATP/WTA n’est pas le candidat figé attendu.')
    for nom in ('controle', 'challenger'):
        if not modele.get(nom) or not modele[nom].get('converged'):
            raise ValueError(f'Modèle {nom} absent ou non convergé.')
    return modele


def eligible(circuit, documentation_h, documentation_a, debut_utc):
    """Couverture réelle des deux joueurs et début strictement postérieur au gel."""
    try:
        futur = CO.instant(debut_utc) > CO.instant(GEL_UTC)
    except (TypeError, ValueError):
        return False
    couvert = lambda d: bool((d or {}).get('couvert') or (d or {}).get('matchs', 0))
    return bool(futur and circuit in CIRCUITS and couvert(documentation_h) and couvert(documentation_a))


def observation(m, contexte):
    """Variables pré-match de recherche ; None si le match n'est pas éligible."""
    if not m.get('debut_utc') or m.get('circuit') not in CIRCUITS or contexte is None:
        return None
    combinaison = m.get('combinaison') or {}
    stats = m.get('stats') or {}
    sim = combinaison.get('match_simule') or {}
    contexte_profil = sim.get('profil_contexte') or {}
    balles = contexte_profil.get('n_balles_effectives') or []
    cles = m.get('cles') or []
    if (len(cles) != 2 or len(balles) != 2 or not m.get('matchs_joues')
            or stats.get('p_home') is None or combinaison.get('p_simulation') is None):
        return None
    h, a = cles
    jour = CO.instant(m['debut_utc']).date()
    charting = contexte.H.charting
    dh, da = charting.documentation(h, jour), charting.documentation(a, jour)
    if not eligible(m['circuit'], dh, da, m['debut_utc']):
        return None
    row = {'elo': float(stats['p_home']), 'service_retour': float(combinaison['p_simulation']),
           'surface': m['surface'], 'circuit': m['circuit'],
           'documentation_balles': min(float(balles[0]), float(balles[1])),
           'documentation_matchs': min(int(m['matchs_joues'][0]), int(m['matchs_joues'][1]))}
    row.update(CH.variables_match(charting.profil(h, jour), charting.profil(a, jour)))
    return row, {'home': dh, 'away': da}


def predire(modele, row):
    """Contrôle et challenger sur exactement les mêmes variables pré-match."""
    base = ST._variables(row)
    ajouts = base + [float(row[nom]) for nom in VARIABLES]
    p0 = ST._predire(modele['controle'], [base])[0]
    p1 = ST._predire(modele['challenger'], [ajouts])[0]
    if not all(math.isfinite(p) and 0 < p < 1 for p in (p0, p1)):
        raise ValueError('Probabilité du candidat non finie.')
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


def journaliser(racine, doc, contexte):
    """Premier pronostic seulement ; toute retouche d'un UID existant est refusée."""
    modele = charger_modele(racine)
    empreinte_modele = empreinte(modele)
    chemin = os.path.join(racine, JOURNAL)
    existants = _lire_journal(chemin)
    nouveaux, eligibles, atp_wta = [], 0, 0
    for m in doc.get('matchs') or []:
        if m.get('circuit') in CIRCUITS:
            atp_wta += 1
        obs = observation(m, contexte)
        if obs is None:
            continue
        eligibles += 1
        if m['uid'] in existants:
            continue
        row, documentation = obs
        p0, p1 = predire(modele, row)
        r = {'schema': SCHEMA, 'uid': m['uid'], 'debut_utc': m['debut_utc'],
             'pronostique_le': doc['genere_le'], 'home': m['home'], 'away': m['away'],
             'circuit': m['circuit'], 'surface': m['surface'], 'controle': p0, 'challenger': p1,
             'variables': row, 'documentation_charting': documentation,
             'modele_empreinte': empreinte_modele, 'pronostic_fige': True,
             'resultat_resolu': False, 'apparie_champion': True, 'activation': False}
        nouveaux.append(r)
    if nouveaux:
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with open(chemin, 'a', encoding='utf-8') as f:
            for r in nouveaux:
                f.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
    return {'schema': SCHEMA, 'n_matchs': len(doc.get('matchs') or []), 'n_atp_wta': atp_wta,
            'n_eligibles': eligibles, 'nouveaux_figes': len(nouveaux),
            'deja_figes': eligibles - len(nouveaux), 'journal': JOURNAL,
            'modele_empreinte': empreinte_modele, 'activation': False,
            'confirmation': 'uniquement après résultats ultérieurs ; 2025–2026 exclus'}


def evaluer_confirmation(rows, minimum_matchs=1000, minimum_semaines=8):
    """Garde-fou de la future évaluation ; ne promeut jamais automatiquement."""
    resolus = []
    for r in rows:
        debut = CO.instant(r.get('debut_utc'))
        if debut <= CO.instant(GEL_UTC):
            raise ValueError('Un pronostic antérieur ou égal au gel ne peut pas confirmer ce candidat.')
        if not r.get('resultat_resolu'):
            continue
        if (not r.get('pronostic_fige') or not r.get('apparie_champion')
                or r.get('y') not in (0, 1)):
            raise ValueError('Observation résolue non figée, non appariée ou sans issue binaire.')
        resolus.append(r)
    if resolus:
        y = [r['y'] for r in resolus]
        p0, p1 = [r['controle'] for r in resolus], [r['challenger'] for r in resolus]
        gains = {'log_loss': sum(-math.log(max(min(p0i if cible else 1-p0i, 1-1e-12), 1e-12))
                                  + math.log(max(min(p1i if cible else 1-p1i, 1-1e-12), 1e-12))
                                  for cible, p0i, p1i in zip(y, p0, p1)) / len(y),
                 'brier': sum((a-cible)**2 - (b-cible)**2
                              for cible, a, b in zip(y, p0, p1)) / len(y)}
    else:
        gains = {'log_loss': None, 'brier': None}
    semaines = len({CO.instant(r['debut_utc']).date().isocalendar()[:2] for r in resolus})
    assez = len(resolus) >= minimum_matchs and semaines >= minimum_semaines
    seuil_atteint = bool(assez and gains['log_loss'] >= .001 and gains['brier'] >= 0)
    return {'n_resolus': len(resolus), 'semaines_iso': semaines, 'gains': gains,
            'minimum_matchs': minimum_matchs, 'minimum_semaines_iso': minimum_semaines,
            'criteres_numeriques_atteints': seuil_atteint, 'activation': False,
            'confirmation_manuelle_requise': True,
            'regle': 'IC bootstrap par semaine et contrôles ciblés restent obligatoires avant toute soumission.'}
