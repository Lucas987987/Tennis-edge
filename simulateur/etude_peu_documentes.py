#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_peu_documentes.py — JOUEURS PEU DOCUMENTÉS : LE POIDS DE LA SIMULATION DOIT-IL DÉPENDRE DE LA DOCUMENTATION ?
(26/11/2026, paquet 462, Lucas : « comment l'algo peut-il mieux traiter les joueurs peu documentés ? » ; priorité au
Challenger.)

POURQUOI CETTE PISTE. Le % de victoire est un mélange σ(a · logit Elo + b · logit simulation), avec les mêmes poids
(a, b) quelle que soit la documentation des joueurs. Or :
  - la simulation part des profils service / retour, appris sur les seuls matchs qui ont une feuille de statistiques ;
    les matchs ITF n'en ont presque jamais (sonde du 28/10 : 6 %) : pour un joueur peu documenté, le profil est
    presque la moyenne du circuit ;
  - l'Elo, lui, connaît désormais les résultats ITF hommes (28/10) et fait partir les joueurs ITF de 1000 (11/11) ;
  - le diagnostic du paquet 367 (tranche 500–1 500 points, nos matchs) attribue l'écart surtout à la simulation
    (−12,5 points) plus qu'à l'Elo (−4,3).
Les études déjà faites corrigent la PENTE du % (187, 368, 452, 453) ou la part de l'Elo (373, 374), jamais le POIDS de
la simulation selon la documentation. La seule étude du poids par groupe de joueurs (etude_poids_elo_simulation.py,
05/11) classait par nombre de MATCHS et non par points de service, sur quatre mois de 2026 et avec un Elo sans les
résultats ITF : elle ne répond pas à la question.

REJEU, COMME EN PRODUCTION (aucune cote, aucune donnée postérieure au match) :
  - Elo : etude_depart_itf.matchs (archive + résultats ITF hommes), elo.de_production, départs par niveau, mis à jour
    après chaque match (comme etude_documentation_itf.py) ;
  - simulation : profils ajustés aux adversaires (ajustement.ajuster_choisi, réglages de choix_simulation.json), refaits
    au plus tard tous les 7 jours avec les seuls tournois terminés avant la date du match, puis
    match_simule.victoire_pure (forme du jour retenue en production) ;
  - documentation : points de service cumulés au jour du match (etude_documentation.Compteur), celle du joueur le
    moins vu ; tranches : moins de 500 · 500 à 1 500 · 1 500 à 3 000 · 3 000 et plus ;
  - base « comme en place » : poids du mélange de la production (choix_simulation.json, poids_circuit.json), puis les
    deux signaux de documentation en service en Challenger : « documentation faible » (pente lue dans
    rapport_documentation.json, sous 500 points) et « favori le moins documenté » (favori_moins_documente.json).
  Le rejeu s'arrête si aucun résultat ITF hommes n'est lu (dépôt incomplet).
  Matchs : ATP, WTA, Challenger du 01/01/2025 au 31/05/2026, sans abandon ni compétition par équipes. Avant juin 2024
  l'archive n'a pas les résultats ITF hommes : l'Elo du Challenger y serait faussé, d'où ces dates. ITF : données
  seulement, jamais pronostiqué.

RÈGLE ÉCRITE LE 26/11/2026, AVANT TOUT RÉSULTAT (circuit par circuit, tranche par tranche ; « matchs concernés » = les
deux tranches sous 1 500 points) :
  apprentissage 01/01/2025 → 30/09/2025 ; jugement UNE SEULE FOIS 01/10/2025 → 31/05/2026.
  Candidat « poids de la simulation » : dans la tranche, b est remplacé par b_t (a inchangé, signaux en place
  inchangés), b_t choisi sur l'apprentissage dans la grille 0 · 0,02 · … · 1 (plus petite log loss ; à égalité, le
  plus proche du poids en place). Il faut au moins 300 matchs de la tranche pour apprendre.
  Mesure : gain de log loss par match de la tranche (base − candidat), avec son erreur type.
  Une tranche est RETENUE sur un circuit si, à la fois :
    1. au moins 1 000 matchs de la tranche jugés (« on ne juge rien sur 100 matchs ») ;
    2. gain jugé ≥ 0,001 par match ;
    3. même sens sur les deux périodes, vérifié en sens inverse : le poids appris sur la période jugée est du même
       côté du poids en place que celui de l'apprentissage, et, appliqué à la période d'apprentissage, il y gagne
       aussi (gain > 0) ;
    4. c'est bien le poids qui compte : sur la période jugée, le candidat fait mieux qu'une simple pente apprise de la
       même façon sur tout le mélange (grille 0,5 · 0,52 · … · 2), écart > 0.
  Sous 1 000 matchs jugés : chiffres publiés, AUCUNE décision.
  Publié à côté du verdict, sans le changer : le gain jugé dépasse-t-il 2 erreurs types ? Sur des données factices
  sans aucun effet, la règle ci-dessus retient parfois une tranche par hasard (tests) : une tranche retenue sous
  2 erreurs types est à confirmer avant toute mise en service.
  Publiés sans décider : les quatre tranches (les deux tranches bien documentées servent de témoin), l'ensemble des
  matchs concernés, la « simple pente », les deux poids appris ensemble (a_t, b_t), et, par tranche et par période,
  la pente et la log loss de l'Elo seul, de la simulation seule et du mélange en place.
  Rien n'entre en production par ce paquet : le verdict est proposé à Lucas.
Limites : simulation de base (profils ajustés), sans les couches du lundi (facteurs, modèle d'arbres, profils
hiérarchiques candidats) ni les autres signaux ; profils refaits tous les 7 jours et non à chaque passage.

Rapport public : simulateur/rapport_peu_documentes.json — comptes et moyennes seulement, aucun nom de joueur.
Usage : python simulateur/etude_peu_documentes.py /tmp/sackmann . [--lignes=/tmp/lignes.json.gz]
        python simulateur/etude_peu_documentes.py --journal-depuis-rapport simulateur/rapport_peu_documentes.json
"""
import datetime as dt
import gzip
import json
import math
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_etalonnage_cases as EC  # noqa: E402

PAQUET = 462
DEBUT, COUPURE, FIN = dt.date(2025, 1, 1), dt.date(2025, 10, 1), dt.date(2026, 6, 1)
CIRCUITS = ('CH', 'ATP', 'WTA')
NOM_CIRCUIT = {'CH': 'Challenger', 'ATP': 'ATP', 'WTA': 'WTA'}
TRANCHES = (('moins_de_500', 0, 500), ('500_a_1500', 500, 1500), ('1500_a_3000', 1500, 3000), ('3000_et_plus', 3000, None))
LIBELLE = {'moins_de_500': 'moins de 500 points', '500_a_1500': '500 à 1 500 points',
           '1500_a_3000': '1 500 à 3 000 points', '3000_et_plus': '3 000 points et plus'}
CONCERNEES = ('moins_de_500', '500_a_1500')
SEUIL_DOC_FAIBLE = 500
MIN_APPRIS, MIN_JUGES, MARGE = 300, 1000, 0.001
GRILLE_POIDS = [round(0.02 * i, 2) for i in range(51)]
GRILLE_PENTE = [round(0.5 + 0.02 * i, 2) for i in range(76)]
JOURS_PROFILS = 7
POIDS_REPLI = {'elo': 0.7815, 'simulation': 0.2378}
SORTIE = os.path.join(ICI, 'rapport_peu_documentes.json')
JOURNAL = os.path.join(ICI, 'journal_changements.json')
GABARIT_JOURNAL = os.path.join(ICI, 'journal_ajouts', 'paquet_462.json')
REGLE = ("par circuit et par tranche de documentation (joueur le moins vu : moins de 500, 500 à 1 500 points) : poids de "
         "la simulation choisi sur le 01/01/2025 → 30/09/2025 (au moins 300 matchs), jugé une seule fois sur le "
         "01/10/2025 → 31/05/2026 ; retenu si au moins 1 000 matchs de la tranche jugés, gain de log loss ≥ 0,001 par "
         "match, même sens sur les deux périodes (poids appris sur la période jugée du même côté du poids en place et "
         "gagnant aussi sur l'apprentissage), et mieux qu'une simple pente sur la période jugée ; sous 1 000 matchs "
         "jugés, aucune décision")
LIMITES = ("simulation de base (profils ajustés aux adversaires, refaits tous les 7 jours), sans les couches du lundi "
           "(facteurs, modèle d'arbres, profils hiérarchiques candidats) ni les autres signaux ; documentation comptée "
           "sur l'archive, à la date de début du tournoi")


# ------------------------------------------------------------------ ce qui est en place
def _json(chemin):
    try:
        with open(chemin, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def en_place(racine):
    """{circuit: {elo, simulation, pente_doc, fmd}} : poids du mélange et signaux de documentation en service (mêmes
    fichiers et même ordre de priorité que pronostics_du_jour.py)."""
    sim = os.path.join(racine, 'simulateur')
    choix = _json(os.path.join(sim, 'choix_simulation.json'))
    communs = None
    for cle in ('combinaison_continue', 'combinaison_feuilles', 'combinaison'):
        c = choix.get(cle) or {}
        if c.get('adopte') and c.get('poids'):
            communs = {'elo': float(c['poids']['elo']), 'simulation': float(c['poids']['simulation'])}
            break
    communs = communs or dict(POIDS_REPLI)
    propres = (_json(os.path.join(sim, 'poids_circuit.json')).get('circuits') or {})
    docs = (_json(os.path.join(sim, 'rapport_documentation.json')).get('circuits') or {})
    fmd = (_json(os.path.join(sim, 'favori_moins_documente.json')).get('pentes') or {})
    out = {}
    for c in CIRCUITS:
        p = propres.get(c) or {}
        w = ({'elo': float(p['elo']), 'simulation': float(p['simulation'])}
             if isinstance(p, dict) and not p.get('retire') and p.get('elo') is not None and p.get('simulation') is not None
             else dict(communs))
        d = docs.get(c) or {}
        f = fmd.get(c) or {}
        out[c] = dict(w, pente_doc=float(d['pente']) if d.get('adopte') and d.get('pente') else None,
                      fmd=({'pente': float(f['pente']), 'de': f.get('de') or 0, 'a': f.get('a')} if f.get('pente') else None))
    return out


def reglages_simulation(racine):
    """(n0, n0 par composante, dynamique, forme du jour) : les réglages de choix_simulation.json, comme la production."""
    import ajustement as AJ
    choix = _json(os.path.join(racine, 'simulateur', 'choix_simulation.json'))
    rg = choix.get('reglage_simulation') or {}
    return (float(choix.get('n0') or AJ.N0), choix.get('n0_par_composante') or None, AJ.lire_dynamique(choix),
            float(rg['sigma']) if rg.get('adopte') and rg.get('sigma') is not None else 0.15)


# ------------------------------------------------------------------ rejeu (Elo et simulation, sans fuite)
def charger(archive, racine):
    """Tout ce que le rejeu lit : (matchs, nombre de résultats ITF hommes, Elo neuf, départ bas, compteur de points)."""
    import elo as E
    import etude_depart_itf as ED
    import etude_documentation as EDO
    M, n_itf = ED.matchs(archive, racine)
    el, bas = E.de_production(racine)
    return M, n_itf, el, bas, EDO.Compteur(EDO.evenements(archive, racine))


def rejeu(archive, racine, journal=print):
    """[[circuit, jour, z Elo du vainqueur, z simulation du vainqueur, points du vainqueur, points du perdant]]."""
    import ajustement as AJ
    import backtest_pronostic as BP
    import elo as E
    import match_simule as S
    t0 = time.time()
    M, n_itf, el, bas, cpt = charger(archive, racine)
    if not n_itf:
        # Sans scripts/resultats_itf.py ET scripts/feuilles_match.py (qu'il importe), backtest_pronostic.resultats_itf
        # rend une liste vide sans rien dire : l'Elo ne serait plus celui de la production.
        raise SystemExit("::error::aucun résultat ITF hommes lu (resultats_itf/, scripts/resultats_itf.py et "
                         "scripts/feuilles_match.py sont nécessaires) : le rejeu ne serait pas « comme en production »")
    n0, n0_comp, dyn, sigma = reglages_simulation(racine)
    debut_profils = DEBUT - dt.timedelta(days=int(365.25 * (AJ.ANNEES + 2)))
    avec_feuille = [m for m in M if m.get('detail') and m['date'] >= debut_profils]
    journal(f"matchs lus {len(M)} dont résultats ITF hommes {n_itf} ; avec feuille depuis {debut_profils} : {len(avec_feuille)}")
    adj, date_adj, n_adj, rows = None, None, 0, []
    for m in M:
        g, p = E.cle(m.get('nom_g')), E.cle(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m.get('surface')
        if bas and c in BP.BAS:
            el.presenter(g, E.depart_du_niveau(c, bas))
            el.presenter(p, E.depart_du_niveau(c, bas))
        if c in CIRCUITS and DEBUT <= m['date'] < FIN and not m.get('abandon') and m.get('niveau') != 'D':
            if adj is None or (m['date'] - date_adj).days >= JOURS_PROFILS:
                adj = AJ.ajuster_choisi(avec_feuille, m['date'], E.cle, n0=n0, dyn=dyn, depart=adj,
                                        tours=6 if adj is None else 2, n0_par_composante=n0_comp)
                date_adj, n_adj = m['date'], n_adj + 1
                if n_adj % 10 == 1:
                    journal(f"  profils refaits au {date_adj} (n° {n_adj}, {round(time.time() - t0)} s)")
            cg, cp = S.composantes_ajustees(adj, g, p, c, s), S.composantes_ajustees(adj, p, g, c, s)
            p_sim = S.victoire_pure(cg, cp, 3 if m.get('bo') == 5 else 2, sigma)
            n = cpt.au(m['date'].isoformat())
            rows.append([c, m['date'].isoformat(), round(EC._lg(el.proba(g, p, s)), 5), round(EC._lg(p_sim), 5),
                         int(n.get(g, 0)), int(n.get(p, 0))])
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    journal(f"rejeu terminé : {len(rows)} matchs, profils refaits {n_adj} fois ({round(time.time() - t0)} s)")
    return rows, n_itf, n_adj


# ------------------------------------------------------------------ mesures
def tranche_de(r):
    n = min(r[4], r[5])
    for nom, lo, hi in TRANCHES:
        if n >= lo and (hi is None or n < hi):
            return nom
    return TRANCHES[-1][0]


def z_melange(r, cfg, b=None, a=None, k=None):
    """Logit du % donné au vainqueur : mélange (poids en place, ou b / a / pente k essayés) puis les deux signaux de
    documentation en service, appliqués comme pronostics_du_jour.py (décalages en logit)."""
    ze, zs = r[2], r[3]
    z0 = (cfg['elo'] if a is None else a) * ze + (cfg['simulation'] if b is None else b) * zs
    if k is not None:
        z0 *= k
    z = z0
    if cfg.get('pente_doc') and min(r[4], r[5]) < SEUIL_DOC_FAIBLE:
        z += (cfg['pente_doc'] - 1.0) * z0
    f = cfg.get('fmd')
    if f and ze != 0:
        n_fav, n_aut = (r[4], r[5]) if ze > 0 else (r[5], r[4])
        if n_fav < n_aut and n_fav >= (f.get('de') or 0) and (f.get('a') is None or n_fav < f['a']):
            z += cfg['elo'] * (f['pente'] - 1.0) * ze
    return z


def moyenne(d):
    """{matchs, gain, erreur_type} d'une liste d'écarts de log loss par match."""
    n = len(d)
    if not n:
        return {'matchs': 0}
    g = sum(d) / n
    et = math.sqrt(sum((v - g) ** 2 for v in d) / max(n - 1, 1)) / math.sqrt(n)
    return {'matchs': n, 'gain': round(g, 5), 'erreur_type': round(et, 5)}


def log_loss(R, cfg, **essai):
    return sum(EC.ll(z_melange(r, cfg, **essai)) for r in R) / max(len(R), 1)


def gain(R, cfg, **essai):
    """Base « comme en place » moins candidat, par match de R."""
    return moyenne([EC.ll(z_melange(r, cfg)) - EC.ll(z_melange(r, cfg, **essai)) for r in R])


def ecart(R, cfg, essai_1, essai_2):
    """Candidat 2 moins candidat 1 vu en gain : > 0 si essai_1 fait mieux que essai_2."""
    return moyenne([EC.ll(z_melange(r, cfg, **essai_2)) - EC.ll(z_melange(r, cfg, **essai_1)) for r in R])


def apprendre_poids(R, cfg):
    """Poids de la simulation de la grille qui donne la plus petite log loss ; à égalité, le plus proche de l'en place."""
    return min(GRILLE_POIDS, key=lambda b: (round(log_loss(R, cfg, b=b), 9), abs(b - cfg['simulation'])))


def apprendre_pente(R, cfg):
    return min(GRILLE_PENTE, key=lambda k: (round(log_loss(R, cfg, k=k), 9), abs(k - 1.0)))


def apprendre_deux_poids(R, cfg, tours=40):
    """(a, b) par maximum de vraisemblance (Newton à deux paramètres, départ : les poids en place)."""
    a, b = cfg['elo'], cfg['simulation']
    for _ in range(tours):
        ga = gb = haa = hab = hbb = 0.0
        for r in R:
            z1 = z_melange(r, cfg, a=a, b=b)
            da = (z_melange(r, cfg, a=a + 1.0, b=b) - z1)        # z est linéaire en a et en b
            db = (z_melange(r, cfg, a=a, b=b + 1.0) - z1)
            q = EC._sg(z1)
            ga += (1 - q) * da
            gb += (1 - q) * db
            w = q * (1 - q)
            haa += w * da * da
            hab += w * da * db
            hbb += w * db * db
        haa, hbb = haa + 1e-6, hbb + 1e-6
        det = haa * hbb - hab * hab
        if det <= 1e-12:
            break
        pa, pb = (hbb * ga - hab * gb) / det, (haa * gb - hab * ga) / det
        pa, pb = max(min(pa, 0.5), -0.5), max(min(pb, 0.5), -0.5)
        a, b = a + pa, b + pb
        if abs(pa) + abs(pb) < 1e-7:
            break
    return round(a, 4), round(b, 4)


def decrire(R, cfg):
    """Comptes et moyennes d'une case (une tranche sur une période) : Elo seul, simulation seule, mélange en place."""
    n = len(R)
    if not n:
        return {'matchs': 0}
    zm = [z_melange(r, cfg) for r in R]
    out = {'matchs': n,
           'favori_annonce_pct': round(100 * sum(max(EC._sg(z), 1 - EC._sg(z)) for z in zm) / n, 1),
           'favori_reel_pct': round(100 * sum(1.0 if z > 0 else 0.5 if z == 0 else 0.0 for z in zm) / n, 1),
           'log_loss_melange_en_place': round(sum(EC.ll(z) for z in zm) / n, 5),
           'log_loss_elo_seul': round(sum(EC.ll(r[2]) for r in R) / n, 5),
           'log_loss_simulation_seule': round(sum(EC.ll(r[3]) for r in R) / n, 5),
           'simulation_et_elo_meme_favori_pct': round(100 * sum((r[2] > 0) == (r[3] > 0) for r in R) / n, 1)}
    if n >= 30:
        for nom, Z in (('pente_melange_en_place', zm), ('pente_elo_seul', [r[2] for r in R]),
                       ('pente_simulation_seule', [r[3] for r in R])):
            p, et = EC.pente(Z)
            out[nom] = round(p, 3)
            out[nom + '_erreur_type'] = round(et, 3) if et is not None else None
    return out


def _cote(b, ref):
    return 0 if abs(b - ref) < 1e-9 else (1 if b > ref else -1)


def juger_tranche(A, J, cfg, concernee):
    """Une tranche d'un circuit : description, poids appris sur A, jugé sur J, sens inverse, témoins, verdict."""
    out = {'apprentissage': decrire(A, cfg), 'jugement': decrire(J, cfg), 'poids_en_place': cfg['simulation']}
    if len(A) < MIN_APPRIS or not J:
        out['verdict'] = ('aucune décision' if concernee else 'témoin')
        out['raisons'] = [f"moins de {MIN_APPRIS} matchs pour apprendre" if len(A) < MIN_APPRIS else 'aucun match jugé']
        return out
    b_a, k_a = apprendre_poids(A, cfg), apprendre_pente(A, cfg)
    out['poids_appris'] = b_a
    out['sens'] = {1: 'plus de simulation', -1: 'moins de simulation', 0: 'inchangé'}[_cote(b_a, cfg['simulation'])]
    out['gain_apprentissage'] = gain(A, cfg, b=b_a)
    out['gain_jugement'] = gain(J, cfg, b=b_a)
    b_j = apprendre_poids(J, cfg) if len(J) >= MIN_APPRIS else None
    out['sens_inverse'] = ({'poids_appris_sur_la_periode_jugee': b_j, 'gain_sur_l_apprentissage': gain(A, cfg, b=b_j)}
                           if b_j is not None else None)
    out['simple_pente'] = {'pente_apprise': k_a, 'gain_jugement': gain(J, cfg, k=k_a),
                           'poids_moins_pente_jugement': ecart(J, cfg, {'b': b_a}, {'k': k_a})}
    a2, b2 = apprendre_deux_poids(A, cfg)
    out['deux_poids'] = {'elo_appris': a2, 'simulation_apprise': b2, 'elo_en_place': cfg['elo'],
                         'gain_jugement': gain(J, cfg, a=a2, b=b2)}
    if not concernee:
        out['verdict'] = 'témoin'
        return out
    gj = out['gain_jugement']
    if gj['matchs'] < MIN_JUGES:
        out['verdict'] = 'aucune décision'
        out['raisons'] = [f"moins de {MIN_JUGES} matchs de la tranche jugés ({gj['matchs']})"]
        return out
    raisons = []
    if gj['gain'] < MARGE:
        raisons.append(f"gain jugé sous {fr(MARGE)}")
    c_a = _cote(b_a, cfg['simulation'])
    if c_a == 0:
        raisons.append('le poids appris est celui en place')
    elif b_j is None or _cote(b_j, cfg['simulation']) != c_a:
        raisons.append('le poids appris sur la période jugée n\'est pas du même côté')
    if b_j is None or out['sens_inverse']['gain_sur_l_apprentissage'].get('gain', -1) <= 0:
        raisons.append('pas de gain en sens inverse')
    if out['simple_pente']['poids_moins_pente_jugement'].get('gain', -1) <= 0:
        raisons.append('une simple pente fait aussi bien')
    out['verdict'] = 'non retenu' if raisons else 'retenu'
    out['raisons'] = raisons
    out['passe_deux_erreurs_types'] = bool(not raisons and gj['gain'] >= 2 * gj['erreur_type'])
    return out


def juger(rows, cfgs):
    """Tout le jugement, circuit par circuit. rows : sortie de rejeu ; cfgs : sortie de en_place."""
    out = {}
    coupure = COUPURE.isoformat()
    for c in CIRCUITS:
        cfg = cfgs[c]
        R = [r for r in rows if r[0] == c]
        doc = {'matchs': len(R), 'matchs_apprentissage': sum(r[1] < coupure for r in R),
               'matchs_jugement': sum(r[1] >= coupure for r in R), 'tranches': {}}
        d_ens = []
        for nom, _, _ in TRANCHES:
            T = [r for r in R if tranche_de(r) == nom]
            A, J = [r for r in T if r[1] < coupure], [r for r in T if r[1] >= coupure]
            t = juger_tranche(A, J, cfg, nom in CONCERNEES)
            doc['tranches'][nom] = t
            if nom in CONCERNEES:
                b = t.get('poids_appris')
                d_ens += [EC.ll(z_melange(r, cfg)) - EC.ll(z_melange(r, cfg, b=b)) if b is not None else 0.0 for r in J]
        doc['ensemble_des_matchs_concernes_jugement'] = moyenne(d_ens)
        doc['tranches_retenues'] = [n for n in CONCERNEES if doc['tranches'][n].get('verdict') == 'retenu']
        out[c] = doc
    return out


# ------------------------------------------------------------------ sorties
def fr(v):
    """Nombre à la française, sans notation scientifique (0,00009 et non 9e-05)."""
    if isinstance(v, float):
        v = (f"{v:.5f}".rstrip('0').rstrip('.')) or '0'
        v = '0' if v == '-0' else v
    return str(v).replace('.', ',')


def phrase_tranche(nom, t):
    gj, ga = t.get('gain_jugement') or {}, t.get('gain_apprentissage') or {}
    j = t['jugement'].get('matchs', 0)
    if 'poids_appris' not in t:
        return f"{LIBELLE[nom]} : {t['apprentissage'].get('matchs', 0)} matchs appris, {j} jugés — {t['verdict']} ({' ; '.join(t.get('raisons') or [])})"
    inv = t.get('sens_inverse') or {}
    gi = inv.get('gain_sur_l_apprentissage') or {}
    sp = t['simple_pente']
    txt = (f"{LIBELLE[nom]} : poids de la simulation {fr(t['poids_appris'])} au lieu de {fr(t['poids_en_place'])} "
           f"({t['sens']}), {j} matchs jugés, gain {fr(gj.get('gain'))} ± {fr(gj.get('erreur_type'))} "
           f"(apprentissage {fr(ga.get('gain'))} ± {fr(ga.get('erreur_type'))} sur {ga.get('matchs', 0)} matchs ; sens "
           f"inverse : poids {fr(inv.get('poids_appris_sur_la_periode_jugee'))}, gain {fr(gi.get('gain'))} ± "
           f"{fr(gi.get('erreur_type'))} ; simple pente {fr(sp['pente_apprise'])} : {fr(sp['gain_jugement'].get('gain'))} ± {fr(sp['gain_jugement'].get('erreur_type'))}) — "
           f"{t['verdict']}")
    if t.get('raisons'):
        txt += f" ({' ; '.join(t['raisons'])})"
    if t['verdict'] == 'retenu':
        txt += ' (plus de 2 erreurs types)' if t.get('passe_deux_erreurs_types') else ' (sous 2 erreurs types : à confirmer)'
    return txt


def phrase_resultats(jug):
    morceaux = []
    for c in CIRCUITS:
        d = jug[c]
        morceaux.append(f"{NOM_CIRCUIT[c]} ({d['matchs']} matchs rejoués) — "
                        + ' · '.join(phrase_tranche(n, d['tranches'][n]) for n in CONCERNEES))
    retenues = [f"{NOM_CIRCUIT[c]} {LIBELLE[n]}" for c in CIRCUITS for n in jug[c]['tranches_retenues']]
    fin = ('Retenu : ' + ', '.join(retenues) + ' ; proposé à Lucas, rien n\'est changé par ce paquet.' if retenues else
           'Aucune tranche retenue ; rien n\'est changé par ce paquet.')
    return ' RÉSULTAT : ' + ' ; '.join(morceaux) + '. ' + fin


def entree_journal(doc, gabarit):
    return {'date': gabarit['date'], 'statut': gabarit['statut'], 'paquet': gabarit['paquet'],
            'quoi': gabarit['quoi_debut'] + phrase_resultats(doc['jugement']) + ' Le % de victoire ne change pas.',
            'garde_fou': gabarit['garde_fou']}


def afficher(jug, journal=print):
    """Ce qui part dans le journal du run (public) : comptes et moyennes seulement."""
    for c in CIRCUITS:
        d = jug[c]
        journal(f"== {NOM_CIRCUIT[c]} — {d['matchs']} matchs ({d['matchs_apprentissage']} appris, {d['matchs_jugement']} jugés)")
        for nom, _, _ in TRANCHES:
            t = d['tranches'][nom]
            for per in ('apprentissage', 'jugement'):
                x = t[per]
                journal(f"   {LIBELLE[nom]:22s} {per:13s} {x.get('matchs', 0):5d} m. | favori {x.get('favori_annonce_pct')} annoncé / "
                        f"{x.get('favori_reel_pct')} réel | pente Elo {x.get('pente_elo_seul')} · simulation "
                        f"{x.get('pente_simulation_seule')} · mélange {x.get('pente_melange_en_place')} | log loss Elo "
                        f"{x.get('log_loss_elo_seul')} · simulation {x.get('log_loss_simulation_seule')} · mélange "
                        f"{x.get('log_loss_melange_en_place')}")
            journal('     → ' + phrase_tranche(nom, t)
                    + (f" | deux poids : Elo {t['deux_poids']['elo_appris']}, simulation {t['deux_poids']['simulation_apprise']}, "
                       f"gain jugé {fr(t['deux_poids']['gain_jugement'].get('gain'))} ± {fr(t['deux_poids']['gain_jugement'].get('erreur_type'))}" if t.get('deux_poids') else ''))
        e = d['ensemble_des_matchs_concernes_jugement']
        journal(f"   ensemble des matchs concernés jugés : {e.get('matchs', 0)} m., gain {fr(e.get('gain'))} ± {fr(e.get('erreur_type'))} "
                f"| retenues : {d['tranches_retenues'] or 'aucune'}")


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
    cfgs = en_place(racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': PAQUET,
           'regle': REGLE, 'apprentissage': [DEBUT.isoformat(), COUPURE.isoformat()],
           'jugement_une_seule_fois': [COUPURE.isoformat(), FIN.isoformat()],
           'itf_hommes_dans_le_rejeu': n_itf, 'profils_refaits': n_adj, 'en_place': cfgs,
           'jugement': juger(rows, cfgs), 'limites': LIMITES, 'en_production': False}
    with open(GABARIT_JOURNAL, encoding='utf-8') as f:
        doc['entree_journal'] = entree_journal(doc, json.load(f))
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    EC.ajouter_au_journal(JOURNAL, doc['entree_journal'])
    afficher(doc['jugement'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
