#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Indice de robustesse d'un pronostic indépendant, appris seulement sur les matchs déjà résolus.

La note ne prédit pas que le favori va gagner : elle résume la qualité des entrées, l'accord entre
Elo et simulation, la calibration historique et la performance passée sur le circuit, toujours à
partir de pronostics antérieurs. Elle ne modifie aucune probabilité. Aucune cote.
"""
import math

VERSIONS = ('combinaison', 'simulation', 'stats')
# 04/11/2026 — NOTE V3 AFFICHÉE (définition de Lucas : « plus la note est proche de 100, plus nos % sont la réalité ») :
# la pente d'étalonnage de la case du match (etude_fiabilite_v3.py : circuit × expérience du moins connu × ampleur des
# signaux appliqués), apprise sur l'archive 2016–2022 ; jugée sur 2023 → : tiers haut pente 0,98 et 0,5 point
# d'erreur d'étalonnage, tiers bas pente 0,76 et 3,1 points. La v1 reste calculée à côté (note_v1).
VERSION_FIABILITE = 'pente_v3'
ACTIVE_LE = '2026-11-05'
# 25/11/2026 (paquet 451, Lucas : « chaque match est indépendant […] un match peut être fiable de 0 à 100 % ») : NOTE
# MESURÉE MATCH PAR MATCH (simulateur/note_par_match.py, règle et garde-fou dans son en-tête) : pente de base de la
# classe d'expérience × effet mesuré de chaque critère du match, sans plafond ; catégories pour lire vite. Tant qu'elle
# n'est pas retirée par son garde-fou, c'est la version affichée (bilan par niveau à partir du 25/11, sans mélange).
try:
    import json as _json
    import os as _os
    with open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'note_par_match.json'), encoding='utf-8') as _f:
        if not _json.load(_f).get('retire'):
            VERSION_FIABILITE, ACTIVE_LE = 'par_match', '2026-11-25'
except (OSError, ValueError):
    pass
SEUILS_V3 = {'prudent': 78, 'correct': 85, 'solide': 93}
_MODELE_V3 = {}


def modele_v3():
    if 'm' not in _MODELE_V3:
        import json
        import os
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rapport_fiabilite_v3.json'),
                      encoding='utf-8') as f:
                doc = json.load(f)
            _MODELE_V3['m'] = doc.get('modele') if doc.get('adopte') else None
        except (OSError, ValueError):
            _MODELE_V3['m'] = None
    return _MODELE_V3['m']


# 25/11/2026 (paquet 450, DÉCISION DE LUCAS après etude_note_v3_challenger.py, paquet 449) : en CHALLENGER, la note v3
# prend les pentes réapprises sur le rejeu comme en production (résultats ITF hommes compris) : une pente par classe
# d'expérience du moins connu (simulateur/note_v3_challenger.json). ATP et WTA ne changent pas. L'ancienne note reste
# calculée à côté (note_v3_ancienne, niveau_ancien) : la correction Challenger « correct » (paquet 270) vise toujours les
# matchs que l'ANCIENNE note classe « correct » (niveau_correction), donc aucun % ne change. Retrait automatique :
# simulateur/note_v3_challenger.py (règle dans le fichier de décision).
NOTE_V3_CHALLENGER = 'note_v3_challenger.json'
_MODELE_CH = {}


def modele_v3_challenger():
    """{classe: pente} de la note v3 Challenger réapprise, ou None (absente ou retirée)."""
    if 'm' not in _MODELE_CH:
        import json
        import os
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), NOTE_V3_CHALLENGER), encoding='utf-8') as f:
                doc = json.load(f)
            _MODELE_CH['m'] = None if doc.get('retire') else {k: float(v) for k, v in (doc.get('pentes') or {}).items()}
        except (OSError, ValueError):
            _MODELE_CH['m'] = None
    return _MODELE_CH['m']


_MODELE_PM = {}


def modele_par_match():
    """Le modèle de la note par match (simulateur/note_par_match.json), ou None (absent, sans effets ou retiré)."""
    if 'm' not in _MODELE_PM:
        import note_par_match as NP
        d = NP.charger()
        _MODELE_PM['m'] = d if d and not d.get('retire') and d.get('effets') else None
    return _MODELE_PM['m']


_INDEX_JOUEURS = {}


def note_du_match(match, p, p_elo, p_sim, historique=None):
    """Paquet 451 : la note mesurée de CE match (note, pente, sens, effets), ou None. Paquet 452 : avec la note de
    fiabilité des deux joueurs, tirée de leurs seuls matchs publiés d'avant le jour du match (historique)."""
    M = modele_par_match()
    c = match.get('circuit')
    mj = [x for x in (match.get('matchs_joues') or []) if x is not None]
    if not M or c not in ('ATP', 'WTA', 'CH') or len(mj) < 2:
        return None
    import note_par_match as NP
    r = {'p': float(p), 'pe': p_elo, 'ps': p_sim, 'xp': min(mj), 'tour': match.get('tour'),
         'p0': match.get('p_premier'), 'p1': (match.get('combinaison') or {}).get('p_home')}
    xj = 0.0
    if historique:
        try:
            if _INDEX_JOUEURS.get('id') != id(historique):
                _INDEX_JOUEURS.update(id=id(historique), idx=NP.index_joueurs(historique))
            jour = str(match.get('debut') or '')[:10] or '9999'
            xj = NP.x_joueur(_INDEX_JOUEURS['idx'], match.get('home'), match.get('away'), jour)
        except Exception:  # noqa: BLE001 — la note des joueurs ne doit jamais bloquer la fiabilité
            xj = 0.0
    out = NP.evaluer_match(M, c, min(mj), NP.criteres_du_match(r, xj))
    if out is not None:
        out['joueur_peu_fiable'] = round(xj, 3)
    return out


def niveau_v3(note):
    s = SEUILS_V3
    return 'fragile' if note < s['prudent'] else 'prudent' if note < s['correct'] else 'correct' if note < s['solide'] else 'solide'


_ACTIFS = {}


def criteres_fragiles(match, p, p_elo, p_sim):
    """Clés des critères de fragilité en vigueur que ce match remplit (surveillance_fragilite.CRITERES)."""
    import os
    import surveillance_fragilite as SF
    if 'a' not in _ACTIFS:
        _ACTIFS['a'] = SF.actifs(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    mj = [x for x in (match.get('matchs_joues') or []) if x is not None]
    r = {'p': float(p), 'pe': p_elo, 'ps': p_sim, 'xp': min(mj) if len(mj) == 2 else None, 'tour': match.get('tour'),
         'p0': match.get('p_premier'), 'p1': (match.get('combinaison') or {}).get('p_home')}
    return sorted(k for k in _ACTIFS['a'] if k in SF.CRITERES and SF.CRITERES[k][1](r))


def note_v3(match, ancienne=False):
    """Note v3 du match, ou None (modèle absent, circuit hors ATP / WTA / Challenger, expérience inconnue).
    Challenger : pentes réapprises (paquet 450) tant qu'elles ne sont pas retirées ; ancienne=True : l'ancienne note."""
    M = modele_v3()
    c = match.get('circuit')
    n = [x for x in (match.get('matchs_joues') or []) if x is not None]
    if not M or c not in ('ATP', 'WTA', 'CH') or len(n) < 2:
        return None
    import etude_fiabilite_v3 as V3
    MC = modele_v3_challenger() if c == 'CH' and not ancienne else None
    if MC:
        a = MC.get(str(V3.classe_experience(min(n))), MC.get('_circuit'))
        return V3.note(a) if a else None
    sc = ((match.get('controle') or {}).get('signaux_circuit') or {}).get('decalages') or {}
    return V3.note_du_match(M, c, min(n), sum(sc.values()))
def pente_v3(match):
    """21/11/2026 (paquet 318) : la pente d'étalonnage a de la case du match (celle dont la note v3 est tirée), ou None."""
    M = modele_v3()
    c = match.get('circuit')
    n = [x for x in (match.get('matchs_joues') or []) if x is not None]
    if not M or c not in ('ATP', 'WTA', 'CH') or len(n) < 2:
        return None
    import etude_fiabilite_v3 as V3
    sc = ((match.get('controle') or {}).get('signaux_circuit') or {}).get('decalages') or {}
    m = M.get(V3.case(c, min(n), sum(sc.values())))
    a = m['pente'] if m else (M.get('_circuits') or {}).get(c)
    return float(a) if a else None


# 29/10/2026 — NOTE V2 EN FANTÔME : la même note SANS la composante « calibration » (la plus liée à l'erreur, dans le
# mauvais sens, sur les 79 premiers matchs notés). Calculée à côté, jamais affichée sur les matchs ; jugée seulement
# sur les matchs pronostiqués à partir du 30/10 (les 79 qui l'ont suggérée n'en font pas partie), avec la même règle
# que la note en place (rapport_validation_fiabilite.json). Poids : ceux de la v1 sans la calibration, renormalisés.
VERSION_V2 = 'sans_calibration_v1'
ACTIVE_V2_LE = '2026-10-30'
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
                    'circuit': m.get('circuit'), 'surface': m.get('surface'),
                    'home': m.get('home'), 'away': m.get('away'), 'debut': m.get('debut')})   # paquet 452 : note des joueurs
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
    note_v2 = min(round(100 * (0.30 * donnees + 0.15 * accord + 0.25 * circuit['score'] + 0.10 * preuve) / 0.80), plafond)
    v3 = note_v3(match)
    note_v1, niveau_v1 = note, niveau(note)
    if v3 is not None:
        note = v3
    # 04/11/2026 (décision de Lucas) : Elo et simulation désignent des favoris DIFFÉRENTS → « fragile » d'office
    # (nos pronostics rejoués : 54 % de bons vainqueurs, log loss 0,686, presque pile ou face ; pente d'étalonnage
    # 0,32 sur octobre–novembre). Les autres critères testés (rapport_criteres_fragilite.json) ne tiennent pas.
    # 04/11/2026 : critères de fragilité EN VIGUEUR, revérifiés chaque semaine (surveillance_fragilite.py)
    criteres = criteres_fragiles(match, p, p_elo, p_sim) if v3 is not None else []
    fragile_force = 'favoris_opposes' in criteres
    if criteres:
        note = min(note, SEUILS_V3['prudent'] - 1)
    ancien = {}
    if v3 is not None and match.get('circuit') == 'CH' and modele_v3_challenger():
        v3a = note_v3(match, ancienne=True)          # paquet 450 : l'ancienne note, gardée pour la correction et le retrait
        if v3a is not None:
            na = min(v3a, SEUILS_V3['prudent'] - 1) if criteres else v3a
            ancien = {'note_v3_ancienne': v3a, 'note_ancienne': na, 'niveau_ancien': niveau_v3(na), 'niveau_correction': niveau_v3(na),
                      'note_v3_challenger': 'comme_en_production_450'}
    nm = note_du_match(match, p, p_elo, p_sim, historique) if v3 is not None else None
    if nm:
        # paquet 451 : la note mesurée match par match remplace la note v3 plafonnée, gardée à côté (garde-fou et
        # correction Challenger « correct », qui vise toujours les mêmes matchs : aucun % ne change)
        a_case = pente_v3(match) or 1.0
        a_anc = a_case if note >= (v3 or 0) else ((SEUILS_V3['prudent'] - 1) / 100 if a_case <= 1 else 100 / (SEUILS_V3['prudent'] - 1))
        ancien = {'note_ancienne': note, 'niveau_ancien': niveau_v3(note), 'niveau_correction': niveau_v3(note),
                  'pente_ancienne': round(a_anc, 4), 'note_par_match': nm['note'], 'pente_du_match': nm['pente_du_match'],
                  'pente_de_base': nm['pente_de_base'], 'effets_criteres': nm['effets_criteres'], 'sens': nm['sens'],
                  'joueur_peu_fiable': nm.get('joueur_peu_fiable'),
                  'methode': 'par_match_451', 'niveau_note': niveau_v3(nm['note'])}
        note = nm['note']
    # paquet 464 : deux niveaux mesurés (fragile / normal) quand la note par match est en place ; les quatre niveaux de
    # la note restent dans « niveau_note » (descriptif), la correction Challenger vise toujours « niveau_correction »
    niv = nm.get('niveau_mesure') if nm and nm.get('niveau_mesure') else (niveau_v3(note) if v3 is not None else niveau_v1)
    return {**ancien, 'note': note, 'niveau': niv, 'categorie': cat, 'version': k,
            'note_v1': note_v1, 'niveau_v1': niveau_v1, 'note_v3': v3,
            'fragile_desaccord_modeles': fragile_force, 'fragile_criteres': criteres,
            'note_v2': note_v2, 'niveau_v2': niveau(note_v2), 'version_v2': VERSION_V2,
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
            'definition': ("Plus la note est proche de 100, plus nos % se sont réalisés tels quels dans ce type de match. "
                           "Robustesse de l'estimation, pas probabilité que le favori gagne.")}


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
