#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Indice de robustesse d'un pronostic indépendant, appris seulement sur les matchs déjà résolus.

La note ne prédit pas que le favori va gagner : elle résume la qualité des entrées, l'accord entre
Elo et simulation, la calibration historique et la performance passée sur le circuit, toujours à
partir de pronostics antérieurs. Elle ne modifie aucune probabilité. Aucune cote.
"""
import math

VERSIONS = ('combinaison', 'simulation', 'stats')
VERSION_FIABILITE = 'circuit_v1'
ACTIVE_LE = '2026-10-27'
SEUILS = {'prudent': 45, 'correct': 65, 'solide': 80}
NIVEAUX = ('fragile', 'prudent', 'correct', 'solide')
CATEGORIES = ('A_solide', 'B_incertain', 'C_fragile', 'D_non_controle')


def niveau(note):
    return 'fragile' if note < SEUILS['prudent'] else 'prudent' if note < SEUILS['correct'] else 'correct' if note < SEUILS['solide'] else 'solide'


def _lg(p):
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def variante(bloc):
    for k in VERSIONS:
        v = (bloc or {}).get(k) or {}
        if v.get('p_home') is not None:
            return k, v
    return None, {}


def enregistrements(doc):
    """Observations antérieures, une par match, sans duplication home/away."""
    out = []
    for m in (doc or {}).get('matchs') or []:
        reel = m.get('reel') or {}
        if reel.get('interrompu') or reel.get('gagnant') not in ('home', 'away'):
            continue
        premier = m.get('premier') or {}
        k, v = variante(premier)
        p = m.get('p_affiche', v.get('p_home'))
        if p is None:
            continue
        out.append({'uid': m.get('uid'), 'p': float(p), 'y': int(reel['gagnant'] == 'home'),
                    'circuit': m.get('circuit'), 'surface': m.get('surface')})
    return out


def calibration_locale(p, circuit, surface, historique, uid=None):
    """Calibration locale pondérée ; n efficace et taux réel sont retournés pour transparence."""
    poids, sp, sy = [], [], []
    for r in historique:
        if uid is not None and r.get('uid') == uid:
            continue
        distance = abs(r['p'] - p)
        if distance > 0.15:
            continue
        w = max(0.0, 1 - distance / 0.15)
        w *= 2.0 if r.get('circuit') == circuit else 0.5
        w *= 1.5 if r.get('surface') == surface else 1.0
        if w:
            poids.append(w)
            sp.append(w * r['p'])
            sy.append(w * r['y'])
    n = sum(poids)
    if not n:
        return {'n': 0.0, 'score': 0.5, 'ecart': None}
    prevu, reel = sum(sp) / n, sum(sy) / n
    ecart = reel - prevu
    # Peu d'historique : on se rapproche d'une note neutre plutôt que d'inventer une certitude.
    brut = 1 - min(abs(ecart) / 0.20, 1.0)
    score = 0.5 + (n / (n + 80.0)) * (brut - 0.5)
    return {'n': round(n, 1), 'score': score, 'ecart': round(ecart, 4),
            'prevu': round(prevu, 4), 'reel': round(reel, 4)}


def performance_circuit(circuit, historique):
    """Performance passée du modèle sur ce circuit, relative à sa confiance.

    La perte résiduelle retranche l'entropie attendue : un circuit avec beaucoup
    de matchs équilibrés n'est pas pénalisé simplement parce que sa réussite brute
    est plus faible. Toutes les observations sont censées être antérieures au
    match ; sans historique, la composante reste neutre et non optimiste.
    """
    rows = [r for r in historique if circuit and r.get('circuit') == circuit]
    n = len(rows)
    if not n:
        return {'n': 0, 'score': .5, 'perte_residuelle': None, 'log_loss': None,
                'exactitude': None, 'exactitude_attendue': None}
    residus, exactes, attendues, pertes = [], [], [], []
    for r in rows:
        p = min(1 - 1e-12, max(1e-12, float(r['p'])))
        y = int(r['y'])
        perte = -math.log(p if y else 1-p)
        entropie = -(p*math.log(p) + (1-p)*math.log(1-p))
        residus.append(perte-entropie)
        pertes.append(perte)
        exactes.append(float((p >= .5) == bool(y)))
        attendues.append(max(p, 1-p))
    residuel = sum(residus)/n
    brut = 1 / (1 + math.exp(residuel/.08))
    score = .5 + n/(n+80.0)*(brut-.5)
    return {'n': n, 'score': score, 'perte_residuelle': round(residuel, 6),
            'log_loss': round(sum(pertes)/n, 6),
            'exactitude': round(sum(exactes)/n, 6),
            'exactitude_attendue': round(sum(attendues)/n, 6)}


def categorie(donnees, desaccord, stabilite=None, historique_effectif=0,
              performance=None):
    """Catégorie descriptive figée avant le résultat ; elle ne change jamais la probabilité.

    A : composantes d'accord, joueurs documentés, score modal contrôlé et historique suffisant.
    B : estimation encore incertaine (documentation, stabilité ou profondeur historique).
    C : Elo et simulation désignent deux vainqueurs différents.
    D : entrées trop pauvres pour prétendre contrôler la robustesse.
    """
    if donnees < .20:
        return 'D_non_controle'
    if desaccord:
        return 'C_fragile'
    circuit_fragile = (performance or {}).get('n', 0) >= 30 and (performance or {}).get('perte_residuelle', 0) > .05
    if (donnees < .65 or stabilite in ('fragile', 'instable', 'non_controle')
            or historique_effectif < 30 or circuit_fragile):
        return 'B_incertain'
    return 'A_solide'


def evaluer(match, historique):
    k, v = variante(match)
    if not k:
        return None
    p = float(v['p_home'])
    sim = v.get('match_simule') or {}
    profils = sim.get('profil_connu') or match.get('style_connu') or [False, False]
    experience = match.get('matchs_joues') or [0, 0]
    donnees_joueurs = []
    for connu, n in zip(profils, experience):
        donnees_joueurs.append(0.5 * bool(connu) + 0.5 * min(max((n or 0) / 30.0, 0.0), 1.0))
    donnees = sum(donnees_joueurs) / 2 if donnees_joueurs else 0.0
    p_elo = (match.get('stats') or {}).get('p_home')
    p_sim = (match.get('simulation') or {}).get('p_home')
    accord = math.exp(-abs(_lg(p_elo) - _lg(p_sim)) / 1.2) if p_elo is not None and p_sim is not None else 0.5
    desaccord = (p_elo is not None and p_sim is not None
                 and (p_elo >= .5) != (p_sim >= .5))
    ecart = abs(float(p_elo) - float(p_sim)) if p_elo is not None and p_sim is not None else None
    stabilite = ((v.get('match_simule') or {}).get('stabilite_score') or {}).get('statut')
    hist = calibration_locale(p, match.get('circuit'), match.get('surface'), historique, match.get('uid'))
    circuit = performance_circuit(match.get('circuit'), historique)
    preuve = min(hist['n'] / 200.0, 1.0)
    note_avant = round(100 * (0.40 * donnees + 0.20 * accord + 0.30 * hist['score'] + 0.10 * preuve))
    note = round(100 * (0.30 * donnees + 0.15 * accord + 0.20 * hist['score']
                        + 0.25 * circuit['score'] + 0.10 * preuve))
    # Une contre-performance circuit suffisamment documentée interdit une note élevée.
    plafond = 64 if circuit['n'] >= 30 and (circuit['perte_residuelle'] or 0) > .05 else 100
    note = min(note, plafond)
    cat = categorie(donnees, desaccord, stabilite, hist['n'], circuit)
    return {'note': note, 'niveau': niveau(note), 'categorie': cat, 'version': k,
            'version_fiabilite': VERSION_FIABILITE, 'active_le': ACTIVE_LE,
            'composantes': {'donnees': round(100 * donnees), 'accord_modeles': round(100 * accord),
                            'calibration': round(100 * hist['score']), 'performance_circuit': round(100 * circuit['score']),
                            'profondeur_historique': round(100 * preuve)},
            'performance_circuit': {k: circuit[k] for k in ('n', 'perte_residuelle', 'log_loss', 'exactitude', 'exactitude_attendue')},
            'note_avant_composante_circuit': note_avant,
            'note_avant_plafond_circuit': note,
            'plafond_circuit': plafond,
            'desaccord_vainqueur_elo_simulation': desaccord,
            'ecart_elo_simulation': round(ecart, 4) if ecart is not None else None,
            'stabilite_score_modal': stabilite or 'non_controle',
            'historique_effectif': hist['n'], 'ecart_calibration': hist['ecart'],
            'definition': "Robustesse de l'estimation, pas probabilité que le favori gagne."}


def ajouter(matchs, resultats):
    historique = enregistrements(resultats)
    import matchs_similaires as MS
    anciens = (resultats or {}).get('matchs') or []
    for m in matchs or []:
        note = evaluer(m, historique)
        if note:
            # Le voisinage reste descriptif : il ne modifie ni p ni la note championne.
            note['matchs_similaires'] = MS.resumer(m, anciens)
            m['fiabilite'] = note
    return matchs
