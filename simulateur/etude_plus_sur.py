#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_plus_sur.py — QUAND L'ELO ET LA SIMULATION DIVERGENT, QUI A RAISON ? LE POIDS DE LA SIMULATION DOIT-IL DÉPENDRE
DU MODÈLE LE PLUS SÛR ? (26/11/2026, paquet 469, question de Lucas.)

POURQUOI CETTE PISTE. Constat sur nos matchs publiés (Tennis_Edge_Lab/live/pronostics_resultats.json, 23/10 → 26/11,
même favori pour les deux modèles et au moins 10 points d'écart entre eux) :
  - Elo plus sûr (208 matchs) : Elo 77 %, simulation 61 %, affiché 75,7 % ; le favori gagne 75,5 % ± 3,0 ;
  - simulation plus sûre (242 matchs) : Elo 61 %, simulation 76 %, affiché 67,6 % ; le favori gagne 71,1 % ± 2,9 ;
  - vainqueurs différents, Challenger (274 matchs) : l'Elo a raison 58 % du temps, la simulation 42 %.
Le mélange σ(a · logit Elo + b · logit simulation) a les mêmes poids (a, b) quel que soit le modèle le plus sûr. Le
constat laisse penser que le % affiché suit bien l'Elo quand il est le plus sûr, et pas assez la simulation quand
c'est elle. Ces chiffres ont DÉJÀ ÉTÉ VUS, sur quelques centaines de matchs : ils ne jugent rien.

DÉJÀ ESSAYÉ DANS LE DÉPÔT (vérifié avant d'écrire : simulateur/etude_*.py, backtest_match_simule.py, journal) — aucune
étude ne fait dépendre les poids du modèle le plus sûr :
  - etude_desaccord_modeles.py (04/11, rejeté) : rapprocher de 50 % les matchs en désaccord (vainqueurs différents OU
    10 points d'écart), sans regarder lequel des deux est le plus sûr ;
  - entrainement_progressif.desaccord_wta (29/10, pas adopté) et suivi du paquet 383 (Challenger, en cours) : mélange
    propre aux seuls matchs où les deux modèles ne désignent PAS le même vainqueur ;
  - etude_poids_elo_simulation.py (05/11), etude_par_circuit.py (255), etude_peu_documentes.py (462) : poids selon
    l'expérience, le circuit, la documentation ;
  - etude_pente_melange.py (465) : une pente sur le % final, pas les poids.

CANDIDATS (fixés AVANT tout résultat). « Plus sûr » = le plus loin de 50 % : la simulation est la plus sûre si
|logit simulation| > |logit Elo|, sinon c'est l'Elo. « Écart » = |% Elo − % simulation| pour le même joueur, en points.
  - TÉMOIN « poids uniques réappris » : un seul couple (a, b) par circuit, réappris sur la période d'apprentissage.
    Sans lui, un gain ne serait peut-être qu'un réapprentissage des poids en place.
  - DEUX RÉGIMES : un couple (a, b) quand l'Elo est le plus sûr, un autre quand c'est la simulation.
  - TROIS RÉGIMES : moins de 10 points d'écart · 10 points et plus avec l'Elo plus sûr · 10 points et plus avec la
    simulation plus sûre (les vainqueurs différents à 10 points et plus vont dans le régime du plus sûr des deux).
  Tous les poids sont appris par maximum de vraisemblance (Newton, départ aux poids en place, bornés entre 0 et 2, au
  moins 300 matchs du régime ; en dessous, le régime garde les poids du témoin). Les signaux en service restent
  appliqués par-dessus, inchangés. Le régime ne dépend que des deux % d'avant match : aucune fuite.

REJEU, COMME EN PRODUCTION (celui de etude_pente_melange.rejeu, donc de etude_peu_documentes.rejeu, réutilisé sans le
modifier) : Elo de production (archive depuis 2012 + résultats ITF hommes du dépôt, départs par niveau), simulation de
base rejouée avec des profils refaits au plus tard tous les 7 jours sur les seuls tournois terminés avant le match.
Un seul passage du 01/06/2024 au 31/05/2026. Le rejeu s'arrête si aucun résultat ITF hommes n'est lu.
BASE « COMME EN PLACE » (celle de l'étude 465, etude_pente_melange.z_base) : poids du mélange de la production
(choix_simulation.json, poids_circuit.json), « documentation faible » et « favori le moins documenté » en Challenger,
pente du Challenger sur terre appliquée en dernier. Non rejouée, comme au 465 : la correction Challenger « correct ».
Matchs : ATP, WTA, Challenger, sans abandon ni compétition par équipes. ITF : données seulement, jamais pronostiqué.

PÉRIODES. Les résultats ITF hommes du dépôt commencent en juin 2024 : aucun rejeu comme en production avant.
  apprentissage : 01/01/2025 → 31/05/2026 ;
  jugement, UNE SEULE FOIS : 01/06/2024 → 31/12/2024.
Ce que la période jugée n'est PAS, écrit avant tout résultat :
  - elle a déjà servi une fois, à l'étude 465 (pentes du % final) : neuve pour CETTE question (aucun poids par régime,
    aucun « qui est le plus sûr » n'y a été mesuré), pas vierge ;
  - en ATP et en WTA, les poids EN PLACE ont été appris sur des matchs qui la contiennent (backtest_match_simule.py :
    2024 → janvier 2026 ; poids propres à l'ATP : 2024). Cela avantage la base « en place », pas le jugement : le
    verdict compare le candidat au TÉMOIN, et tous deux n'apprennent que sur 01/2025 → 05/2026. Les gains « face aux
    poids en place » sont publiés à titre indicatif seulement ;
  - en Challenger, l'Elo n'y a que 0 à 7 mois de résultats ITF (le contrôle « Elo en chauffe » du 465 est republié) :
    la confiance relative de l'Elo et de la simulation peut y différer de celle d'aujourd'hui.

RÈGLE ÉCRITE LE 26/11/2026, AVANT TOUT RÉSULTAT (par circuit, pour chaque candidat à part) :
  « matchs concernés » = les matchs dont le régime change quelque chose : le % du candidat s'écarte d'au moins
  1 point du % du témoin. Mesure : gain de log loss par match concerné (témoin − candidat), avec son erreur type.
  Un candidat est RETENU sur un circuit si, à la fois :
    1. au moins 1 000 matchs concernés jugés (« on ne juge rien sur 100 matchs ») ;
    2. gain jugé ≥ 0,001 par match concerné, face au témoin « poids uniques réappris » ;
    3. même sens en sens inverse : témoin et candidat réappris sur la période jugée, appliqués à l'apprentissage, le
       candidat y gagne aussi (gain > 0 sur ses matchs concernés), et la part de la simulation b / (a + b) bouge dans
       le même sens entre « Elo plus sûr » et « simulation plus sûre » sur les deux périodes (à moins de 0,01
       d'écart : « inchangé », non retenu) ;
    4. gain jugé de plus de 2 erreurs types.
  Sinon : chiffres publiés, AUCUNE décision. Rien n'entre en production par ce paquet : le verdict est proposé à Lucas.
  Publiés sans décider : la table « qui a raison » sur le rejeu (par circuit, par période et par régime : même favori
  et 10 points d'écart avec l'Elo plus sûr, avec la simulation plus sûre, vainqueurs différents) ; le gain sur tous
  les matchs ; le gain régime par régime ; le gain face aux poids en place ; trois régimes moins deux régimes ; un
  second témoin « une pente par régime » (poids du témoin, une pente par régime) pour savoir si un gain vient de la
  PART de la simulation ou seulement de la confiance ; et, en confirmation seulement, la même table et les mêmes
  poids sur nos matchs publiés (dont le % « stats » porte déjà d'autres signaux que l'Elo).

REPORT EN PRODUCTION (écrit avant tout résultat). Le rejeu n'a que la simulation de base : sans les couches du lundi
(facteurs, modèle d'arbres, profils hiérarchiques) ni les autres signaux. Des poids retenus ici ne seraient qu'un
point de départ : mise en service seulement avec les deux % gardés dans la fiche et une règle de retrait cumulée.

Rapport public : simulateur/rapport_plus_sur.json — comptes et moyennes seulement, aucun nom de joueur.
Usage : python simulateur/etude_plus_sur.py /tmp/sackmann . [--lignes=/tmp/lignes.json.gz]
        python simulateur/etude_plus_sur.py --journal-depuis-rapport simulateur/rapport_plus_sur.json
"""
import datetime as dt
import gzip
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_etalonnage_cases as EC  # noqa: E402
import etude_pente_melange as PM  # noqa: E402  (rejeu, base « comme en place », Elo en chauffe : réutilisés tels quels)
import etude_peu_documentes as PD  # noqa: E402  (mélange et signaux de documentation : réutilisés tels quels)

PAQUET = 469
DEBUT, COUPURE, FIN = PM.DEBUT, PM.COUPURE, PM.FIN
CIRCUITS = ('ATP', 'WTA', 'CH')
NOM_CIRCUIT = PD.NOM_CIRCUIT
ECART_POINTS = 10.0
SEUIL_CONCERNE = 0.01
MIN_APPRIS, MIN_JUGES, MARGE, MIN_ERREURS_TYPES = 300, 1000, 0.001, 2.0
POIDS_MIN, POIDS_MAX, INCHANGE = 0.0, 2.0, 0.01
ELO, SIM, PROCHES, ELO10, SIM10 = 'elo_plus_sur', 'simulation_plus_sure', 'moins_de_10_points', 'elo_plus_sur_10', 'simulation_plus_sure_10'
CANDIDATS = (('deux_regimes', (ELO, SIM)), ('trois_regimes', (PROCHES, ELO10, SIM10)))
EXTREMES = {'deux_regimes': (ELO, SIM), 'trois_regimes': (ELO10, SIM10)}
LIBELLE = {ELO: 'Elo plus sûr', SIM: 'simulation plus sûre', PROCHES: "moins de 10 points d'écart",
           ELO10: '10 points et plus, Elo plus sûr', SIM10: '10 points et plus, simulation plus sûre',
           'deux_regimes': 'deux régimes', 'trois_regimes': 'trois régimes'}
GROUPES = ('meme_favori_10_points_elo_plus_sur', 'meme_favori_10_points_simulation_plus_sure',
           'meme_favori_moins_de_10_points', 'vainqueurs_differents')
SORTIE = os.path.join(ICI, 'rapport_plus_sur.json')
JOURNAL = os.path.join(ICI, 'journal_changements.json')
GABARIT_JOURNAL = os.path.join(ICI, 'journal_ajouts', 'paquet_469.json')
DIRECT = os.path.join('Tennis_Edge_Lab', 'live', 'pronostics_resultats.json')
REGLE = ("par circuit (ATP, WTA, Challenger) : poids du mélange selon le modèle le plus sûr (deux régimes : Elo plus sûr, "
         "simulation plus sûre ; variante à trois régimes : moins de 10 points d'écart, 10 points et plus avec l'Elo plus "
         "sûr, 10 points et plus avec la simulation plus sûre), appris sur le 01/01/2025 → 31/05/2026 (au moins 300 matchs "
         "par régime), jugés une seule fois sur le 01/06/2024 → 31/12/2024 face à un témoin « poids uniques réappris » sur "
         "la même période ; matchs concernés = ceux dont le % bouge d'au moins 1 point face au témoin ; retenu si au moins "
         "1 000 matchs concernés jugés, gain de log loss ≥ 0,001 par match concerné, même sens en sens inverse (gain aussi, "
         "et part de la simulation qui bouge dans le même sens entre les deux régimes) et gain de plus de 2 erreurs "
         "types ; sinon chiffres publiés, aucune décision")
PERIODE_JUGEE = ("juin → décembre 2024 : seule période rejouable comme en production hors de l'apprentissage (résultats "
                 "ITF hommes depuis juin 2024). Réserves écrites avant tout résultat : elle a déjà servi une fois, à "
                 "l'étude 465 (pentes du % final), jamais à cette question ; en ATP et en WTA les poids en place ont été "
                 "appris sur des matchs qui la contiennent (2024 → janvier 2026, poids propres à l'ATP : 2024), ce qui "
                 "avantage la base « en place » mais pas le jugement, fait face au témoin réappris sur 01/2025 → 05/2026 "
                 "comme le candidat ; en Challenger l'Elo n'y a que 0 à 7 mois de résultats ITF")
LIMITES = ("simulation de base (profils ajustés aux adversaires, refaits tous les 7 jours), sans les couches du lundi "
           "(facteurs, modèle d'arbres, profils hiérarchiques) ni les autres signaux ; la correction Challenger "
           "« correct » n'est pas rejouée ; sur nos matchs publiés, le % « stats » porte déjà d'autres signaux que "
           "l'Elo : confirmation seulement")
fr = PD.fr


# ------------------------------------------------------------------ régimes (ne dépendent que des deux % d'avant match)
def ecart_points(ze, zs):
    """|% Elo − % simulation| pour le même joueur, en points."""
    return 100.0 * abs(EC._sg(ze) - EC._sg(zs))


def plus_sur(ze, zs):
    """Le modèle le plus loin de 50 % ; à égalité, l'Elo."""
    return SIM if abs(zs) > abs(ze) else ELO


def regime_2(ze, zs):
    return plus_sur(ze, zs)


def regime_3(ze, zs):
    if ecart_points(ze, zs) < ECART_POINTS:
        return PROCHES
    return SIM10 if plus_sur(ze, zs) == SIM else ELO10


REGIME = {'deux_regimes': regime_2, 'trois_regimes': regime_3}


def groupe(ze, zs):
    """Case de la table descriptive « qui a raison » (None si l'un des deux modèles est à 50 % pile)."""
    if ze == 0 or zs == 0:
        return None
    if (ze > 0) != (zs > 0):
        return 'vainqueurs_differents'
    if ecart_points(ze, zs) < ECART_POINTS:
        return 'meme_favori_moins_de_10_points'
    return 'meme_favori_10_points_' + plus_sur(ze, zs)


# ------------------------------------------------------------------ mélange avec des poids essayés
def z_de(r, cfg, a, b):
    """Logit du % donné au vainqueur avec les poids (a, b), signaux en service par-dessus comme au 465 : mélange et
    signaux de documentation (PD.z_melange), puis la pente de surface en dernier. z_de(r, cfg, cfg['elo'],
    cfg['simulation']) vaut PM.z_base(r, cfg)."""
    z = PD.z_melange(r, cfg, a=a, b=b)
    k = (cfg.get('surfaces') or {}).get(r[6] if len(r) > 6 else None)
    return z * k if k else z


def termes(r, cfg):
    """(c, da, db) tels que z_de(r, cfg, a, b) = c + a · da + b · db (le mélange est linéaire en a et en b)."""
    c = z_de(r, cfg, 0.0, 0.0)
    return c, z_de(r, cfg, 1.0, 0.0) - c, z_de(r, cfg, 0.0, 1.0) - c


def z_t(t, w):
    return t[0] + w[0] * t[1] + w[1] * t[2]


def _ll_moyenne(T, w):
    return sum(EC.ll(z_t(t, w)) for t in T) / max(len(T), 1)


def _newton(T, a, b, libre=(True, True), tours=60):
    """Maximum de vraisemblance de (a, b) sur les termes T ; libre : quels poids bougent."""
    for _ in range(tours):
        ga = gb = haa = hab = hbb = 0.0
        for c, da, db in T:
            q = EC._sg(c + a * da + b * db)
            ga += (1 - q) * da
            gb += (1 - q) * db
            w = q * (1 - q)
            haa += w * da * da
            hab += w * da * db
            hbb += w * db * db
        haa, hbb = haa + 1e-6, hbb + 1e-6
        if libre == (True, True):
            det = haa * hbb - hab * hab
            if det <= 1e-12:
                break
            pa, pb = (hbb * ga - hab * gb) / det, (haa * gb - hab * ga) / det
        else:
            pa, pb = (ga / haa if libre[0] else 0.0), (gb / hbb if libre[1] else 0.0)
        pa, pb = max(min(pa, 0.5), -0.5), max(min(pb, 0.5), -0.5)
        a, b = a + pa, b + pb
        if abs(pa) + abs(pb) < 1e-8:
            break
    return a, b


def _borne(v):
    return min(max(v, POIDS_MIN), POIDS_MAX)


def apprendre(T, depart):
    """(a, b) appris sur les termes T, départ aux poids en place, bornés entre POIDS_MIN et POIDS_MAX : si le maximum
    libre sort des bornes, le meilleur des maxima avec un poids posé sur sa borne."""
    a, b = _newton(T, depart[0], depart[1])
    if not (POIDS_MIN <= a <= POIDS_MAX and POIDS_MIN <= b <= POIDS_MAX):
        essais = []
        a1, b1 = _newton(T, _borne(a), _borne(b), libre=(False, True))
        essais.append((a1, _borne(b1)))
        a2, b2 = _newton(T, _borne(a), _borne(b), libre=(True, False))
        essais.append((_borne(a2), b2))
        essais.append((_borne(a), _borne(b)))
        a, b = min(essais, key=lambda w: round(_ll_moyenne(T, w), 9))
    return round(a, 4), round(b, 4)


def part_simulation(w):
    s = w[0] + w[1]
    return round(w[1] / s, 4) if s > 1e-9 else None


def pente_de(Z):
    a, _ = EC.pente(Z)
    return min(max(a, PM.PENTE_MIN), PM.PENTE_MAX)


# ------------------------------------------------------------------ jugement d'un candidat
def _apprendre_tout(T, G, regimes, depart):
    """Témoin (un couple) et candidat (un couple par régime ; sous MIN_APPRIS matchs, le régime garde le témoin)."""
    temoin = apprendre(T, depart)
    poids, appris = {}, {}
    for g in regimes:
        Tg = [t for t, x in zip(T, G) if x == g]
        appris[g] = len(Tg) >= MIN_APPRIS
        poids[g] = apprendre(Tg, depart) if appris[g] else temoin
    return temoin, poids, appris


def _ecarts(T, G, temoin, poids):
    """Par match : (régime, concerné ?, log loss du témoin − log loss du candidat)."""
    out = []
    for t, g in zip(T, G):
        zt, zc = z_t(t, temoin), z_t(t, poids[g])
        out.append((g, abs(EC._sg(zc) - EC._sg(zt)) >= SEUIL_CONCERNE, EC.ll(zt) - EC.ll(zc)))
    return out


def _sens(poids, extremes):
    """+1 : la simulation pèse plus quand elle est la plus sûre ; −1 : moins ; 0 : inchangé ; None : indéfini."""
    pe, ps = part_simulation(poids[extremes[0]]), part_simulation(poids[extremes[1]])
    if pe is None or ps is None:
        return None
    return 0 if abs(ps - pe) < INCHANGE else (1 if ps > pe else -1)


LIRE_SENS = {1: 'plus de simulation quand elle est la plus sûre', -1: 'moins de simulation quand elle est la plus sûre',
             0: 'inchangé', None: 'indéfini'}


def _poids_doc(w):
    return {'elo': w[0], 'simulation': w[1], 'part_simulation': part_simulation(w), 'somme': round(w[0] + w[1], 4)}


def juger_candidat(nom, TA, GA, TJ, GJ, depart):
    """Un candidat sur un circuit. TA, TJ : termes de l'apprentissage et de la période jugée ; GA, GJ : leurs régimes ;
    depart : poids en place (elo, simulation)."""
    regimes, extremes = dict(CANDIDATS)[nom], EXTREMES[nom]
    out = {'matchs_apprentissage': len(TA), 'matchs_jugement': len(TJ),
           'regimes': {g: {'matchs_apprentissage': sum(x == g for x in GA), 'matchs_jugement': sum(x == g for x in GJ)}
                       for g in regimes}}
    if len(TA) < MIN_APPRIS or not TJ:
        out['verdict'] = 'aucune décision'
        out['raisons'] = [f"moins de {MIN_APPRIS} matchs pour apprendre" if len(TA) < MIN_APPRIS else 'aucun match jugé']
        return out
    temoin, poids, appris = _apprendre_tout(TA, GA, regimes, depart)
    out['temoin_poids_uniques_reappris'] = _poids_doc(temoin)
    for g in regimes:
        out['regimes'][g]['poids_appris'] = _poids_doc(poids[g])
        out['regimes'][g]['appris'] = appris[g]
    out['sens'] = LIRE_SENS[_sens(poids, extremes)]
    if not any(appris.values()):
        out['verdict'] = 'aucune décision'
        out['raisons'] = [f"aucun régime n'a {MIN_APPRIS} matchs pour apprendre"]
        return out
    EJ, EA = _ecarts(TJ, GJ, temoin, poids), _ecarts(TA, GA, temoin, poids)
    gj = out['gain_jugement_matchs_concernes'] = PD.moyenne([d for _, c, d in EJ if c])
    out['gain_jugement_tous_les_matchs'] = PD.moyenne([d for _, _, d in EJ])
    out['gain_apprentissage_matchs_concernes'] = PD.moyenne([d for _, c, d in EA if c])
    out['erreurs_types'] = round(gj['gain'] / gj['erreur_type'], 2) if gj.get('erreur_type') else None
    for g in regimes:
        out['regimes'][g]['gain_jugement'] = PD.moyenne([d for x, _, d in EJ if x == g])
        out['regimes'][g]['matchs_concernes_jugement'] = sum(1 for x, c, _ in EJ if x == g and c)
    # publié sans décider : le gain face aux poids EN PLACE (tous les matchs jugés), témoin et candidat
    out['face_aux_poids_en_place_jugement'] = {
        'temoin': PD.moyenne([EC.ll(z_t(t, depart)) - EC.ll(z_t(t, temoin)) for t in TJ]),
        'candidat': PD.moyenne([EC.ll(z_t(t, depart)) - EC.ll(z_t(t, poids[g])) for t, g in zip(TJ, GJ)])}
    # second témoin, sans décider : poids du témoin, UNE PENTE par régime (la confiance seule, pas la part)
    pentes = {}
    for g in regimes:
        Z = [z_t(t, temoin) for t, x in zip(TA, GA) if x == g]
        pentes[g] = round(pente_de(Z), 3) if len(Z) >= MIN_APPRIS else 1.0
    out['temoin_une_pente_par_regime'] = {
        'pentes': pentes,
        'gain_jugement_tous_les_matchs': PD.moyenne([EC.ll(z_t(t, temoin)) - EC.ll(pentes[g] * z_t(t, temoin))
                                                     for t, g in zip(TJ, GJ)]),
        'candidat_moins_pentes_jugement': PD.moyenne([EC.ll(pentes[g] * z_t(t, temoin)) - EC.ll(z_t(t, poids[g]))
                                                      for t, g in zip(TJ, GJ)])}
    # sens inverse : tout est réappris sur la période jugée, appliqué à l'apprentissage
    inv = None
    if len(TJ) >= MIN_APPRIS:
        temoin_j, poids_j, appris_j = _apprendre_tout(TJ, GJ, regimes, depart)
        EI = _ecarts(TA, GA, temoin_j, poids_j)
        inv = {'temoin_poids_uniques_reappris': _poids_doc(temoin_j),
               'poids_appris': {g: _poids_doc(poids_j[g]) for g in regimes}, 'appris': appris_j,
               'sens': LIRE_SENS[_sens(poids_j, extremes)],
               'gain_sur_l_apprentissage_matchs_concernes': PD.moyenne([d for _, c, d in EI if c]),
               'gain_sur_l_apprentissage_tous_les_matchs': PD.moyenne([d for _, _, d in EI])}
    out['sens_inverse'] = inv
    if gj['matchs'] < MIN_JUGES:
        out['verdict'] = 'aucune décision'
        out['raisons'] = [f"moins de {MIN_JUGES} matchs concernés jugés ({gj['matchs']})"]
        return out
    raisons = []
    if gj['gain'] < MARGE:
        raisons.append(f"gain jugé sous {fr(MARGE)} face au témoin")
    s = _sens(poids, extremes)
    if s in (0, None):
        raisons.append('part de la simulation inchangée entre les deux régimes')
    elif inv is None or inv['sens'] != LIRE_SENS[s]:
        raisons.append("la part de la simulation ne bouge pas dans le même sens sur la période jugée")
    if inv is None or inv['gain_sur_l_apprentissage_matchs_concernes'].get('gain', -1) <= 0:
        raisons.append('pas de gain en sens inverse')
    if not gj.get('erreur_type') or gj['gain'] <= MIN_ERREURS_TYPES * gj['erreur_type']:
        raisons.append('gain jugé à 2 erreurs types ou moins')
    out['verdict'] = 'non retenu' if raisons else 'retenu'
    out['raisons'] = raisons
    return out


# ------------------------------------------------------------------ table descriptive « qui a raison »
def _pct(v, n):
    return round(100.0 * v / n, 1) if n else None


def _et_pct(k, n):
    """Erreur type d'une proportion k / n, en points."""
    if not n:
        return None
    p = k / n
    return round(100.0 * math.sqrt(max(p * (1 - p), 0.0) / n), 1)


def qui_a_raison(L):
    """L : [(z Elo, z simulation, z « en place »)] vus du vainqueur. Par case : comptes et moyennes seulement.
    Même favori : % moyen donné au favori commun par l'Elo, la simulation et le mélange en place, et part des matchs
    qu'il gagne. Vainqueurs différents : part des matchs où l'Elo, la simulation et le mélange en place ont raison."""
    out = {}
    for nom in GROUPES:
        X = [x for x in L if groupe(x[0], x[1]) == nom]
        n = len(X)
        d = {'matchs': n}
        if n and nom == 'vainqueurs_differents':
            k = sum(1 for x in X if x[0] > 0)
            d.update({'elo_a_raison_pct': _pct(k, n), 'simulation_a_raison_pct': _pct(n - k, n),
                      'erreur_type_points': _et_pct(k, n),
                      'en_place_a_raison_pct': _pct(sum(1.0 if x[2] > 0 else 0.5 if x[2] == 0 else 0.0 for x in X), n),
                      'elo_confiance_moyenne_pct': _pct(sum(EC._sg(abs(x[0])) for x in X), n),
                      'simulation_confiance_moyenne_pct': _pct(sum(EC._sg(abs(x[1])) for x in X), n),
                      'elo_plus_sur_pct': _pct(sum(1 for x in X if plus_sur(x[0], x[1]) == ELO), n),
                      'le_plus_sur_a_raison_pct': _pct(sum(1 for x in X if (x[0] > 0) == (plus_sur(x[0], x[1]) == ELO)), n)})
        elif n:
            k = sum(1 for x in X if x[0] > 0)                        # le favori commun a gagné
            d.update({'elo_pct': _pct(sum(EC._sg(abs(x[0])) for x in X), n),
                      'simulation_pct': _pct(sum(EC._sg(abs(x[1])) for x in X), n),
                      'en_place_pct': _pct(sum(EC._sg(x[2] if x[0] > 0 else -x[2]) for x in X), n),
                      'favori_gagne_pct': _pct(k, n), 'erreur_type_points': _et_pct(k, n)})
        out[nom] = d
    return out


# ------------------------------------------------------------------ tout le jugement
def juger(rows, cfgs):
    """Circuit par circuit. rows : sortie de etude_pente_melange.rejeu ; cfgs : sortie de etude_pente_melange.en_place."""
    out, coupure = {}, COUPURE.isoformat()
    for c in CIRCUITS:
        cfg = cfgs[c]
        depart = (cfg['elo'], cfg['simulation'])
        R = [r for r in rows if r[0] == c]
        A, J = [r for r in R if r[1] >= coupure], [r for r in R if r[1] < coupure]
        TA, TJ = [termes(r, cfg) for r in A], [termes(r, cfg) for r in J]
        doc = {'matchs': len(R), 'matchs_apprentissage': len(A), 'matchs_jugement': len(J),
               'poids_en_place': {'elo': cfg['elo'], 'simulation': cfg['simulation'],
                                  'part_simulation': part_simulation(depart)}}
        for nom, _ in CANDIDATS:
            f = REGIME[nom]
            doc[nom] = juger_candidat(nom, TA, [f(r[2], r[3]) for r in A], TJ, [f(r[2], r[3]) for r in J], depart)
        # trois régimes moins deux régimes, sur tous les matchs jugés (> 0 : trois régimes font mieux)
        d2, d3 = doc['deux_regimes'], doc['trois_regimes']
        if 'gain_jugement_tous_les_matchs' in d2 and 'gain_jugement_tous_les_matchs' in d3:
            w2 = {g: (v['poids_appris']['elo'], v['poids_appris']['simulation']) for g, v in d2['regimes'].items()}
            w3 = {g: (v['poids_appris']['elo'], v['poids_appris']['simulation']) for g, v in d3['regimes'].items()}
            doc['trois_regimes_moins_deux_regimes_jugement'] = PD.moyenne(
                [EC.ll(z_t(t, w2[regime_2(r[2], r[3])])) - EC.ll(z_t(t, w3[regime_3(r[2], r[3])])) for t, r in zip(TJ, J)])
        doc['qui_a_raison'] = {'jugement': qui_a_raison([(r[2], r[3], PM.z_base(r, cfg)) for r in J]),
                               'apprentissage': qui_a_raison([(r[2], r[3], PM.z_base(r, cfg)) for r in A])}
        doc['elo_seul'] = PM.elo_en_chauffe(R)
        doc['retenus'] = [nom for nom, _ in CANDIDATS if doc[nom].get('verdict') == 'retenu']
        out[c] = doc
    return out


# ------------------------------------------------------------------ nos matchs publiés (confirmation seulement)
def direct(racine, jug):
    """Par circuit, sur nos matchs publiés terminés (sans abandon) : la même table « qui a raison » (version « stats »
    à la place de l'Elo, % affiché à la place du mélange en place) et le gain qu'y feraient les poids à deux régimes
    appris au rejeu face au témoin du rejeu, posés nus sur les deux % publiés. Confirmation seulement. Aucun nom."""
    try:
        with open(os.path.join(racine, DIRECT), encoding='utf-8') as f:
            M = json.load(f).get('matchs') or []
    except (OSError, ValueError):
        return {'lu': False}
    out = {'lu': True, 'circuits': {}}
    for c in CIRCUITS:
        L = []
        for m in M:
            reel, p, pr = m.get('reel') or {}, m.get('p_affiche'), m.get('premier') or {}
            pe, ps = (pr.get('stats') or {}).get('p_home'), (pr.get('simulation') or {}).get('p_home')
            if (m.get('circuit') != c or reel.get('gagnant') not in ('home', 'away') or reel.get('interrompu')
                    or p is None or pe is None or ps is None or not pr.get('combinaison')):
                continue
            s = 1.0 if reel['gagnant'] == 'home' else -1.0
            L.append((s * EC._lg(pe), s * EC._lg(ps), s * EC._lg(p)))
        d = {'matchs': len(L), 'qui_a_raison': qui_a_raison(L)}
        d2 = (jug.get(c) or {}).get('deux_regimes') or {}
        if L and d2.get('temoin_poids_uniques_reappris') and 'gain_jugement_tous_les_matchs' in d2:
            wt = (d2['temoin_poids_uniques_reappris']['elo'], d2['temoin_poids_uniques_reappris']['simulation'])
            w = {g: (v['poids_appris']['elo'], v['poids_appris']['simulation']) for g, v in d2['regimes'].items()}
            E = _ecarts([(0.0, x[0], x[1]) for x in L], [regime_2(x[0], x[1]) for x in L], wt, w)
            d['poids_du_rejeu_deux_regimes'] = {'gain_matchs_concernes': PD.moyenne([e for _, k, e in E if k]),
                                                'gain_tous_les_matchs': PD.moyenne([e for _, _, e in E])}
        out['circuits'][c] = d
    return out


# ------------------------------------------------------------------ sorties
def _pm(g):
    return f"{fr(g.get('gain'))} ± {fr(g.get('erreur_type'))}"


def phrase_candidat(nom, d):
    if 'gain_jugement_matchs_concernes' not in d:
        return f"{LIBELLE[nom]} : {d['verdict']} ({' ; '.join(d.get('raisons') or [])})"
    gj, ga, inv = d['gain_jugement_matchs_concernes'], d['gain_apprentissage_matchs_concernes'], d.get('sens_inverse') or {}
    gi = inv.get('gain_sur_l_apprentissage_matchs_concernes') or {}
    t = d['temoin_poids_uniques_reappris']
    poids = ' · '.join(f"{LIBELLE[g]} Elo {fr(v['poids_appris']['elo'])} / simulation {fr(v['poids_appris']['simulation'])}"
                       f" ({v['matchs_apprentissage']} matchs appris)" for g, v in d['regimes'].items())
    txt = (f"{LIBELLE[nom]} : témoin Elo {fr(t['elo'])} / simulation {fr(t['simulation'])} ; {poids} ; "
           f"{ga.get('matchs', 0)} matchs concernés appris, {gj.get('matchs', 0)} jugés, gain face au témoin {_pm(gj)} "
           f"(sens inverse : {gi.get('matchs', 0)} matchs concernés, gain {_pm(gi)}) — {d['verdict']}")
    if d.get('raisons'):
        txt += f" ({' ; '.join(d['raisons'])})"
    return txt


def phrase_table(q):
    a, s, v = (q['meme_favori_10_points_elo_plus_sur'], q['meme_favori_10_points_simulation_plus_sure'],
               q['vainqueurs_differents'])
    return (f"même favori et 10 points d'écart, Elo plus sûr ({a['matchs']} matchs) : Elo {fr(a.get('elo_pct'))} %, simulation "
            f"{fr(a.get('simulation_pct'))} %, en place {fr(a.get('en_place_pct'))} %, le favori gagne "
            f"{fr(a.get('favori_gagne_pct'))} % ± {fr(a.get('erreur_type_points'))} ; simulation plus sûre ({s['matchs']}) : "
            f"Elo {fr(s.get('elo_pct'))} %, simulation {fr(s.get('simulation_pct'))} %, en place {fr(s.get('en_place_pct'))} %, "
            f"le favori gagne {fr(s.get('favori_gagne_pct'))} % ± {fr(s.get('erreur_type_points'))} ; vainqueurs différents "
            f"({v['matchs']}) : l'Elo a raison {fr(v.get('elo_a_raison_pct'))} % ± {fr(v.get('erreur_type_points'))}")


def phrase_resultats(jug, en_direct=None):
    morceaux = []
    for c in CIRCUITS:
        d = jug[c]
        morceaux.append(f"{NOM_CIRCUIT[c]} ({d['matchs_apprentissage']} matchs appris, {d['matchs_jugement']} jugés ; poids en "
                        f"place Elo {fr(d['poids_en_place']['elo'])} / simulation {fr(d['poids_en_place']['simulation'])}) — "
                        f"qui a raison sur la période jugée : {phrase_table(d['qui_a_raison']['jugement'])} — "
                        + ' · '.join(phrase_candidat(nom, d[nom]) for nom, _ in CANDIDATS))
    retenus = [f"{NOM_CIRCUIT[c]} ({LIBELLE[n]})" for c in CIRCUITS for n in jug[c]['retenus']]
    fin = ('Retenu : ' + (', '.join(retenus) if retenus else 'aucun circuit') + ". Proposé à Lucas ; rien n'est changé par "
           'ce paquet.')
    conf = ''
    if en_direct and en_direct.get('lu'):
        bouts = []
        for c, x in en_direct['circuits'].items():
            g = (x.get('poids_du_rejeu_deux_regimes') or {}).get('gain_matchs_concernes') or {}
            bouts.append(f"{NOM_CIRCUIT[c]} {x.get('matchs', 0)} matchs" + (f", poids à deux régimes du rejeu : {_pm(g)} sur "
                                                                           f"{g.get('matchs', 0)} matchs concernés" if g.get('matchs') else ''))
        conf = ' Confirmation seulement, nos matchs publiés : ' + ' ; '.join(bouts) + '.'
    return ' RÉSULTAT : ' + ' ; '.join(morceaux) + '. ' + fin + conf


def entree_journal(doc, gabarit):
    return {'date': gabarit['date'], 'statut': gabarit['statut'], 'paquet': gabarit['paquet'],
            'quoi': gabarit['quoi_debut'] + phrase_resultats(doc['jugement'], doc.get('nos_matchs_publies'))
            + ' Le % de victoire ne change pas.',
            'garde_fou': gabarit['garde_fou']}


def _ligne_table(journal, titre, q):
    for nom in GROUPES:
        x = q[nom]
        if nom == 'vainqueurs_differents':
            journal(f"   {titre:13s} {nom:44s} {x['matchs']:5d} m. | Elo a raison {x.get('elo_a_raison_pct')} % ± "
                    f"{x.get('erreur_type_points')} | en place a raison {x.get('en_place_a_raison_pct')} % | le plus sûr a raison "
                    f"{x.get('le_plus_sur_a_raison_pct')} % | confiance Elo {x.get('elo_confiance_moyenne_pct')} · simulation "
                    f"{x.get('simulation_confiance_moyenne_pct')}")
        else:
            journal(f"   {titre:13s} {nom:44s} {x['matchs']:5d} m. | Elo {x.get('elo_pct')} · simulation {x.get('simulation_pct')} "
                    f"· en place {x.get('en_place_pct')} | le favori gagne {x.get('favori_gagne_pct')} % ± "
                    f"{x.get('erreur_type_points')}")


def afficher(jug, en_direct=None, journal=print):
    """Ce qui part dans le journal du run (public) : comptes et moyennes seulement."""
    for c in CIRCUITS:
        d = jug[c]
        journal(f"== {NOM_CIRCUIT[c]} — {d['matchs']} matchs ({d['matchs_apprentissage']} appris, {d['matchs_jugement']} jugés) "
                f"| poids en place {d['poids_en_place']}")
        for per in ('jugement', 'apprentissage'):
            _ligne_table(journal, per, d['qui_a_raison'][per])
        for nom, _ in CANDIDATS:
            x = d[nom]
            journal('   → ' + phrase_candidat(nom, x) + f" | {x.get('erreurs_types')} erreurs types | sens {x.get('sens')} ; sens "
                    f"inverse {(x.get('sens_inverse') or {}).get('sens')}")
            if 'gain_jugement_tous_les_matchs' in x:
                f_, p_ = x['face_aux_poids_en_place_jugement'], x['temoin_une_pente_par_regime']
                journal(f"     tous les matchs jugés : {_pm(x['gain_jugement_tous_les_matchs'])} | face aux poids en place : témoin "
                        f"{_pm(f_['temoin'])}, candidat {_pm(f_['candidat'])} | une pente par régime {p_['pentes']} : "
                        f"{_pm(p_['gain_jugement_tous_les_matchs'])} ; candidat moins pentes {_pm(p_['candidat_moins_pentes_jugement'])}")
                for g, v in x['regimes'].items():
                    journal(f"     {LIBELLE[g]:42s} {v['matchs_apprentissage']:5d} appris, {v['matchs_jugement']:5d} jugés dont "
                            f"{v.get('matchs_concernes_jugement')} concernés | poids {v.get('poids_appris')} | gain jugé "
                            f"{_pm(v.get('gain_jugement') or {})}")
                inv = x.get('sens_inverse') or {}
                journal(f"     sens inverse : témoin {inv.get('temoin_poids_uniques_reappris')} | poids {inv.get('poids_appris')}")
        t = d.get('trois_regimes_moins_deux_regimes_jugement')
        if t:
            journal(f"   trois régimes moins deux régimes, tous les matchs jugés : {_pm(t)}")
        e = d['elo_seul']
        journal('   Elo seul : ' + ' · '.join(f"{k} {v.get('pente_elo_seul')} ± {v.get('erreur_type')} ({v['matchs']} m.)"
                                              for k, v in e.items() if isinstance(v, dict))
                + f" | écart {e.get('ecart_en_erreurs_types')} erreurs types, en chauffe : {e.get('en_chauffe')}")
        journal(f"   retenus : {d['retenus'] or 'aucun'}")
    if en_direct and en_direct.get('lu'):
        for c, x in en_direct['circuits'].items():
            journal(f"nos matchs publiés {NOM_CIRCUIT[c]} : {x.get('matchs', 0)} m.")
            _ligne_table(journal, 'publiés', x['qui_a_raison'])
            p = x.get('poids_du_rejeu_deux_regimes')
            if p:
                journal(f"   poids à deux régimes du rejeu face au témoin du rejeu : {_pm(p['gain_matchs_concernes'])} sur "
                        f"{p['gain_matchs_concernes'].get('matchs', 0)} matchs concernés ; tous les matchs {_pm(p['gain_tous_les_matchs'])}")


def main(argv):
    if len(argv) > 2 and argv[1] == '--journal-depuis-rapport':
        with open(argv[2], encoding='utf-8') as f:
            EC.ajouter_au_journal(JOURNAL, json.load(f)['entree_journal'])
        print('journal : entrée du paquet', PAQUET, 'ajoutée')
        return 0
    args = [a for a in argv[1:] if not a.startswith('--')]
    opt = {a.split('=')[0]: a.split('=', 1)[1] for a in argv[1:] if a.startswith('--') and '=' in a}
    archive, racine = args[0], (args[1] if len(args) > 1 else '.')
    cache = opt.get('--lignes')
    if cache and os.path.exists(cache):
        with gzip.open(cache, 'rt', encoding='utf-8') as f:
            sauve = json.load(f)
        rows, n_itf, n_adj = sauve['rows'], sauve['n_itf'], sauve['n_adj']
    else:
        rows, n_itf, n_adj = PM.rejeu(archive, racine)
        if cache:
            with gzip.open(cache, 'wt', encoding='utf-8') as f:
                json.dump({'rows': rows, 'n_itf': n_itf, 'n_adj': n_adj}, f)
    if not n_itf:
        raise SystemExit("::error::aucun résultat ITF hommes lu : le rejeu ne serait pas « comme en production »")
    cfgs = PM.en_place(racine)
    jug = juger(rows, cfgs)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': PAQUET,
           'regle': REGLE, 'apprentissage': [COUPURE.isoformat(), FIN.isoformat()],
           'jugement_une_seule_fois': [DEBUT.isoformat(), COUPURE.isoformat()], 'periode_jugee': PERIODE_JUGEE,
           'itf_hommes_dans_le_rejeu': n_itf, 'profils_refaits': n_adj, 'en_place': cfgs,
           'correction_non_rejouee': PM.NON_REJOUE, 'jugement': jug, 'nos_matchs_publies': direct(racine, jug),
           'limites': LIMITES, 'en_production': False}
    with open(GABARIT_JOURNAL, encoding='utf-8') as f:
        doc['entree_journal'] = entree_journal(doc, json.load(f))
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    EC.ajouter_au_journal(JOURNAL, doc['entree_journal'])
    afficher(jug, doc['nos_matchs_publies'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
