#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Socle commun point-in-time des cinq pistes d'amélioration.

Une seule passe construit les contrôles et toutes les variables nouvelles. Elo,
calendrier, H2H, pression et conditions sont mis à jour au changement de date ;
les profils service–retour conservent leur libération après la fin du tournoi.
Aucune cote n'est lue et aucune sortie du modèle actif n'est modifiée.
"""
import datetime as dt
import heapq

import conditions_tournoi as CT
import elo as E
import match_simule as MS
import profils_service as PS
import styles_joueurs as ST
import variables_pre_match as VP

ELO_CONTROLE = {'poids_surface': .3, 'welo': 'norme', 'incertitude': 5.0}


def cle_match(m):
    """Clé stable pour aligner les prévisions Elo sans utiliser le résultat."""
    joueurs = '|'.join(sorted((m['gagnant'], m['perdant'])))
    return (f"{m['date'].isoformat()}|{joueurs}|{m.get('tournoi_id') or m.get('tournoi') or ''}"
            f"|{m.get('tour', 0)}|{m.get('num', 0)}")


def observations(M, choisis, demi_vie=PS.DEMI_VIE, prior_mult=1.0, sigma=.15):
    P, classement = PS.Profils(demi_vie, prior_mult), E.Elo(**ELO_CONTROLE)
    historique, conditions = VP.HistoriquePreMatch(), CT.ConditionsTournoi()
    attente, serial, out = [], 0, []
    resultats_veille, jour_courant = [], None
    for m in sorted(M, key=lambda x: (x['date'], x.get('tour', 0), x.get('num', 0))):
        if jour_courant != m['date']:
            # Tous les matchs du jour précédent deviennent disponibles ensemble.
            for ancien, p_elo, attendu in resultats_veille:
                classement.maj(ancien['gagnant'], ancien['perdant'], ancien['surface'],
                               ancien.get('niveau') == 'G',
                               E.part_jeux(ancien['sets']) if ancien.get('complet') else None)
                historique.ajouter(ancien, p_elo)
                conditions.ajouter(ancien, attendu)
            resultats_veille, jour_courant = [], m['date']
        debut = dt.datetime.combine(m['date'], dt.time())
        while attente and attente[0][0] < debut:
            _, _, ancien = heapq.heappop(attente)
            P.ajouter(ancien)
        gagnant, perdant = m['gagnant'], m['perdant']
        if m['circuit'] in ('CH', 'ITF'):
            classement.presenter(gagnant, 1200.0)
            classement.presenter(perdant, 1200.0)
        p_gagnant = classement.proba(gagnant, perdant, m['surface'])
        attendu = conditions.attendu(m)
        if id(m) in choisis:
            h, a = sorted((gagnant, perdant))
            ih = ST.instantane(P, h, m['circuit'], m['surface'], m['date'])
            ia = ST.instantane(P, a, m['circuit'], m['surface'], m['date'])
            mu = P.moyenne(m['circuit'], m['surface'])
            ch = MS.composantes(ih['profil'], ia['profil'], mu)
            ca = MS.composantes(ia['profil'], ih['profil'], mu)
            main_h = m.get('main_g') if h == gagnant else m.get('main_p')
            main_a = m.get('main_p') if h == gagnant else m.get('main_g')
            row = {
                'uid': cle_match(m), 'date': m['date'], 'semaine': ST._semaine(m['date']),
                'y': int(gagnant == h), 'elo': p_gagnant if h == gagnant else 1.0 - p_gagnant,
                'service_retour': MS.victoire_pure(ch, ca, m['bo'] // 2 + 1, sigma),
                'surface': m['surface'], 'circuit': m['circuit'], 'bo': m['bo'],
                'documentation_balles': min(ih['balles_effectives'], ia['balles_effectives']),
                'documentation_matchs': min(classement.matchs(h), classement.matchs(a)),
            }
            row.update(historique.features(m, h, a, main_h, main_a))
            row.update(conditions.features(m, h, a, ih['profil'], ia['profil'], historique))
            repos_h, _ = historique._repos(h, m['date'])
            repos_a, _ = historique._repos(a, m['date'])
            row['transition_surface'] = bool(row['fatigue_transition_surface'])
            row['retour_absence_30j'] = max(repos_h, repos_a) >= 30
            out.append(row)
        resultats_veille.append((m, p_gagnant, attendu))
        heapq.heappush(attente, (dt.datetime.combine(m['fin'], dt.time()), serial, m))
        serial += 1
    return out
