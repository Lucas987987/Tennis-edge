#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gel et confirmation future des challengers algorithmiques.

Le diagnostic historique ne peut pas promouvoir un candidat. Seuls des pronostics
figés postérieurs au gel, appariés au champion et résolus ensuite, alimentent la
confirmation finale. Toute modification exige une nouvelle version du candidat.
"""
import datetime as dt
import hashlib
import json
import os

FICHIER = 'candidats_algorithmes.json'


def charger(racine='.'):
    chemin = os.path.join(racine, 'simulateur', FICHIER)
    with open(chemin, encoding='utf-8') as f:
        return json.load(f)


def empreinte_candidat(candidat):
    brut = json.dumps(candidat, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(brut).hexdigest()


def empreintes(manifeste):
    return {nom: empreinte_candidat(c) for nom, c in manifeste['candidats'].items()}


def auditer(manifeste, observations=None, empreintes_gel=None):
    """Vérifie le manifeste et, si fourni, les nouvelles observations résolues."""
    problemes = []
    if manifeste.get('schema') != 'candidats_algorithmes_v1':
        problemes.append('Schéma de manifeste inconnu.')
    try:
        gel = dt.date.fromisoformat(manifeste['fige_le'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('Date de gel absente ou invalide.')
    if empreintes_gel is not None and empreintes(manifeste) != empreintes_gel:
        problemes.append('Un candidat a changé : créer une nouvelle version et remettre sa confirmation à zéro.')
    for nom, c in manifeste.get('candidats', {}).items():
        if c.get('activation') is not False:
            problemes.append(f'{nom}: activation interdite par ce chantier de diagnostic.')
        if c.get('statut') != 'diagnostic':
            problemes.append(f'{nom}: statut initial attendu = diagnostic.')
        if not c.get('implementation'):
            problemes.append(f'{nom}: implémentation non traçable.')
    confirmation = {'eligible': False, 'n': 0, 'semaines': 0, 'raison': 'aucune observation fournie'}
    if observations is not None:
        rows = list(observations)
        dates = []
        for r in rows:
            d = r.get('date')
            if isinstance(d, str):
                d = dt.date.fromisoformat(d)
            if not isinstance(d, dt.date):
                raise ValueError('Chaque observation doit avoir une date ISO.')
            if d <= gel:
                problemes.append('Une observation antérieure ou égale au gel ne peut pas confirmer un candidat.')
            if not r.get('pronostic_fige') or not r.get('resultat_resolu') or not r.get('apparie_champion'):
                problemes.append('Pronostic figé, résultat résolu et appariement champion obligatoires.')
                break
            dates.append(d)
        semaines = len({d.isocalendar()[:2] for d in dates})
        regles = manifeste['confirmation_finale']
        confirmation = {
            'eligible': not problemes and len(rows) >= regles['minimum_matchs'] and semaines >= regles['minimum_semaines_iso'],
            'n': len(rows), 'semaines': semaines,
            'minimum_matchs': regles['minimum_matchs'], 'minimum_semaines_iso': regles['minimum_semaines_iso'],
            'raison': 'fenêtre future suffisante' if len(rows) >= regles['minimum_matchs'] and semaines >= regles['minimum_semaines_iso']
                      else 'accumuler uniquement de nouveaux pronostics figés et résolus',
        }
    return {'ok': not problemes, 'problemes': sorted(set(problemes)), 'fige_le': str(gel),
            'empreintes': empreintes(manifeste), 'confirmation_future': confirmation,
            'diagnostic_historique_peut_activer': False}
