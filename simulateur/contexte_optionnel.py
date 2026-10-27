#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Connecteurs optionnels pour horodatages et données physiques réelles.

Aucune valeur n'est inventée. Une donnée absente reste absente ; une donnée
physique n'entre dans aucun pronostic tant qu'un challenger figé n'a pas démontré
son apport. Les horodatages doivent être UTC ou porter un fuseau explicite.
"""
import csv
import datetime as dt
import json

CHAMPS_PHYSIQUES = ('charge_aigue', 'charge_chronique', 'minutes_jouees_7j',
                    'minutes_jouees_28j', 'distance_m', 'sprints', 'fc_moyenne', 'fc_max')


def instant(valeur):
    if not isinstance(valeur, str) or not valeur.strip():
        raise ValueError('Horodatage ISO 8601 obligatoire.')
    try:
        d = dt.datetime.fromisoformat(valeur.strip().replace('Z', '+00:00'))
    except ValueError as e:
        raise ValueError(f'Horodatage invalide: {valeur}') from e
    if d.tzinfo is None:
        raise ValueError('Fuseau horaire obligatoire : ne pas deviner l’heure locale.')
    return d.astimezone(dt.timezone.utc)


def charger(path):
    with open(path, encoding='utf-8') as f:
        if path.lower().endswith('.json'):
            rows = json.load(f)
        else:
            rows = list(csv.DictReader(f))
    if not isinstance(rows, list):
        raise ValueError('Le connecteur attend une liste d’objets.')
    return rows


def horodatages(rows):
    """Index match_id -> horodatage validé ; doublons et fins incohérentes refusés."""
    out = {}
    for r in rows:
        uid = str(r.get('match_id') or '').strip()
        if not uid:
            raise ValueError('match_id obligatoire pour relier un horodatage.')
        debut = instant(r.get('debut'))
        fin = instant(r['fin']) if r.get('fin') else None
        if fin is not None and fin <= debut:
            raise ValueError(f'Fin non postérieure au début pour {uid}.')
        if uid in out:
            raise ValueError(f'Horodatage dupliqué pour {uid}.')
        out[uid] = {'debut_utc': debut.isoformat(), 'fin_utc': fin.isoformat() if fin else None,
                    'source': str(r.get('source') or 'non_precisee')}
    return out


def appliquer_horodatage(match, index):
    """Copie enrichie ; sans identifiant exact, la date de tournoi reste un proxy assumé."""
    out = dict(match)
    uid = str(match.get('match_id') or match.get('uid') or '')
    if uid in index:
        out.update(index[uid])
        out['horodatage_reel'] = True
    else:
        out['horodatage_reel'] = False
    return out


def physiques(rows, date_reference=None):
    """Valide les observations et leur disponibilité ; ne fabrique ni ACWR ni blessure."""
    ref = instant(date_reference) if isinstance(date_reference, str) else date_reference
    out = []
    for r in rows:
        joueur = str(r.get('joueur') or '').strip()
        if not joueur:
            raise ValueError('joueur obligatoire pour une donnée physique.')
        observe = instant(r.get('observe_le'))
        if ref is not None and observe >= ref:
            continue
        valeurs = {}
        for nom in CHAMPS_PHYSIQUES:
            brut = r.get(nom)
            if brut in (None, ''):
                valeurs[nom] = None
                continue
            x = float(brut)
            if x < 0:
                raise ValueError(f'{nom} ne peut pas être négatif.')
            valeurs[nom] = x
        out.append({'joueur': joueur, 'observe_le': observe.isoformat(), 'valeurs': valeurs,
                    'source': str(r.get('source') or 'non_precisee'),
                    'disponible_avant_reference': True})
    return out


def couverture(matchs, index):
    n = len(matchs)
    k = sum(bool(appliquer_horodatage(m, index)['horodatage_reel']) for m in matchs)
    return {'n': n, 'horodatages_reels': k, 'couverture_pct': round(100 * k / n, 2) if n else None,
            'repli': 'tourney_date, proxy prudent ; aucune interpolation'}
