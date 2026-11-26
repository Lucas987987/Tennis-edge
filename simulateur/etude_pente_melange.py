#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_pente_melange.py — FAUT-IL ÉTIRER (OU RESSERRER) LE % FINAL PAR UNE PENTE PROPRE À CHAQUE CIRCUIT ET À CHAQUE
TRANCHE DE DOCUMENTATION ? (26/11/2026, paquet 465, Lucas : « On peut adapter les règles en fonction du nombre de
points et du circuit ».)

POURQUOI CETTE PISTE. L'étude 462 (etude_peu_documentes.py) n'a pas retenu un poids de la simulation par
documentation. Mais sur sa période jugée (10/2025 → 05/2026), une simple pente sur le mélange gagnait dans toutes les
tranches du Challenger (1,14 sous 500 points, 1,06 de 500 à 1 500, 1,12 de 1 500 à 3 000, 1,02 au-delà), et l'analyse
448 relancée avec les résultats ITF hommes donne un Elo seul un peu timide en Challenger (pente 1,078). Ces chiffres
ont DÉJÀ ÉTÉ VUS : ils ne peuvent pas servir de jugement. Il faut une période que cette question n'a jamais regardée.

CANDIDAT. Le % final devient σ(a · logit p), p étant le % « comme en place », avec une pente a par CIRCUIT (ATP, WTA,
Challenger) × TRANCHE de documentation du joueur le moins vu au jour du match (moins de 500 points de service,
500 à 1 500, 1 500 à 3 000, 3 000 et plus). a > 1 écarte le % de 50 %, a < 1 l'en rapproche.

REJEU, COMME EN PRODUCTION (aucune donnée postérieure au match ; celui de etude_peu_documentes.rejeu, réutilisé tel
quel, seules ses dates sont élargies) : Elo de production (archive depuis 2012 + résultats ITF hommes du dépôt, départs
par niveau), simulation de base rejouée avec des profils refaits au plus tard tous les 7 jours sur les seuls tournois
terminés avant le match, documentation comptée au jour du match. Un seul passage du 01/06/2024 au 31/05/2026 : l'Elo
et les profils de chaque match ne connaissent que ce qui le précède, quelle que soit la période où il est rangé.

BASE « COMME EN PLACE » (ce que la pente candidate vient corriger EN PLUS, pour ne rien compter deux fois) :
  - poids du mélange de la production (choix_simulation.json, poids_circuit.json) ;
  - Challenger, « documentation faible » : pente lue dans rapport_documentation.json (1,11) sous 500 points ;
  - Challenger, « favori le moins documenté » (favori_moins_documente.json, 500 à 1 500 points) ;
  - Challenger sur terre battue : pente lue dans corrections_chercheur.json (1,065), appliquée en dernier ;
  - NON REJOUÉE : la correction Challenger « correct » × 1,142 (correction_niveaux.json). Elle dépend du niveau de
    fiabilité du match, calculé à partir de nos pronostics publiés (réussite récente du circuit, notes des joueurs,
    stabilité entre passages) : il n'existe pas avant octobre 2026 et ne peut pas être reconstitué sur 2024–2026. Les
    matchs qu'elle toucherait (Challenger de niveau « correct », toutes tranches) sont donc jugés ici SANS elle ; leur
    part parmi nos matchs publiés est comptée dans le rapport. Conséquence écrite avant tout résultat : une pente
    Challenger retenue ici ne doit pas être multipliée par 1,142 sur le même match (voir « report en production »).
  Publié à côté, sans décider : la pente du mélange NU (sans aucun de ces signaux) dans chaque case, pour savoir ce
  que la nouvelle pente remplacerait.

PÉRIODES. Les résultats ITF hommes du dépôt commencent en juin 2024 (resultats_itf/2024-06) : avant, l'Elo du
Challenger est faussé (paquets 229, 230, 317–319, 448) et aucun rejeu « comme en production » n'est possible.
  apprentissage : 01/01/2025 → 31/05/2026 (période DÉJÀ VUE par les études 230, 320, 448, 452 et 462) ;
  jugement, UNE SEULE FOIS : 01/06/2024 → 31/12/2024, la seule période rejouable que ces études n'ont pas utilisée.
Ce que la période jugée n'est PAS, écrit avant tout résultat :
  - en Challenger, l'Elo n'y a que 0 à 7 mois de résultats ITF (7 à 24 mois sur l'apprentissage, plus de deux ans
    en production) : il est « en chauffe ». Contrôle publié : pente de l'Elo seul sur la période jugée (et ses deux moitiés, 06–08 et 09–12/2024)
    contre celle de l'apprentissage ; au-delà de 2 erreurs types d'écart, le Challenger est marqué « Elo en chauffe »
    et un verdict Challenger, quel qu'il soit, est à confirmer sur nos matchs publiés avant toute mise en service ;
  - en ATP et en WTA, les poids du mélange en place ont été appris sur des matchs de 2024 → janvier 2026
    (backtest_match_simule.py ; poids propres à l'ATP : 2024) : la base y est déjà ajustée sur les deux périodes, ce
    qui joue contre le candidat (une pente y a peu à gagner). Le chercheur (320) et l'analyse 448 ont aussi publié
    des pentes de l'Elo SEUL en ATP et en WTA sur 2023 → 2026, fenêtre qui contient ces sept mois. La période est
    donc neuve pour la question posée (aucune pente du MÉLANGE, ni aucune tranche de points de service, n'y a été
    mesurée), pas vierge de tout.
Matchs : ATP, WTA, Challenger, sans abandon ni compétition par équipes. ITF : données seulement, jamais pronostiqué.

RÈGLE ÉCRITE LE 26/11/2026, AVANT TOUT RÉSULTAT (case par case : circuit × tranche) :
  pente apprise sur l'apprentissage par maximum de vraisemblance (au moins 300 matchs dans la case, bornée entre 0,5
  et 2), appliquée telle quelle à la période jugée. Mesure : gain de log loss par match de la case (base − candidat),
  avec son erreur type.
  Une case est RETENUE si, à la fois :
    1. au moins 1 000 matchs de la case jugés (« on ne juge rien sur 100 matchs ») ;
    2. gain jugé ≥ 0,001 par match ;
    3. même sens sur les deux périodes, vérifié en sens inverse : la pente apprise sur la période jugée est du même
       côté de 1 que celle de l'apprentissage (à moins de 0,005 de 1 : « inchangé », non retenu), et, appliquée à
       l'apprentissage, elle y gagne aussi (gain > 0) ;
    4. gain jugé de plus de 2 erreurs types.
  Sous 1 000 matchs jugés : chiffres publiés, AUCUNE décision.
  VARIANTE publiée pour comparaison, même règle : UNE SEULE PENTE PAR CIRCUIT (toutes tranches ensemble), et, sur la
  période jugée, l'écart entre « une pente par tranche » et « une seule pente » (> 0 : les tranches font mieux).
  Confirmation seulement, sans décider : nos matchs publiés depuis la mise en ligne
  (Tennis_Edge_Lab/live/pronostics_resultats.json), qui portent déjà toutes les corrections en place.
  Rien n'entre en production par ce paquet : le verdict est proposé à Lucas.

REPORT EN PRODUCTION (écrit avant tout résultat). Le rejeu n'a que la simulation de base : sans les couches du lundi
(facteurs, modèle d'arbres, profils hiérarchiques) ni les autres signaux (zone d'hésitation, outsiders, Grand Chelem,
âge, surface…). Le % publié n'est donc pas celui du rejeu, et une pente apprise ici n'est qu'un point de départ : elle
ne peut entrer en service qu'avec les deux % gardés dans la fiche (avec / sans) et une règle de retrait cumulée.

Rapport public : simulateur/rapport_pente_melange.json — comptes et moyennes seulement, aucun nom de joueur.
Usage : python simulateur/etude_pente_melange.py /tmp/sackmann . [--lignes=/tmp/lignes.json.gz]
        python simulateur/etude_pente_melange.py --journal-depuis-rapport simulateur/rapport_pente_melange.json
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
import etude_peu_documentes as PD  # noqa: E402  (rejeu, base « comme en place », mesures : réutilisés sans les changer)

PAQUET = 465
DEBUT, COUPURE, FIN = dt.date(2024, 6, 1), dt.date(2025, 1, 1), dt.date(2026, 6, 1)
MI_JUGEMENT = dt.date(2024, 9, 1)
CIRCUITS = ('ATP', 'WTA', 'CH')
NOM_CIRCUIT = PD.NOM_CIRCUIT
TRANCHES = PD.TRANCHES
LIBELLE = PD.LIBELLE
MIN_APPRIS, MIN_JUGES, MARGE, MIN_ERREURS_TYPES = 300, 1000, 0.001, 2.0
PENTE_MIN, PENTE_MAX, INCHANGE = 0.5, 2.0, 0.005
SORTIE = os.path.join(ICI, 'rapport_pente_melange.json')
JOURNAL = os.path.join(ICI, 'journal_changements.json')
GABARIT_JOURNAL = os.path.join(ICI, 'journal_ajouts', 'paquet_465.json')
DIRECT = os.path.join('Tennis_Edge_Lab', 'live', 'pronostics_resultats.json')
REGLE = ("case par case (circuit × tranche de documentation du joueur le moins vu : moins de 500, 500 à 1 500, 1 500 à "
         "3 000, 3 000 points et plus) : pente du % final apprise sur le 01/01/2025 → 31/05/2026 (au moins 300 matchs), "
         "jugée une seule fois sur le 01/06/2024 → 31/12/2024 ; retenue si au moins 1 000 matchs de la case jugés, gain "
         "de log loss ≥ 0,001 par match, même sens sur les deux périodes (pente apprise sur la période jugée du même "
         "côté de 1 et gagnant aussi sur l'apprentissage) et gain de plus de 2 erreurs types ; sous 1 000 matchs jugés, "
         "aucune décision ; variante « une seule pente par circuit » publiée pour comparaison, même règle")
PERIODE_NEUVE = ("les résultats ITF hommes du dépôt commencent en juin 2024 : le rejeu comme en production ne peut pas "
                 "remonter plus haut ; juin → décembre 2024 est la seule période rejouable que les études 230, 320, 448, "
                 "452 et 462 n'ont pas utilisée. Réserves écrites avant tout résultat : en Challenger l'Elo n'y a que 0 "
                 "à 7 mois de résultats ITF (contrôle « Elo en chauffe » publié) ; en ATP et en WTA les poids du mélange "
                 "en place ont été appris sur des matchs de 2024 → janvier 2026, ce qui joue contre le candidat, et des "
                 "pentes de l'Elo seul y ont déjà été publiées sur 2023 → 2026 (320, 448) : période neuve pour le "
                 "mélange et pour les tranches de points, pas vierge de tout")
NON_REJOUE = ("correction Challenger « correct » × 1,142 (correction_niveaux.json) : non rejouée, car le niveau de "
              "fiabilité du match vient de nos pronostics publiés et n'existe pas avant octobre 2026 ; les matchs "
              "qu'elle toucherait (Challenger de niveau « correct », toutes tranches) sont jugés ici sans elle")
LIMITES = ("simulation de base (profils ajustés aux adversaires, refaits tous les 7 jours), sans les couches du lundi "
           "(facteurs, modèle d'arbres, profils hiérarchiques) ni les autres signaux ; la correction Challenger "
           "« correct » n'est pas rejouée ; documentation comptée sur l'archive, à la date de début du tournoi ; en "
           "Challenger, l'Elo de la période jugée n'a que 0 à 7 mois de résultats ITF")


# ------------------------------------------------------------------ rejeu (celui de l'étude 462, dates élargies)
def surfaces_des_lignes(M, rows, debut=DEBUT, fin=FIN):
    """Surface de chaque ligne du rejeu : M relu avec le filtre de etude_peu_documentes.rejeu, dans le même ordre.
    S'arrête si les deux listes ne se correspondent pas (le rejeu réutilisé aurait changé)."""
    import elo as E
    S = []
    for m in M:
        g, p = E.cle(m.get('nom_g')), E.cle(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        if m['circuit'] in PD.CIRCUITS and debut <= m['date'] < fin and not m.get('abandon') and m.get('niveau') != 'D':
            S.append((m['circuit'], m['date'].isoformat(), m.get('surface')))
    if len(S) != len(rows) or any(s[0] != r[0] or s[1] != r[1] for s, r in zip(S, rows)):
        raise SystemExit("::error::les surfaces ne s'alignent pas sur les lignes du rejeu (etude_peu_documentes.rejeu a "
                         "changé de filtre ?)")
    return [s[2] for s in S]


def rejeu(archive, racine, journal=print):
    """Lignes de etude_peu_documentes.rejeu sur DEBUT → FIN, plus la surface :
    [[circuit, jour, z Elo du vainqueur, z simulation du vainqueur, points du vainqueur, points du perdant, surface]].
    Le module 462 n'est pas modifié : ses dates et son chargement sont remplacés le temps de l'appel, puis remis."""
    capture = {}
    charger_462 = PD.charger

    def charger(a, r):
        out = charger_462(a, r)
        capture['M'] = out[0]
        return out

    anciens = (PD.DEBUT, PD.FIN, PD.charger)
    PD.DEBUT, PD.FIN, PD.charger = DEBUT, FIN, charger
    try:
        rows, n_itf, n_adj = PD.rejeu(archive, racine, journal)      # s'arrête de lui-même si aucun résultat ITF n'est lu
    finally:
        PD.DEBUT, PD.FIN, PD.charger = anciens
    S = surfaces_des_lignes(capture['M'], rows, DEBUT, FIN)
    return [list(r) + [s] for r, s in zip(rows, S)], n_itf, n_adj


# ------------------------------------------------------------------ ce qui est en place
def en_place(racine):
    """PD.en_place (poids, documentation faible, favori le moins documenté) plus les pentes par surface du chercheur
    (corrections_chercheur.json) : {circuit: {..., 'surfaces': {surface: pente}}}."""
    cfgs = PD.en_place(racine)
    try:
        import corrections_chercheur as CC
        corr = CC.actives(racine)
    except Exception:  # noqa: BLE001 — fichier absent ou illisible : aucune correction par surface
        corr = []
    for c in CIRCUITS:
        cfgs[c]['surfaces'] = {v['surface']: v['pente'] for v in corr if v['circuit'] == c}
    return cfgs


def sans_signaux(cfg):
    """Le mélange nu : mêmes poids, aucun signal."""
    return dict(cfg, pente_doc=None, fmd=None, surfaces={})


def z_base(r, cfg):
    """Logit du % « comme en place » donné au vainqueur : mélange et signaux de documentation (PD.z_melange), puis la
    pente de surface du chercheur, appliquée en dernier comme en production."""
    z = PD.z_melange(r, cfg)
    k = (cfg.get('surfaces') or {}).get(r[6] if len(r) > 6 else None)
    return z * k if k else z


# ------------------------------------------------------------------ mesures
def pente_de(Z):
    """(pente, erreur type) du maximum de vraisemblance, pente bornée entre PENTE_MIN et PENTE_MAX."""
    a, et = EC.pente(Z)
    return round(min(max(a, PENTE_MIN), PENTE_MAX), 3), (round(et, 3) if et is not None else None)


def gain(Z, a):
    """Base moins candidat, par match : gain de log loss de la pente a sur les logits Z."""
    return PD.moyenne([EC.ll(z) - EC.ll(a * z) for z in Z])


def cote(a):
    return 0 if abs(a - 1.0) < INCHANGE else (1 if a > 1.0 else -1)


def decrire(Z):
    n = len(Z)
    if not n:
        return {'matchs': 0}
    out = {'matchs': n,
           'favori_annonce_pct': round(100 * sum(max(EC._sg(z), 1 - EC._sg(z)) for z in Z) / n, 1),
           'favori_reel_pct': round(100 * sum(1.0 if z > 0 else 0.5 if z == 0 else 0.0 for z in Z) / n, 1),
           'log_loss': round(sum(EC.ll(z) for z in Z) / n, 5)}
    if n >= 30:
        out['pente'], out['pente_erreur_type'] = pente_de(Z)
    return out


def juger_case(ZA, ZJ, ZA_nu=None):
    """Une case (ou un circuit entier) : ZA = logits « comme en place » de l'apprentissage, ZJ = de la période jugée."""
    out = {'apprentissage': decrire(ZA), 'jugement': decrire(ZJ)}
    if ZA_nu and len(ZA_nu) >= 30:
        out['pente_du_melange_nu_apprentissage'] = pente_de(ZA_nu)[0]
    if len(ZA) < MIN_APPRIS or not ZJ:
        out['verdict'] = 'aucune décision'
        out['raisons'] = [f"moins de {MIN_APPRIS} matchs pour apprendre" if len(ZA) < MIN_APPRIS else 'aucun match jugé']
        return out
    a = out['apprentissage']['pente']
    out['pente_apprise'] = a
    out['sens'] = {1: 'étirer', -1: 'resserrer', 0: 'inchangé'}[cote(a)]
    out['gain_apprentissage'] = gain(ZA, a)
    gj = out['gain_jugement'] = gain(ZJ, a)
    out['erreurs_types'] = round(gj['gain'] / gj['erreur_type'], 2) if gj.get('erreur_type') else None
    a_j = pente_de(ZJ)[0] if len(ZJ) >= MIN_APPRIS else None
    out['sens_inverse'] = ({'pente_apprise_sur_la_periode_jugee': a_j, 'gain_sur_l_apprentissage': gain(ZA, a_j)}
                           if a_j is not None else None)
    if gj['matchs'] < MIN_JUGES:
        out['verdict'] = 'aucune décision'
        out['raisons'] = [f"moins de {MIN_JUGES} matchs jugés ({gj['matchs']})"]
        return out
    raisons = []
    if gj['gain'] < MARGE:
        raisons.append(f"gain jugé sous {PD.fr(MARGE)}")
    if cote(a) == 0:
        raisons.append('pente apprise à moins de 0,005 de 1')
    elif a_j is None or cote(a_j) != cote(a):
        raisons.append("la pente apprise sur la période jugée n'est pas du même côté de 1")
    if a_j is None or out['sens_inverse']['gain_sur_l_apprentissage'].get('gain', -1) <= 0:
        raisons.append('pas de gain en sens inverse')
    if not gj.get('erreur_type') or gj['gain'] <= MIN_ERREURS_TYPES * gj['erreur_type']:
        raisons.append('gain jugé à 2 erreurs types ou moins')
    out['verdict'] = 'non retenu' if raisons else 'retenu'
    out['raisons'] = raisons
    return out


def elo_en_chauffe(R):
    """Contrôle écrit dans la règle : pente de l'Elo SEUL sur la période jugée (et ses deux moitiés) contre celle de
    l'apprentissage ; « en chauffe » si l'écart dépasse 2 erreurs types."""
    coupure, mi = COUPURE.isoformat(), MI_JUGEMENT.isoformat()
    parts = {'apprentissage': [r[2] for r in R if r[1] >= coupure], 'jugement': [r[2] for r in R if r[1] < coupure],
             'jugement_06_08_2024': [r[2] for r in R if r[1] < mi],
             'jugement_09_12_2024': [r[2] for r in R if mi <= r[1] < coupure]}
    out = {}
    for nom, Z in parts.items():
        out[nom] = {'matchs': len(Z)}
        if len(Z) >= 30:
            out[nom]['pente_elo_seul'], out[nom]['erreur_type'] = pente_de(Z)
    a, j = out['apprentissage'], out['jugement']
    if a.get('erreur_type') and j.get('erreur_type'):
        e = (j['pente_elo_seul'] - a['pente_elo_seul']) / math.sqrt(a['erreur_type'] ** 2 + j['erreur_type'] ** 2)
        out['ecart_en_erreurs_types'] = round(e, 2)
        out['en_chauffe'] = bool(abs(e) > 2.0)
    else:
        out['ecart_en_erreurs_types'], out['en_chauffe'] = None, None
    return out


def juger(rows, cfgs):
    """Tout le jugement, circuit par circuit. rows : sortie de rejeu ; cfgs : sortie de en_place."""
    out, coupure = {}, COUPURE.isoformat()
    for c in CIRCUITS:
        cfg, nu = cfgs[c], sans_signaux(cfgs[c])
        R = [r for r in rows if r[0] == c]
        L = [(r[1] >= coupure, PD.tranche_de(r), z_base(r, cfg), z_base(r, nu)) for r in R]      # (appris ?, tranche, z, z nu)
        doc = {'matchs': len(R), 'matchs_apprentissage': sum(x[0] for x in L),
               'matchs_jugement': sum(not x[0] for x in L), 'tranches': {}}
        for nom, _, _ in TRANCHES:
            doc['tranches'][nom] = juger_case([x[2] for x in L if x[0] and x[1] == nom],
                                              [x[2] for x in L if not x[0] and x[1] == nom],
                                              [x[3] for x in L if x[0] and x[1] == nom])
        u = doc['une_seule_pente'] = juger_case([x[2] for x in L if x[0]], [x[2] for x in L if not x[0]],
                                                [x[3] for x in L if x[0]])
        # une pente par tranche contre une seule pente, sur la période jugée (> 0 : les tranches font mieux)
        a_u = u.get('pente_apprise', 1.0)
        a_t = {nom: doc['tranches'][nom].get('pente_apprise', a_u) for nom, _, _ in TRANCHES}
        J = [x for x in L if not x[0]]
        doc['toutes_les_tranches_jugement'] = PD.moyenne([EC.ll(x[2]) - EC.ll(a_t[x[1]] * x[2]) for x in J])
        doc['tranches_moins_une_seule_pente_jugement'] = PD.moyenne([EC.ll(a_u * x[2]) - EC.ll(a_t[x[1]] * x[2]) for x in J])
        doc['elo_seul'] = elo_en_chauffe(R)
        doc['cases_retenues'] = [n for n, _, _ in TRANCHES if doc['tranches'][n].get('verdict') == 'retenu']
        out[c] = doc
    return out


# ------------------------------------------------------------------ nos matchs publiés (confirmation seulement)
def direct(racine, jug):
    """Par circuit, sur nos matchs publiés terminés (sans abandon) : pente du % publié, gain qu'y ferait la pente
    unique du circuit apprise au rejeu, et part des matchs déjà corrigés par niveau ou par surface. Confirmation
    seulement : ces % portent déjà toutes les corrections en place. Comptes et moyennes, aucun nom."""
    try:
        with open(os.path.join(racine, DIRECT), encoding='utf-8') as f:
            M = json.load(f).get('matchs') or []
    except (OSError, ValueError):
        return {'lu': False}
    out = {'lu': True, 'circuits': {}}
    for c in CIRCUITS:
        Z, sources = [], {}
        for m in M:
            reel, p = m.get('reel') or {}, m.get('p_affiche')
            if (m.get('circuit') != c or reel.get('gagnant') not in ('home', 'away') or reel.get('interrompu')
                    or p is None or not (m.get('premier') or {}).get('combinaison')):
                continue
            Z.append(EC._lg(p if reel['gagnant'] == 'home' else 1 - float(p)))
            s = ((m.get('fiabilite') or {}).get('correction_niveau') or {}).get('source')
            if s:
                s = os.path.basename(s)
                sources[s] = sources.get(s, 0) + 1
        d = decrire(Z)
        d['deja_corriges_par'] = sources
        a = ((jug.get(c) or {}).get('une_seule_pente') or {}).get('pente_apprise')
        if a is not None and Z:
            d['pente_unique_du_rejeu'] = a
            d['gain_de_la_pente_unique_du_rejeu'] = gain(Z, a)
        out['circuits'][c] = d
    return out


# ------------------------------------------------------------------ sorties
fr = PD.fr


def phrase_case(titre, t):
    j = t['jugement'].get('matchs', 0)
    if 'pente_apprise' not in t:
        return (f"{titre} : {t['apprentissage'].get('matchs', 0)} matchs appris, {j} jugés — {t['verdict']} "
                f"({' ; '.join(t.get('raisons') or [])})")
    gj, inv = t['gain_jugement'], t.get('sens_inverse') or {}
    gi = inv.get('gain_sur_l_apprentissage') or {}
    txt = (f"{titre} : pente {fr(t['pente_apprise'])} apprise sur {t['apprentissage']['matchs']} matchs, {j} jugés, gain "
           f"{fr(gj.get('gain'))} ± {fr(gj.get('erreur_type'))} (sens inverse : pente "
           f"{fr(inv.get('pente_apprise_sur_la_periode_jugee'))}, gain {fr(gi.get('gain'))} ± {fr(gi.get('erreur_type'))}) — "
           f"{t['verdict']}")
    if t.get('raisons'):
        txt += f" ({' ; '.join(t['raisons'])})"
    return txt


def phrase_resultats(jug, en_direct=None):
    morceaux = []
    for c in CIRCUITS:
        d = jug[c]
        e = d['elo_seul']
        chauffe = ''
        if c == 'CH':
            lecture = ('Elo en chauffe : verdicts Challenger à confirmer en direct' if e.get('en_chauffe')
                       else "pas d'écart au-delà de 2 erreurs types")
            chauffe = (f" ; Elo seul : pente {fr(e['jugement'].get('pente_elo_seul'))} sur la période jugée contre "
                       f"{fr(e['apprentissage'].get('pente_elo_seul'))} sur l'apprentissage ({lecture})")
        ec = d['tranches_moins_une_seule_pente_jugement']
        morceaux.append(f"{NOM_CIRCUIT[c]} ({d['matchs_apprentissage']} matchs appris, {d['matchs_jugement']} jugés) — "
                        + ' · '.join(phrase_case(LIBELLE[n], d['tranches'][n]) for n, _, _ in TRANCHES)
                        + ' · ' + phrase_case('une seule pente pour le circuit', d['une_seule_pente'])
                        + f" · une pente par tranche moins une seule pente, période jugée : {fr(ec.get('gain'))} ± "
                          f"{fr(ec.get('erreur_type'))}" + chauffe)
    retenues = [f"{NOM_CIRCUIT[c]} {LIBELLE[n]}" for c in CIRCUITS for n in jug[c]['cases_retenues']]
    uniques = [NOM_CIRCUIT[c] for c in CIRCUITS if jug[c]['une_seule_pente'].get('verdict') == 'retenu']
    fin = ('Cases retenues : ' + (', '.join(retenues) if retenues else 'aucune') + ' ; pente unique retenue : '
           + (', '.join(uniques) if uniques else 'aucun circuit') + '. Proposé à Lucas ; rien n\'est changé par ce paquet.')
    conf = ''
    if en_direct and en_direct.get('lu'):
        conf = ' Confirmation seulement, nos matchs publiés (ils portent déjà les corrections en place) : ' + ' ; '.join(
            f"{NOM_CIRCUIT[c]} {x.get('matchs', 0)} matchs, pente du % publié {fr(x.get('pente'))} ± {fr(x.get('pente_erreur_type'))}"
            for c, x in en_direct['circuits'].items()) + '.'
    return ' RÉSULTAT : ' + ' ; '.join(morceaux) + '. ' + fin + conf


def entree_journal(doc, gabarit):
    return {'date': gabarit['date'], 'statut': gabarit['statut'], 'paquet': gabarit['paquet'],
            'quoi': gabarit['quoi_debut'] + phrase_resultats(doc['jugement'], doc.get('nos_matchs_publies'))
            + ' Le % de victoire ne change pas.',
            'garde_fou': gabarit['garde_fou']}


def afficher(jug, en_direct=None, journal=print):
    """Ce qui part dans le journal du run (public) : comptes et moyennes seulement."""
    for c in CIRCUITS:
        d = jug[c]
        journal(f"== {NOM_CIRCUIT[c]} — {d['matchs']} matchs ({d['matchs_apprentissage']} appris, {d['matchs_jugement']} jugés)")
        for nom, t in [(LIBELLE[n], d['tranches'][n]) for n, _, _ in TRANCHES] + [('une seule pente', d['une_seule_pente'])]:
            for per in ('apprentissage', 'jugement'):
                x = t[per]
                journal(f"   {nom:22s} {per:13s} {x.get('matchs', 0):5d} m. | favori {x.get('favori_annonce_pct')} annoncé / "
                        f"{x.get('favori_reel_pct')} réel | pente {x.get('pente')} ± {x.get('pente_erreur_type')} | log loss "
                        f"{x.get('log_loss')}")
            journal('     → ' + phrase_case(nom, t) + f" | {t.get('erreurs_types')} erreurs types | mélange nu : pente "
                    f"{t.get('pente_du_melange_nu_apprentissage')}")
        e, ec, tt = d['elo_seul'], d['tranches_moins_une_seule_pente_jugement'], d['toutes_les_tranches_jugement']
        journal(f"   toutes les tranches, période jugée : gain {fr(tt.get('gain'))} ± {fr(tt.get('erreur_type'))} ; moins une "
                f"seule pente : {fr(ec.get('gain'))} ± {fr(ec.get('erreur_type'))} | retenues : {d['cases_retenues'] or 'aucune'}")
        journal('   Elo seul : ' + ' · '.join(f"{k} {v.get('pente_elo_seul')} ± {v.get('erreur_type')} ({v['matchs']} m.)"
                                              for k, v in e.items() if isinstance(v, dict))
                + f" | écart {e.get('ecart_en_erreurs_types')} erreurs types, en chauffe : {e.get('en_chauffe')}")
    if en_direct and en_direct.get('lu'):
        for c, x in en_direct['circuits'].items():
            g = x.get('gain_de_la_pente_unique_du_rejeu') or {}
            journal(f"nos matchs publiés {NOM_CIRCUIT[c]} : {x.get('matchs', 0)} m., pente du % publié {x.get('pente')} ± "
                    f"{x.get('pente_erreur_type')}, pente unique du rejeu {x.get('pente_unique_du_rejeu')} → gain "
                    f"{fr(g.get('gain'))} ± {fr(g.get('erreur_type'))}, déjà corrigés {x.get('deja_corriges_par')}")


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
        rows, n_itf, n_adj = rejeu(archive, racine)
        if cache:
            with gzip.open(cache, 'wt', encoding='utf-8') as f:
                json.dump({'rows': rows, 'n_itf': n_itf, 'n_adj': n_adj}, f)
    if not n_itf:
        raise SystemExit("::error::aucun résultat ITF hommes lu : le rejeu ne serait pas « comme en production »")
    cfgs = en_place(racine)
    jug = juger(rows, cfgs)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': PAQUET,
           'regle': REGLE, 'apprentissage': [COUPURE.isoformat(), FIN.isoformat()],
           'jugement_une_seule_fois': [DEBUT.isoformat(), COUPURE.isoformat()], 'periode_jugee': PERIODE_NEUVE,
           'itf_hommes_dans_le_rejeu': n_itf, 'profils_refaits': n_adj, 'en_place': cfgs,
           'correction_non_rejouee': NON_REJOUE, 'jugement': jug, 'nos_matchs_publies': direct(racine, jug),
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
