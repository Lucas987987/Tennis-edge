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

import charting as CH
import conditions_tournoi as CT
import elo as E
import hierarchie as HI
import match_simule as MS
import profils_service as PS
import pression_v2 as PV2
import styles_joueurs as ST
import variables_pre_match as VP

ELO_CONTROLE = {'poids_surface': .3, 'welo': 'norme', 'incertitude': 5.0}


def cle_match(m):
    """Clé stable pour aligner les prévisions Elo sans utiliser le résultat."""
    joueurs = '|'.join(sorted((m['gagnant'], m['perdant'])))
    return (f"{m['date'].isoformat()}|{joueurs}|{m.get('tournoi_id') or m.get('tournoi') or ''}"
            f"|{m.get('tour', 0)}|{m.get('num', 0)}")


def observations(M, choisis, demi_vie=PS.DEMI_VIE, prior_mult=1.0, sigma=.15,
                 evolutions=False, charting=None, avec_pression_v2=False):
    P, classement = PS.Profils(demi_vie, prior_mult), E.Elo(**ELO_CONTROLE)
    hierarchie = HI.HierarchieServiceRetour() if evolutions else None
    historique, conditions = VP.HistoriquePreMatch(), CT.ConditionsTournoi()
    pression_v2 = PV2.HistoriquePressionV2() if avec_pression_v2 else None
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
                if pression_v2 is not None:
                    pression_v2.ajouter(ancien, p_elo)
            resultats_veille, jour_courant = [], m['date']
        debut = dt.datetime.combine(m['date'], dt.time())
        while attente and attente[0][0] < debut:
            _, _, ancien = heapq.heappop(attente)
            P.ajouter(ancien)
            if hierarchie is not None:
                hierarchie.ajouter(ancien)
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
            if charting is not None:
                nom_h = m.get('nom_g') if h == gagnant else m.get('nom_p')
                nom_a = m.get('nom_p') if h == gagnant else m.get('nom_g')
                kh, ka = E.cle(nom_h), E.cle(nom_a)
                ph, pa = charting.profil(kh, m['date']), charting.profil(ka, m['date'])
                dh, da = charting.documentation(kh, m['date']), charting.documentation(ka, m['date'])
                row.update(CH.variables_match(ph, pa))
                row.update({'mcp_matchs_h': dh['matchs'], 'mcp_matchs_a': da['matchs'],
                            'mcp_points_minimum': min(dh['points_service'] + dh['points_retour'],
                                                      da['points_service'] + da['points_retour']),
                            'mcp_deux_joueurs_couverts': dh['matchs'] > 0 and da['matchs'] > 0})
            if hierarchie is not None:
                sigma_dyn, detail = hierarchie.sigma(h, a, m['date'])
                ch_h = MS.ajuster(ch, hierarchie.point(h, a, m['circuit'], m['surface']))
                ca_h = MS.ajuster(ca, hierarchie.point(a, h, m['circuit'], m['surface']))
                row.update({
                    'hierarchie_service_retour': MS.victoire_pure(ch_h, ca_h, m['bo'] // 2 + 1, sigma),
                    'incertitude_dynamique': MS.victoire_pure(ch, ca, m['bo'] // 2 + 1, sigma_dyn),
                    'hierarchie_incertitude': MS.victoire_pure(ch_h, ca_h, m['bo'] // 2 + 1, sigma_dyn),
                    'sigma_dynamique': sigma_dyn,
                    'hierarchie_point_h': MS.p_service(ch_h),
                    'hierarchie_point_a': MS.p_service(ca_h),
                    **detail,
                })
            row.update(historique.features(m, h, a, main_h, main_a))
            if pression_v2 is not None:
                row.update(pression_v2.features(h, a, m['surface'], m['circuit'], m['date']))
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
