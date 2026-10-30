#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pronostics_du_jour.py — pronostic de chaque match à venir, deux versions côte à côte (21/10/2026).

  « stats seules »   : force Elo (elo_etat.json, refait chaque run depuis tous
                        les résultats) + style service/retour de chaque joueur
                        (notes_joueurs.json) + forme du jour, dans le moteur ;
  « simulation pure » : profils service/retour ajustés aux adversaires ;
  « combinaison »   : Elo + simulation + corrections apprises sur le passé.
Aucune cote ni aucun mouvement de marché n'entre dans ces trois variantes.
Pour chaque match : probabilité de victoire, 2-0 / 2-1 / 1-2 / 0-2 (ou en 5
sets), les 3 scores complets les plus probables set par set dans l'ordre réel
(ex. « 4-6 6-3 6-4 »), victoire après la perte du 1er set, set 1, total de jeux
moyen, au moins un tie-break.

JOURNAL : le PREMIER pronostic de chaque match est écrit une fois dans
simulateur/pronostics_log.jsonl et jamais modifié ; le bilan (taux de
vainqueurs devinés des deux versions, sur les matchs joués) se calcule sur ce
journal — un vrai suivi en direct, sans retouche.

MATCH SIMULÉ : chaque version est aussi jouée SIMULATIONS fois point
par point (match_simule.py) avec le profil de service des deux joueurs
(profils_service.json : % de 1re balle, aces, doubles fautes, points gagnés
derrière la 1re et la 2e balle, qualité de retour), au niveau de la version.
On en tire la feuille de stats prévue (moyenne et fourchette à 80 %) et un
match type, set par set avec les breaks.

Entrées : matches_oddspapi.json (matchs à venir), simulateur/elo_etat.json,
simulateur/notes_joueurs.json, simulateur/profils_service.json, set_results.json (résultats).
Sorties : Tennis_Edge_Lab/live/pronostics.json, Tennis_Edge_Lab/live/pronostics_bilan.json,
simulateur/pronostics_log.jsonl. 0 requête API.
"""
import datetime as dt
import json
import math
import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import contexte_optionnel as CO  # noqa: E402
import distribution_exacte as DE  # noqa: E402
import elo as E  # noqa: E402
import feuilles as FE  # noqa: E402
import fiabilite as FI  # noqa: E402
import match_simule as MS  # noqa: E402
import modele as M  # noqa: E402
import nos_resultats as NR  # noqa: E402
import profils_service as PS  # noqa: E402
import ajustement as AJ  # noqa: E402

SIGMA = 0.15
SIMULATIONS = int(os.environ.get('SIMULATIONS', '20000'))
STABILITE_BLOCS = int(os.environ.get('STABILITE_BLOCS', '2'))
BALLES_CONNU = 500          # profil « connu » : au moins 500 balles de service (pondérées) dans l'archive
HORIZON_H = 36
LOG = 'simulateur/pronostics_log.jsonl'
# 22/10/2026 — TOUT est enregistré pour l'analyse a posteriori :
#   INSTANTANES : chaque passage (toutes les 6 h), chaque match, chaque version (%, sets, scores,
#                 jeux, tie-break, facteurs) — on voit le pronostic évoluer jusqu'au match ;
#   RESULTATS   : chaque match joué, prédiction (1re et dernière avant le match) contre résultat réel
#                 (vainqueur, score en sets et en jeux, feuille de stats), et ce qui était juste ou faux.
INSTANTANES = 'simulateur/journal_pronostics'
RESULTATS = 'Tennis_Edge_Lab/live/pronostics_resultats.json'
VERSIONS = ('combinaison', 'simulation', 'stats')
SORTIE = 'Tennis_Edge_Lab/live/pronostics.json'
BILAN = 'Tennis_Edge_Lab/live/pronostics_bilan.json'


def circuit(t):
    t = str(t or '').lower()
    if 'wta' in t or 'women' in t:
        return 'WTA'
    if 'itf' in t:
        return 'ITF'
    if 'challenger' in t:
        return 'CH'
    return 'ATP'


def sig(z):
    return 1 / (1 + math.exp(-z))


class Styles:
    """Service / retour de chaque joueur (notes Sackmann ajustées aux adversaires)."""

    def __init__(self, chemin):
        try:
            doc = json.load(open(chemin, encoding='utf-8'))
        except (OSError, ValueError):
            doc = {}
        self.mu = {}
        for k, v in (doc.get('mu') or {}).items():
            c, _, s = k.partition(' ')
            self.mu[(c, s)] = v
        self.j = {}
        for v in (doc.get('joueurs') or {}).values():
            k = E.cle(v.get('nom'))
            if k and (k not in self.j or v.get('points', 0) > self.j[k][2]):
                self.j[k] = (v.get('service', 0.0), v.get('retour', 0.0), v.get('points', 0))

    def mu_de(self, c, s):
        if (c, s) in self.mu:
            return self.mu[(c, s)]
        v = [x for (cc, _), x in self.mu.items() if cc == c]
        return sum(v) / len(v) if v else 0.5

    def service(self, a, b, c, s):
        """P(A gagne un point sur son service contre B), avant ancrage au niveau."""
        sa, ra = (self.j.get(a) or (0.0, 0.0, 0))[:2]
        sb, rb = (self.j.get(b) or (0.0, 0.0, 0))[:2]
        mu = self.mu_de(c, s)
        return sig(mu + sa - rb), sig(mu + sb - ra)

    def connu(self, a):
        return a in self.j


def pronostic(p_home, c, sg, pa0, pb0):
    """Distribution complète, niveau ancré sur p_home, style (pa0, pb0).

    Scores : les 3 scores COMPLETS les plus probables, set par set et dans l'ordre
    réel (modele.scores_complets : rien n'est supposé — le vainqueur peut perdre le
    1er set). Il y a ~1 500 scores possibles : même le premier dépasse rarement 4 %."""
    sig = sigma_de(c)
    a, b = M.ancrer_forme(pa0, pb0, min(max(p_home, 0.01), 0.99), sg, sig, iterations=20)
    r = M.match_forme(a, b, sg, sig)
    sc = M.scores_complets(a, b, sg, sig, top=3)
    return {'p_home': round(r['victoire'], 4),
            'sets': {k: round(v, 4) for k, v in r['sets'].items()},
            'scores_probables': [[s_, round(p_, 4)] for s_, p_ in sc['scores']],
            'remontee': {'home': round(sc['remontee_A'], 4), 'away': round(sc['remontee_B'], 4)},
            'set1_home': round(r['set1'], 4),
            'jeux_moyen': round(M.moyenne(r['total_jeux']), 1),
            'tiebreak': round(r['tiebreak'], 3)}


def charger_profils(racine):
    try:
        with open(os.path.join(racine, 'simulateur', 'profils_service.json'), encoding='utf-8') as f:
            return PS.Profils.importer(json.load(f))
    except (OSError, ValueError, KeyError):
        return None


def charger_reglages(racine):
    """Réglages du match simulé, seulement s'ils ont été ADOPTÉS (reglage_match_simule.py)."""
    try:
        with open(os.path.join(racine, 'simulateur', 'reglages_match_simule.json'), encoding='utf-8') as f:
            d = json.load(f)
        return d['reglages'] if d.get('adopte') else None
    except (OSError, ValueError, KeyError):
        return None


REGLAGES = None


def charger_choix(racine):
    """Composantes retenues par le test (backtest_match_simule.py) : 'ajustees' ou 'profils'."""
    try:
        with open(os.path.join(racine, 'simulateur', 'choix_simulation.json'), encoding='utf-8') as f:
            return json.load(f).get('composantes', 'profils')
    except (OSError, ValueError):
        return 'profils'


CHOIX = 'profils'


def charger_combinaison(racine):
    """Poids de la combinaison simulation + Elo si le test l'a adoptée (backtest_match_simule.py), sinon None."""
    try:
        with open(os.path.join(racine, 'simulateur', 'choix_simulation.json'), encoding='utf-8') as f:
            choix = json.load(f)
        cc = choix.get('combinaison_continue') or {}            # appris sur NOS matchs joués (apprentissage continu)
        if cc.get('adopte') and cc.get('poids'):
            return dict(cc['poids'], source='nos matchs joués')
        cf = choix.get('combinaison_feuilles') or {}            # rejouée semaine après semaine sur les feuilles
        if cf.get('adopte') and cf.get('poids'):
            return dict(cf['poids'], source='les feuilles depuis juin (entraînement semaine après semaine)')
        cb = choix.get('combinaison') or {}
        return dict(cb['poids'], source='archive 2024–2026') if cb.get('adopte') and cb.get('poids') else None
    except (OSError, ValueError, KeyError):
        return None


COMBINAISON = None
ACTIVITE = None       # 29/10/2026 : activité récente des joueurs (activite.py), chargée par construire()
ECHANGES = None       # 30/10/2026 : longueur des échanges (Match Charting Project), affichage seul
FORME_SERVICE = None  # 29/10/2026 : service / retour du moment (forme_service.py), information + modèle fantôme
PROGRAMME = {}        # 29/10/2026 : {(jour, clé, clé) triée: tour} — programme du jour relevé par feuilles_match.py


def charger_programme(racine, jours=4):
    """Programme des derniers jours (feuilles/programme/AAAA-MM-JJ.json) : le tour de chaque match à venir."""
    import glob
    out = {}
    for p in sorted(glob.glob(os.path.join(racine, 'feuilles', 'programme', '20*.json')))[-jours:]:
        try:
            with open(p, encoding='utf-8') as f:
                doc = json.load(f)
        except (OSError, ValueError):
            continue
        for r in (doc.get('matchs') or {}).values():
            if r.get('tour') and r.get('home') and r.get('away'):
                out[(str(r.get('jour')), *sorted((E.cle(r['home']), E.cle(r['away']))))] = r['tour']
    return out


def tour_du_match(h, a, debut):
    """Nom du tour (« Round of 32 »…) d'un match à venir, ou None ; h, a : clés des joueurs."""
    j = (debut.date() if isinstance(debut, dt.datetime) else debut).isoformat()
    return PROGRAMME.get((j, *sorted((h, a))))
CLASSEMENTS = None   # 23/10/2026 : classements (archive résumée + photos TennisApi), classements.py
AJUSTEMENTS = {}      # 22/10/2026 : poids propres aux Challenger, correction des nouveaux venus (si adoptés)


def charger_ajustements(racine):
    """Décisions de l'entraînement semaine après semaine (facteurs.py → entrainement_progressif.py)."""
    try:
        with open(os.path.join(racine, 'simulateur', 'choix_simulation.json'), encoding='utf-8') as f:
            choix = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    pc = choix.get('poids_challenger') or {}
    if pc.get('adopte') and pc.get('poids'):
        out['poids_CH'] = pc['poids']
    for c_ in ('ATP', 'WTA'):                                  # 29/10/2026 : même règle que les Challenger
        v = choix.get('poids_' + c_) or {}
        if v.get('adopte') and v.get('poids'):
            out['poids_' + c_] = v['poids']
    nv = choix.get('nouveaux_venus') or {}
    if nv.get('adopte') and nv.get('delta') is not None:
        out['delta_nouveaux'] = float(nv['delta'])
    ma = choix.get('modele_arbres') or {}                      # 23/10/2026 : arbres qui combinent tout (si adoptés)
    if ma.get('adopte') and ma.get('modele') and ma.get('poids'):
        out['arbres'] = {'modele': ma['modele'], 'poids': ma['poids']}
    # 29/10/2026 : candidats de la famille des arbres (activité récente, tour du tableau) ; si plusieurs sont adoptés,
    # celui qui a la log loss la plus basse au dernier jugement
    adoptes = []
    for cle_c in ('modele_arbres_activite', 'modele_arbres_tour', 'modele_arbres_points'):
        v = choix.get(cle_c) or {}
        if v.get('adopte') and v.get('modele') and v.get('poids'):
            adoptes.append(((v.get('ll') or {}).get('avec') or 9.0, cle_c, v))
    if adoptes:
        _, cle_c, v = min(adoptes)
        out['arbres_candidat'] = {'cle': cle_c, 'modele': v['modele'], 'poids': v['poids']}
    dw = choix.get('desaccord_wta') or {}                      # 29/10/2026 : désaccords Elo / simulation en WTA
    if dw.get('adopte') and dw.get('poids'):
        out['poids_desaccord_wta'] = dw['poids']
    for cle_s in ('qualifies', 'transition', 'classement', 'classement_relatif'):    # 22/10/2026 : même règle
        v = choix.get(cle_s) or {}
        if v.get('adopte') and v.get('delta') is not None:
            out['delta_' + cle_s] = float(v['delta'])
    return out


def ajuster_combinaison(p_c, c, p_elo, p_sim, n_home, n_away, situations=None, surface=None, bo=3):
    """Pronostic final ; 29/10/2026 : en WTA, si l'Elo et la simulation désignent deux vainqueurs différents et que
    la règle desaccord_wta est adoptée, son mélange propre remplace le reste (entrainement_progressif.desaccord_wta)."""
    pw = AJUSTEMENTS.get('poids_desaccord_wta')
    if pw and c == 'WTA' and p_elo is not None and p_sim is not None and (p_elo >= .5) != (p_sim >= .5):
        return MS.melange(pw, p_elo, p_sim)
    return _ajuster_combinaison(p_c, c, p_elo, p_sim, n_home, n_away, situations, surface, bo)


def _ajuster_combinaison(p_c, c, p_elo, p_sim, n_home, n_away, situations=None, surface=None, bo=3):
    """Challenger : poids propres s'ils sont adoptés (remplacent le mélange commun) ; puis chaque situation
    adoptée (règle de entrainement_progressif.correction_situation) : z += δ·(situation(home) − situation(away)).
    Nouveaux venus : nouveau(n) = max(0, 1 − n/30) ; situations = {'qualifies': (h, a), 'transition': (h, a)}."""
    ac_ = AJUSTEMENTS.get('arbres_candidat')
    if ac_:
        # 29/10/2026 : arbres avec les variables d'un candidat adopté (activité récente ou tour du tableau) ; sans la
        # donnée (tour inconnu…), sa valeur neutre, comme à l'apprentissage
        import arbres as A
        import entrainement_progressif as EP
        sit = situations or {}
        q, t = sit.get('qualifies') or (0.0, 0.0), sit.get('transition') or (0.0, 0.0)
        sit_k = EP.CANDIDATS_ARBRES[ac_['cle']][0]
        v = EP.variables_candidat(ac_['cle'], p_elo, p_sim, n_home or 0, n_away or 0, (q[0], t[0]), (q[1], t[1]), c, surface, bo,
                                  sit.get('rangs'), sit.get(sit_k))
        pm = MS.melange(ac_['poids'], p_elo, p_sim)
        return A.predire_symetrique(ac_['modele'], v, math.log(pm / (1 - pm)), EP.ecarts_candidat(ac_['cle']))
    if AJUSTEMENTS.get('arbres'):
        # les arbres partent de LEUR mélange et contiennent déjà nouveaux venus, qualifiés, surface, circuit…
        import arbres as A
        import entrainement_progressif as EP
        sit = situations or {}
        q, t = sit.get('qualifies') or (0.0, 0.0), sit.get('transition') or (0.0, 0.0)
        v = EP.variables_match(p_elo, p_sim, n_home or 0, n_away or 0, (q[0], t[0]), (q[1], t[1]), c, surface, bo,
                               sit.get('rangs'))
        o = math.log(MS.melange(AJUSTEMENTS['arbres']['poids'], p_elo, p_sim) / (1 - MS.melange(AJUSTEMENTS['arbres']['poids'], p_elo, p_sim)))
        return A.predire_symetrique(AJUSTEMENTS['arbres']['modele'], v, o, EP.ECARTS)
    if c in ('CH', 'ATP', 'WTA') and AJUSTEMENTS.get('poids_' + c):    # 29/10/2026 : ATP et WTA aussi
        p_c = MS.melange(AJUSTEMENTS['poids_' + c], p_elo, p_sim)
    ecarts = []
    if AJUSTEMENTS.get('delta_nouveaux') and n_home is not None and n_away is not None:
        ecarts.append((AJUSTEMENTS['delta_nouveaux'], max(0.0, 1 - n_home / 30) - max(0.0, 1 - n_away / 30)))
    for cle_s, (vh, va) in ((k, v) for k, v in (situations or {}).items() if k not in ('activite', 'rangs', 'tour', 'points')):
        if AJUSTEMENTS.get('delta_' + cle_s):
            ecarts.append((AJUSTEMENTS['delta_' + cle_s], vh - va))
    dz = sum(d * f for d, f in ecarts)
    if dz:
        q = min(max(p_c, 1e-6), 1 - 1e-6)
        p_c = sig(max(min(math.log(q / (1 - q)) + dz, 30), -30))
    return p_c


def situations_du_match(h, a, tournoi, debut, surface):
    """(qualifié, changement de surface) de chaque joueur, depuis le contexte des facteurs ; {} sans contexte."""
    if CONTEXTE is None or not hasattr(CONTEXTE, 'qualifie'):
        return {}
    ts = (debut.replace(tzinfo=dt.timezone.utc).timestamp() if debut.tzinfo is None else debut.timestamp()) \
        if isinstance(debut, dt.datetime) else float(debut)
    return {'qualifies': (CONTEXTE.qualifie(h, tournoi, ts), CONTEXTE.qualifie(a, tournoi, ts)),
            'transition': (CONTEXTE.transition(h, surface, ts), CONTEXTE.transition(a, surface, ts))}


def charger_facteurs(racine):
    """Facteurs du match ADOPTÉS par l'étude (facteurs.py, règle fixée d'avance) et contexte du jour
    (forme, fatigue, vitesse des tournois, gaucher/taille, points importants). (None, None) sinon."""
    try:
        with open(os.path.join(racine, 'simulateur', 'facteurs.json'), encoding='utf-8') as f:
            doc = json.load(f)
        if not doc.get('adoptes') or not doc.get('coefs'):
            return None, None
        import facteurs as FA
        with open(os.path.join(racine, 'simulateur', 'facteurs_contexte.json'), encoding='utf-8') as f:
            return doc, FA.Contexte(json.load(f))
    except (OSError, ValueError, ImportError):
        return None, None


FACTEURS, CONTEXTE = None, None
FORME_SCORES = None             # 28/10/2026 : (coefs, profils, repères par circuit) si la forme des scores est adoptée
SIGMA_CIRCUIT = None            # 28/10/2026 : {circuit: σ} de la forme du jour si sigma_circuit.py l'a ADOPTÉ


def controle_fantome(elo, elo_ref, ref_etat, etat, h, a, c, s, elo_fem=None, fem_etat=None):
    """{p_elo, p_elo_reference, reference} : la probabilité Elo en place et celle du modèle fantôme (Elo d'avant les
    changements), jamais affichée comme pronostic ; comparées après le match (apres_match.py).
    29/10/2026 : + p_elo_sans_itf_femmes (matchs WTA) : l'Elo sans les seuls résultats ITF femmes."""
    out = {}
    for e_, et_, cle in ((elo_ref, ref_etat, 'p_elo_reference'), (elo_fem if c == 'WTA' else None, fem_etat, 'p_elo_sans_itf_femmes')):
        if e_ is None:
            continue
        if (et_ or {}).get('depart_bas') and c in ('CH', 'ITF'):
            e_.presenter(h, et_['depart_bas'])
            e_.presenter(a, et_['depart_bas'])
        out[cle] = round(e_.proba(h, a, s), 4)
    if not out:
        return None
    out.update({'p_elo': round(elo.proba(h, a, s), 4), 'en_place': (etat or {}).get('variante')})
    if 'p_elo_reference' in out:
        out['reference'] = ref_etat.get('variante')
    return out


def _avec_forme(ct, forme):
    if not forme:
        return ct
    return dict(ct or {}, forme=forme)


def _echanges(h, a, debut):
    """30/10/2026 : [profil home, profil away] de la longueur des échanges, ou None si aucun des deux n'est charté."""
    if ECHANGES is None:
        return None
    try:
        e = [ECHANGES.profil(k, debut) for k in (h, a)]
    except Exception:  # noqa: BLE001 — affichage seul
        return None
    return e if any(e) else None


def _avec_service(ct, fsv_ctl):
    """29/10/2026 : le fantôme « forme du service » dans le bloc de contrôle (créé s'il n'existe pas)."""
    if not fsv_ctl:
        return ct
    return dict(ct or {}, forme_service=fsv_ctl)


def controle_forme(PR, h, a, c, s, sg, p_home, fct):
    """29/10/2026 — FANTÔME DE LA FORME DU JOUR : pour un circuit dont le σ a changé (Challenger 0,22), la forme du
    match (camp × tie-break × 3 sets × jeux) avec le σ en place et avec l'ancien (0,15), même vainqueur (ancrage).
    Jamais affichée ; la forme réelle les départage après le match. None si σ inchangé ou match en 5 sets."""
    import sigma_circuit as SGC
    import forme_scores as FS
    sig = sigma_de(c)
    if sg != 2 or sig == SGC.BASE or p_home is None:
        return None
    m1 = FS.masses(distribution_exacte_du_match(PR, h, a, c, s, sg, p_home, fct, sigma=sig, brut=True))
    m0 = FS.masses(distribution_exacte_du_match(PR, h, a, c, s, sg, p_home, fct, sigma=SGC.BASE, brut=True))
    cles = sorted(set(m1) | set(m0))
    return {'sigma': sig, 'sigma_reference': SGC.BASE,
            'masses': [[int(k[0]), bool(k[1]), bool(k[2]), int(k[3]), round(m1.get(k, 0.0), 4), round(m0.get(k, 0.0), 4)]
                       for k in cles if max(m1.get(k, 0.0), m0.get(k, 0.0)) >= 5e-4]}


def controle_forme_service(cH, cA, vh, va, c, s, sg, p_elo, p_sim, n_h, n_a, sit):
    """29/10/2026 — FANTÔME « FORME DU SERVICE » : la simulation rejouée avec le service et le retour du moment
    (forme_service.decalages), puis le même mélange avec l'Elo et les mêmes ajustements que le pronostic affiché.
    Jamais affiché comme pronostic ; jugé après les matchs (apres_match : fantome_forme_service). None sans écart."""
    import forme_service as FSV
    dh, da = FSV.decalages(vh, va)
    if not (dh or da) or not COMBINAISON:
        return None
    cH2, cA2 = MS.appliquer_facteurs(cH, dh), MS.appliquer_facteurs(cA, da)
    p_sim2 = MS.victoire_pure(cH2, cA2, sg, sigma_sim())
    p2 = MS.melange_contexte(COMBINAISON, MS.contexte_match(s, c, 2 * sg - 1), p_elo, p_sim2)
    p2 = MS.calibrer(p2, COMBINAISON.get('calibration'))
    p2 = ajuster_combinaison(p2, c, p_elo, p_sim2, n_h, n_a, sit, s, 2 * sg - 1)
    return {'p_home': round(p2, 4), 'p_simulation': round(p_sim2, 4), 'p_simulation_sans': round(p_sim, 4),
            'decalages': [round(dh, 4), round(da, 4)]}


def charger_sigma_circuit(racine):
    """{circuit: σ} de la forme du jour. 28/10/2026 : en production par décision de Lucas (sigma_circuit.DECISION,
    Challenger 0,22) tant que le jugement hebdomadaire n'a rien dit ; ensuite ce que dit facteurs.json — σ appris si
    en place, None (0,15 partout) s'il a été RETIRÉ (moins bien deux semaines de suite)."""
    import sigma_circuit as SGC
    try:
        with open(os.path.join(racine, 'simulateur', 'facteurs.json'), encoding='utf-8') as f:
            r = json.load(f).get('sigma_circuit')
    except (OSError, ValueError):
        r = None
    if not r or 'adopte' not in r:
        return dict(SGC.DECISION)
    try:
        return {k: float(v) for k, v in (r.get('sigmas') or SGC.DECISION).items()} if r.get('adopte') else None
    except (TypeError, ValueError):
        return dict(SGC.DECISION)


def sigma_de(c):
    """σ de la forme du jour pour un circuit (le vainqueur ne dépend pas de σ : seule la forme du match)."""
    return (SIGMA_CIRCUIT or {}).get(c, SIGMA)


def charger_forme_scores(racine):
    """(coefs, profils, repères par circuit) si facteurs.json l'a ADOPTÉE (forme_scores.py v3, règle fixée,
    stabilité), sinon None."""
    try:
        with open(os.path.join(racine, 'simulateur', 'facteurs.json'), encoding='utf-8') as f:
            fs = json.load(f).get('forme_scores') or {}
        if not fs.get('adopte') or not fs.get('coefs') or fs.get('version') != 3:
            return None
        with open(os.path.join(racine, 'simulateur', 'profil_rythme.json'), encoding='utf-8') as f:
            doc = json.load(f)
        return fs['coefs'], doc.get('joueurs') or {}, doc.get('references_circuit') or {}
    except (OSError, ValueError):
        return None


def charger_reglage_simulation(racine):
    """Réglage de la simulation pure adopté par le test (σ de la forme du jour, amplification k), ou None."""
    try:
        with open(os.path.join(racine, 'simulateur', 'choix_simulation.json'), encoding='utf-8') as f:
            r = json.load(f).get('reglage_simulation') or {}
        return {'sigma': float(r['sigma']), 'k': float(r['amplification']), 'jeux': float(r.get('jeux') or 0)} if r.get('adopte') else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


REGLAGE_SIM = None


def sigma_sim():
    return REGLAGE_SIM['sigma'] if REGLAGE_SIM else SIGMA


def composantes_du_match(P, h, a, c, s, pure=False):
    """pure=True : la simulation pure (son réglage adopté s'applique) ; sinon versions ancrées (inchangées)."""
    ph, nh = P.profil(h, c, s, P.jour_export)
    pa, na = P.profil(a, c, s, P.jour_export)
    mu = P.moyenne(c, s)
    if CHOIX == 'ajustees' and getattr(P, 'ajuste', None) is not None:
        cH, cA = MS.composantes_ajustees(P.ajuste, h, a, c, s), MS.composantes_ajustees(P.ajuste, a, h, c, s)
        if pure and getattr(P, 'resultats', None):       # appris aussi de qui a gagné (matchs sans feuille, si adopté)
            d = P.resultats.get(h, 0.0) - P.resultats.get(a, 0.0)
            cH = MS.borner(dict(cH, w1=MS._sg(MS._lg(cH['w1']) + d), w2j=MS._sg(MS._lg(cH['w2j']) + d)))
            cA = MS.borner(dict(cA, w1=MS._sg(MS._lg(cA['w1']) - d), w2j=MS._sg(MS._lg(cA['w2j']) - d)))
        if pure and REGLAGE_SIM and getattr(P, 'jeux', None):            # appris aussi des scores sans feuille
            cH, cA = MS.borner(AJ.avec_jeux(cH, P.jeux, h, a)), MS.borner(AJ.avec_jeux(cA, P.jeux, a, h))
        if pure and REGLAGE_SIM and REGLAGE_SIM['k'] != 1.0:
            moy = MS.borner(P.ajuste.taux('__moyen__', '__moyen__', c, s))
            cH, cA = MS.amplifier(cH, moy, REGLAGE_SIM['k']), MS.amplifier(cA, moy, REGLAGE_SIM['k'])
    else:
        cH, cA = MS.composantes(ph, pa, mu), MS.composantes(pa, ph, mu)
    return cH, cA, nh, na


def facteurs_du_match(h, a, tournoi, debut, adj=None):
    """{groupe adopté: ((d_service, d_aces, d_bp) home, (…) away)} en logit, + variables lues."""
    if not FACTEURS or CONTEXTE is None:
        return None
    import facteurs as FA
    ts = debut.replace(tzinfo=dt.timezone.utc).timestamp() if debut.tzinfo is None else debut.timestamp()
    vH, vA = CONTEXTE.variables(h, a, tournoi, ts, adj), CONTEXTE.variables(a, h, tournoi, ts, adj)
    coefs = FACTEURS['coefs']
    par_groupe = {}
    for g in FACTEURS['adoptes']:
        cg = {m: {f: b for f, b in (coefs.get(m) or {}).items() if f in FA.GROUPES[g].get(m, [])} for m in coefs}
        par_groupe[g] = (FA.deltas(vH, cg), FA.deltas(vA, cg))
    return {'groupes': par_groupe, 'total': (FA.deltas(vH, coefs), FA.deltas(vA, coefs))}


def avec_facteurs(cH, cA, fct):
    if not fct:
        return cH, cA
    dH, dA = fct['total']
    return MS.appliquer_facteurs(cH, *dH), MS.appliquer_facteurs(cA, *dA)


def impact_facteurs(cH, cA, sg, fct):
    """Ce qui pèse : victoire home (simulation pure, limite exacte) sans facteurs, avec tous, et
    l'écart dû à chaque groupe seul (en points de %)."""
    if not fct:
        return None
    base = MS.victoire_pure(cH, cA, sg, sigma_sim())
    tH, tA = avec_facteurs(cH, cA, fct)
    out = {'sans': round(base, 4), 'avec': round(MS.victoire_pure(tH, tA, sg, sigma_sim()), 4), 'groupes': {}}
    for g, (dH, dA) in fct['groupes'].items():
        p = MS.victoire_pure(MS.appliquer_facteurs(cH, *dH), MS.appliquer_facteurs(cA, *dA), sg, sigma_sim())
        out['groupes'][g] = round(100 * (p - base), 1)
    return out


def match_simule(P, h, a, c, s, sg, p_home, cle, fct=None, controler_stabilite=False):
    """Le match joué SIMULATIONS fois au niveau p_home, avec les profils de service des deux joueurs
    (et les facteurs du match adoptés, s'il y en a)."""
    cH, cA, nh, na = composantes_du_match(P, h, a, c, s, pure=p_home is None)
    cH, cA = avec_facteurs(cH, cA, fct)
    sigma = sigma_sim() if p_home is None else sigma_de(c)
    r = MS.simuler(cH, cA, p_home, sg, SIMULATIONS, sigma, cle=cle, reglages=REGLAGES)
    if controler_stabilite and STABILITE_BLOCS > 0:
        import stabilite_scores as SS
        r['stabilite_score'] = SS.controler(cH, cA, p_home, r, sg, SIMULATIONS, sigma, cle,
                                           reglages=REGLAGES, blocs=STABILITE_BLOCS)
    r['reglages'] = REGLAGES
    r['composantes'] = CHOIX if (CHOIX == 'ajustees' and getattr(P, 'ajuste', None) is not None) else 'profils'
    r['profil_connu'] = [nh >= BALLES_CONNU, na >= BALLES_CONNU]
    niveau = lambda n: 'tres_faible' if n < 100 else 'faible' if n < 500 else 'documente'
    prior_service = 150 * getattr(P, 'prior_mult', 1.0)
    r['profil_contexte'] = {
        'n_balles_effectives': [round(nh, 1), round(na, 1)],
        'niveau_documentation': [niveau(nh), niveau(na)],
        'poids_donnees_service': [round(nh/(nh+prior_service), 4), round(na/(na+prior_service), 4)],
    }
    if CONTEXTE is not None:
        try:
            jour = P.jour_export
            ts = dt.datetime.combine(jour, dt.time(), tzinfo=dt.timezone.utc).timestamp() if isinstance(jour, dt.date) and not isinstance(jour, dt.datetime) else jour.timestamp()
            r['profil_contexte']['changement_surface'] = [bool(CONTEXTE.transition(h, s, ts)), bool(CONTEXTE.transition(a, s, ts))]
        except (AttributeError, KeyError, TypeError, ValueError):
            pass
    return r


def distribution_exacte_du_match(P, h, a, c, s, sg, p_home, fct=None, pure=False, sigma=None, brut=False):
    """Distribution complète sans bruit Monte Carlo, ancrée sur CETTE variante.

    Elle ne remplace ni les tirages, ni leur médoid, ni leurs statistiques. Le
    contrôle de masse et de victoire est bloquant pour éviter un score trompeur.
    """
    cH, cA, _, _ = composantes_du_match(P, h, a, c, s, pure=pure)
    cH, cA = avec_facteurs(cH, cA, fct)
    sigma = sigma if sigma is not None else (sigma_sim() if pure else sigma_de(c))
    distribution = DE.distribution_forme(cH, cA, sg, sigma, p_victoire=p_home)
    if brut:                        # 29/10/2026 : distribution seule (fantôme de la forme du jour)
        return distribution
    forme = None
    if FORME_SCORES and not pure and sg == 2:
        # 28/10/2026 : forme du match selon les profils (tie-break, 3 sets) ; vainqueur inchangé par construction
        import forme_scores as FS
        f = FS.caracteristiques(FORME_SCORES[1].get(h), FORME_SCORES[1].get(a), FORME_SCORES[2].get(c))  # None : base seule
        distribution = FS.reponderer(distribution, f, FORME_SCORES[0], c)          # base propre au circuit (v3)
        forme = {'caracteristiques': [round(x, 4) for x in f] if f else None, 'coefs': FORME_SCORES[0]}
    controle = DE.controle(distribution)
    victoire = DE.victoire_depuis_distribution(distribution)
    if not controle['ok'] or abs(victoire - p_home) > 1e-8:
        raise ValueError(f'Distribution exacte incohérente pour {h}–{a}: {controle}, victoire={victoire}')
    rows = DE.scores_ordonnes(distribution)
    scores = [(' '.join(f'{x}-{y}' for x, y in r['score']), r['probabilite']) for r in rows]
    return {'source': 'exact', 'scores': [[score, round(p, 8)] for score, p in scores[:3]],
            'distribution': [{'score': r['score'], 'vainqueur': r['vainqueur'],
                              'probabilite': round(r['probabilite'], 12)} for r in rows],
            'controle': {'somme': controle['somme'], 'n_scores': controle['n_scores'],
                         'victoire_home': victoire, 'monte_carlo': False},
            'forme_profils': forme}


def matchs_a_venir(racine, maintenant, avec_couverture=False):
    try:
        with open(os.path.join(racine, 'matches_oddspapi.json'), encoding='utf-8') as f:
            L = json.load(f)
    except (OSError, ValueError):
        L = []
    L = L if isinstance(L, list) else list(L.values())
    out, invalides, valides = [], [], 0
    for m in L:
        try:
            debut_utc = CO.instant(str(m['commence_time']))
            debut = debut_utc.replace(tzinfo=None)       # comparaison historique en UTC naïf
            valides += 1
        except (KeyError, TypeError, ValueError):
            invalides.append({'id': m.get('id'), 'raison': 'commence_time absent, invalide ou sans fuseau'})
            continue
        if not (maintenant < debut <= maintenant + dt.timedelta(hours=HORIZON_H)):
            continue
        h, a = m.get('home_team'), m.get('away_team')
        if not h or not a:
            continue
        out.append({'debut': debut, 'debut_utc': debut_utc.isoformat(),
                    'horodatage': {'nature': 'debut_planifie', 'source': 'oddspapi.commence_time',
                                   'fuseau': 'UTC', 'interpole': False, 'fin_utc': None},
                    'home': h, 'away': a, 'tournoi': m.get('sport_title') or ''})
    out.sort(key=lambda x: x['debut'])
    couverture = {'n_source': len(L), 'horodatages_valides': valides,
                  'couverture_pct': round(100 * valides / len(L), 2) if L else None,
                  'matchs_dans_fenetre': len(out), 'horodatages_invalides': invalides,
                  'nature': 'débuts planifiés avec fuseau, pas heures de fin constatées',
                  'repli': 'aucun : un match sans horodatage valide est exclu des pronostics à venir',
                  'interpolation': False, 'dates_de_fin_inventees': False}
    return (out, couverture) if avec_couverture else out


def construire(racine, maintenant=None):
    maintenant = maintenant or dt.datetime.utcnow()
    etat = E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8')))
    elo = E.Elo.importer(etat['joueurs'], etat.get('options'))
    # 29/10/2026 — modèle fantôme : l'Elo d'avant les changements du 28-29/10 (sans ITF), pour comparer en direct
    try:
        ref_etat = E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat_reference.json'), encoding='utf-8')))
        elo_ref = E.Elo.importer(ref_etat['joueurs'], ref_etat.get('options'))
    except (OSError, ValueError, KeyError):
        ref_etat, elo_ref = None, None
    try:                            # 29/10/2026 : fantôme propre aux résultats ITF femmes
        fem_etat = E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat_sans_itf_femmes.json'), encoding='utf-8')))
        elo_fem = E.Elo.importer(fem_etat['joueurs'], fem_etat.get('options'))
    except (OSError, ValueError, KeyError):
        fem_etat, elo_fem = None, None
    global ACTIVITE, PROGRAMME, FORME_SERVICE, ECHANGES
    try:                            # 30/10/2026 : longueur des échanges (affichage seul ; /tmp/mcp cloné par le workflow)
        import echanges_joueur as EJ
        ECHANGES = EJ.depuis(os.environ.get('MCP_DIR', '/tmp/mcp'))
    except Exception as e_:  # noqa: BLE001
        print(f"::warning::longueur des échanges non chargée : {type(e_).__name__}: {e_}")
        ECHANGES = None
    PROGRAMME = charger_programme(racine)
    try:
        fiches_ = FE.lire(racine)
    except Exception:  # noqa: BLE001
        fiches_ = None
    try:                            # 29/10/2026 : service / retour du moment (information + fantôme)
        import forme_service as FSV
        FORME_SERVICE = FSV.FormeService.depuis(racine, fiches_)
    except Exception as e_:  # noqa: BLE001
        print(f"::warning::forme du service non chargée : {type(e_).__name__}: {e_}")
        FORME_SERVICE = None
    try:
        import activite as ACT
        ACTIVITE = ACT.Activite.depuis(racine, fiches_)
    except Exception as e_:  # noqa: BLE001
        print(f"::warning::activité des joueurs non chargée : {type(e_).__name__}: {e_}")
        ACTIVITE = None
    surf = etat.get('surfaces_tournois') or {}
    S = Styles(os.path.join(racine, 'simulateur', 'notes_joueurs.json'))
    PR = charger_profils(racine)
    global REGLAGES, CHOIX, FACTEURS, CONTEXTE, COMBINAISON, REGLAGE_SIM
    REGLAGES = charger_reglages(racine)
    CHOIX = charger_choix(racine)
    COMBINAISON = charger_combinaison(racine)
    AJUSTEMENTS.clear()
    AJUSTEMENTS.update(charger_ajustements(racine))
    global CLASSEMENTS
    try:
        import classements as CLS
        CLASSEMENTS = CLS.charger(None, racine)
    except Exception:  # noqa: BLE001 — sans classement, la correction ne s'applique pas
        CLASSEMENTS = None
    REGLAGE_SIM = charger_reglage_simulation(racine)
    FACTEURS, CONTEXTE = charger_facteurs(racine)
    global FORME_SCORES
    FORME_SCORES = charger_forme_scores(racine)
    global SIGMA_CIRCUIT
    SIGMA_CIRCUIT = charger_sigma_circuit(racine)
    venir, couverture_horodatages = matchs_a_venir(racine, maintenant, avec_couverture=True)
    if os.environ.get('PRONOSTICS_MAX'):            # 29/10/2026 : test de chaîne courte (appliquer_paquet.yml) seulement
        venir = venir[:int(os.environ['PRONOSTICS_MAX'])]
    # Un joueur = un classement : alias du dernier calcul, puis noms nouveaux reliés au joueur connu.
    alias = dict(etat.get('alias') or {})
    alias.update(E.unifier({k: v.get('nom', k) for k, v in etat['joueurs'].items()},
                           [n for x in venir for n in (x['home'], x['away'])]))
    cle_c = lambda n: alias.get(E.cle(n), E.cle(n))
    noms = [v.get('nom', k) for k, v in etat['joueurs'].items()] + [n for x in venir for n in (x['home'], x['away'])]
    ambigus = {c['cle'] for c in E.collisions_identite(noms)}
    out, rejets = [], []
    for x in venir:
        h, a = cle_c(x['home']), cle_c(x['away'])
        if not h or not a or h == a or h in ambigus or a in ambigus:
            rejets.append({'home': x['home'], 'away': x['away'], 'raison': 'identite_ambigue'})
            continue
        c = circuit(x['tournoi'])
        if etat.get('depart_bas') and c in ('CH', 'ITF'):
            elo.presenter(h, etat['depart_bas'])
            elo.presenter(a, etat['depart_bas'])
        s = NR.surface_de(x['tournoi'], surf)
        if s not in E.SURFACES:
            rejets.append({'home': x['home'], 'away': x['away'], 'tournoi': x['tournoi'], 'raison': 'surface_inconnue'})
            continue
        sg = 3 if NR.cinq_sets(x['tournoi']) else 2
        pa0, pb0 = S.service(h, a, c, s)
        stats = pronostic(elo.proba(h, a, s), c, sg, pa0, pb0)
        uid = f"{x['debut'].date()}_{NR.slug(x['home'])}_{NR.slug(x['away'])}"
        simulation = combinaison = direct = forme_ctl = fsv_ctl = None
        fsv = None
        if FORME_SERVICE is not None:
            try:
                fsv = [FORME_SERVICE.variables(k_, x['debut'], s) for k_ in (h, a)]
            except Exception as e_:  # noqa: BLE001 — information seule, ne bloque jamais un pronostic
                print(f"::warning::forme du service non calculée ({h}–{a}) : {type(e_).__name__}: {e_}")
                fsv = None
        if PR is not None:
            # 22/10/2026 — SIMULATION PURE : le match joué SIMULATIONS fois avec les seuls taux des deux
            # joueurs (1re balle, aces, doubles fautes, points gagnés derrière la 1re et la 2e, retour),
            # sans Elo ni cote : c'est la simulation qui dit qui gagne.
            fct = facteurs_du_match(h, a, x['tournoi'], x['debut'], getattr(PR, 'ajuste', None))
            r = match_simule(PR, h, a, c, s, sg, None, f"{uid}|simulation", fct)
            exact_simulation = distribution_exacte_du_match(PR, h, a, c, s, sg, r['victoire_A'], fct, pure=True)
            simulation = {'p_home': r['victoire_A'], 'sets': r['sets'],
                          'scores_probables': exact_simulation['scores'], 'scores_exact': exact_simulation,
                          'remontee': {'home': r['remontee'][0], 'away': r['remontee'][1]}, 'set1_home': r['set1_A'],
                          'jeux_moyen': r['jeux']['moy'], 'tiebreak': r['tiebreak'], 'match_simule': r}
            if fct:
                cH, cA, _, _ = composantes_du_match(PR, h, a, c, s, pure=True)
                simulation['facteurs'] = impact_facteurs(cH, cA, sg, fct)
            if COMBINAISON:
                # 22/10/2026 — SIMULATION + ELO : le % de la simulation (limite exacte) mélangé à celui de l'Elo,
                # poids appris sur 2024 et adoptés parce qu'ils trouvent mieux le vainqueur en 2025–2026 ; le
                # match est ensuite joué avec les statistiques des deux joueurs, à ce niveau.
                cH, cA = avec_facteurs(*composantes_du_match(PR, h, a, c, s, pure=True)[:2], fct)
                p_sim = MS.victoire_pure(cH, cA, sg, sigma_sim())
                p_c = MS.melange_contexte(COMBINAISON, MS.contexte_match(s, c, 2 * sg - 1), stats['p_home'], p_sim)
                p_c = MS.calibrer(p_c, COMBINAISON.get('calibration'))     # excès de confiance (si adopté)
                sit = situations_du_match(h, a, x['tournoi'], x['debut'], s)
                tr_ = tour_du_match(h, a, x['debut'])            # 29/10/2026 : tour du tableau (programme TennisApi)
                if tr_:
                    import entrainement_progressif as EP_t
                    sit['tour'] = EP_t.variables_tour(tr_)
                if ACTIVITE is not None:                        # 29/10/2026 : (Δ tendance, Δ volume) vus de home
                    import activite as ACT
                    sit['activite'] = ACT.ecarts(ACTIVITE.variables(h, x['debut']), ACTIVITE.variables(a, x['debut']))
                if CLASSEMENTS is not None:                     # 23/10/2026 : classement du joueur peu connu
                    import classements as CLS
                    sit['classement'] = tuple(CLS.niveau_inconnu(CLASSEMENTS.rang_au(j, x['debut']), elo.matchs(j)) for j in (h, a))
                    # 28/10/2026 : classement relatif quand un joueur est peu connu (entrainement_progressif.rang_relatif)
                    import entrainement_progressif as EP_
                    rh_, ra_ = CLASSEMENTS.rang_au(h, x['debut']), CLASSEMENTS.rang_au(a, x['debut'])
                    # 30/10/2026 : points ATP/WTA des deux joueurs (candidat des arbres en production par décision)
                    pts_ = CLS.ecart_points(CLASSEMENTS.points_au(h, x['debut']), CLASSEMENTS.points_au(a, x['debut']))
                    if pts_ is not None:
                        sit['points'] = pts_
                    if rh_ and ra_:
                        w_rel = max(0.0, 1 - elo.matchs(h) / EP_.SEUIL_RANG_RELATIF, 1 - elo.matchs(a) / EP_.SEUIL_RANG_RELATIF)
                        sit['rangs'] = (rh_, ra_)
                        sit['classement_relatif'] = (-w_rel * math.log(rh_), -w_rel * math.log(ra_))
                p_c = ajuster_combinaison(p_c, c, stats['p_home'], p_sim, elo.matchs(h), elo.matchs(a), sit, s, 2 * sg - 1)
                combinaison = dict(pronostic(p_c, c, sg, MS.p_service(cH), MS.p_service(cA)),
                                   p_simulation=round(p_sim, 4), p_elo=stats['p_home'])
                if fsv and (fsv[0] or fsv[1]):
                    try:
                        fsv_ctl = controle_forme_service(cH, cA, fsv[0], fsv[1], c, s, sg, stats['p_home'], p_sim,
                                                         elo.matchs(h), elo.matchs(a), sit)
                    except Exception as e_:  # noqa: BLE001 — le fantôme ne doit jamais bloquer un pronostic
                        print(f"::warning::fantôme forme du service non calculé ({h}–{a}) : {type(e_).__name__}: {e_}")
            # 22/10/2026 — EN DIRECT (direct.py, Lab) : points de service des deux joueurs pour la version
            # principale (simulation + Elo si adoptée, sinon simulation pure), avant toute forme du jour.
            cH0, cA0 = avec_facteurs(*composantes_du_match(PR, h, a, c, s, pure=not combinaison)[:2], fct)
            pa_s, pb_s = MS.p_service(cH0), MS.p_service(cA0)
            if combinaison:
                pa_s, pb_s = MS.ancrer_rapide(pa_s, pb_s, combinaison['p_home'], sg, sigma_de(c))
            if combinaison:
                try:
                    forme_ctl = controle_forme(PR, h, a, c, s, sg, combinaison['p_home'], fct)
                except Exception as e_:  # noqa: BLE001 — le contrôle ne doit jamais bloquer un pronostic
                    print(f"::warning::fantôme de la forme du jour non calculé ({h}–{a}) : {type(e_).__name__}: {e_}")
            direct = {'a': round(pa_s, 5), 'b': round(pb_s, 5), 'sigma': sigma_de(c) if combinaison else sigma_sim(), 'sets_gagnants': sg,
                      'tb_final': 10 if sg == 3 else 7, 'version': 'combinaison' if combinaison else 'simulation'}
            for nom_v, v in (('stats', stats), ('combinaison', combinaison)):
                if v:
                    v['match_simule'] = match_simule(PR, h, a, c, s, sg, v['p_home'], f"{uid}|{nom_v}", fct,
                                                    controler_stabilite=(nom_v == 'combinaison'))
                    v['scores_exact'] = distribution_exacte_du_match(PR, h, a, c, s, sg, v['p_home'], fct)
                    v['scores_probables'] = v['scores_exact']['scores']
                    if v['scores_exact'].get('forme_profils'):          # sets cohérents avec les scores inclinés
                        sets = {}
                        for row in v['scores_exact']['distribution']:
                            k = f"{sum(x > y for x, y in row['score'])}-{sum(y > x for x, y in row['score'])}"
                            sets[k] = sets.get(k, 0.0) + row['probabilite']
                        ordre = ('2-0', '2-1', '1-2', '0-2')
                        v['sets'] = {k: round(sets.get(k, 0.0), 4) for k in ordre}
        out.append({'uid': uid,
                    'debut': x['debut'].isoformat(timespec='minutes'), 'debut_utc': x['debut_utc'],
                    'horodatage': x['horodatage'], 'tournoi': x['tournoi'], 'circuit': c,
                    'surface': s, 'meilleur_des': 2 * sg - 1, 'home': x['home'], 'away': x['away'],
                    'cles': [h, a], 'matchs_joues': [elo.matchs(h), elo.matchs(a)], 'style_connu': [S.connu(h), S.connu(a)],
                    'combinaison': combinaison, 'simulation': simulation, 'stats': stats, 'direct': direct,
                    'activite': ([ACTIVITE.variables(k_, x['debut'], relatif=True) for k_ in (h, a)] if ACTIVITE is not None else None),
                    'forme_service': fsv if fsv and (fsv[0] or fsv[1]) else None,
                    'echanges': _echanges(h, a, x['debut']),
                    'controle': _avec_service(_avec_forme(controle_fantome(elo, elo_ref, ref_etat, etat, h, a, c, s, elo_fem, fem_etat),
                                                          forme_ctl), fsv_ctl)})
    doc = {'genere_le': maintenant.isoformat(timespec='seconds') + 'Z', 'elo_au': etat.get('dernier_match'),
            'horizon_h': HORIZON_H, 'sigma': SIGMA, 'simulations': SIMULATIONS if PR is not None else 0,
            'qualite_horodatages': couverture_horodatages,
            'profils_au': PR.jour_export.isoformat() if PR is not None else None,
            'facteurs_adoptes': (FACTEURS or {}).get('adoptes') or [], 'combinaison': COMBINAISON,
            'reglage_simulation': REGLAGE_SIM, 'rejets_entrees': rejets,
            'noeuds_forme': [[round(z, 6), round(w, 8)] for z, w in zip(M._Z, M._W)], 'matchs': out}
    import charting_atp_wta as CAW
    try:
        doc['suivi_charting_atp_wta'] = CAW.journaliser(racine, doc, CONTEXTE)
    except FileNotFoundError:
        # Checkout de test ou ancien paquet : le suivi optionnel ne bloque pas le champion.
        doc['suivi_charting_atp_wta'] = {'schema': CAW.SCHEMA, 'statut': 'modele_non_installe',
                                         'nouveaux_figes': 0, 'activation': False}
    import styles_ajustes as SA
    try:
        doc['suivi_styles_ajustes'] = SA.journaliser(racine, doc)
    except FileNotFoundError:
        doc['suivi_styles_ajustes'] = {'schema': SA.SCHEMA, 'statut': 'modele_non_installe',
                                       'nouveaux_figes': 0, 'activation': False}
    import styles_global as SG
    try:
        doc['suivi_styles_global'] = SG.journaliser(racine, doc)
    except FileNotFoundError:
        doc['suivi_styles_global'] = {'schema': SG.SCHEMA, 'statut': 'modele_non_installe',
                                      'nouveaux_figes': 0, 'activation': False}
    import statistiques_styles as SS
    try:
        doc['suivi_statistiques_styles_dur'] = SS.journaliser(racine, doc)
    except FileNotFoundError:
        doc['suivi_statistiques_styles_dur'] = {'schema': SS.SCHEMA, 'statut': 'modele_non_installe',
                                                'nouveaux_figes': 0, 'activation': False}
    return doc


SUIVI_STATS = ('aces', 'doubles_fautes', 'premiere_pct', 'gagnes_1re_pct', 'gagnes_2e_pct', 'breaks', 'jeux')


def feuille_prevue(m):
    """Feuille de la MÊME variante que le pronostic public, jamais celle d'une autre version."""
    v = next((m[k] for k in VERSIONS if m.get(k) and m[k].get('match_simule')), None)
    S = (v or {}).get('match_simule')
    if not S:
        return None
    out = {'version': next(k for k in VERSIONS if m.get(k) is v)}
    for k in SUIVI_STATS:
        a, b = S['feuille'][0].get(k), S['feuille'][1].get(k)
        if a and b:
            out[k] = [[a['moy'], a['p10'], a['p90']], [b['moy'], b['p10'], b['p90']]]
    if S.get('jeux'):
        out['total_jeux'] = [S['jeux']['moy'], S['jeux']['p10'], S['jeux']['p90']]
    return out


def suivi_feuilles(racine, lignes):
    """Match simulé contre la vraie feuille (feuilles/ collectées) : par statistique, prévu moyen,
    réel moyen, écart moyen absolu et part des réels dans la fourchette à 80 % (bornes incluses)."""
    avec = [r for r in lignes if r.get('feuille')]
    if not avec:
        return {'n': 0}
    jours = sorted(r['debut'][:10] for r in avec)
    debut = (dt.date.fromisoformat(jours[0]) - dt.timedelta(days=1)).isoformat()
    idx = FE.Index(FE.lire(racine, depuis=debut))
    acc = {k: [] for k in SUIVI_STATS + ('total_jeux',)}
    n = 0
    for r in avec:
        fi, inv = idx.trouver(r['debut'][:10], r['home'], r['away'])
        if not fi or str((fi.get('statut') or {}).get('texte') or '').lower() != 'ended':
            continue
        reel = FE.feuille_reelle(fi, inv)
        if not reel:
            continue
        (fh, fa), tot = reel
        n += 1
        for k in SUIVI_STATS:
            if k in r['feuille']:
                for i, f in ((0, fh), (1, fa)):
                    moy, lo, hi = r['feuille'][k][i]
                    acc[k].append((moy, lo, hi, f[k]))
        if 'total_jeux' in r['feuille']:
            moy, lo, hi = r['feuille']['total_jeux']
            acc['total_jeux'].append((moy, lo, hi, tot))
    out = {'n': n, 'stats': {}}
    for k, L in acc.items():
        if L:
            out['stats'][k] = {'n': len(L), 'prevu': round(sum(x[0] for x in L) / len(L), 2),
                               'reel': round(sum(x[3] for x in L) / len(L), 2),
                               'ecart_moyen': round(sum(abs(x[0] - x[3]) for x in L) / len(L), 2),
                               'dans_fourchette_pct': round(100 * sum(x[1] <= x[3] <= x[2] for x in L) / len(L), 1)}
    return out


def resume_version(v):
    """Ce qu'on garde d'une version pour l'analyse : %, sets, 3 scores, jeux, tie-break, 1er set."""
    if not v:
        return None
    out = {k: v.get(k) for k in ('p_home', 'sets', 'scores_probables', 'jeux_moyen', 'tiebreak', 'set1_home') if v.get(k) is not None}
    if v.get('scores_exact'):
        out['scores_source'] = 'exact'
        out['scores_exact_controle'] = v['scores_exact']['controle']
    if v.get('facteurs'):
        out['facteurs'] = v['facteurs']
    return out


def instantane(doc, m):
    return {'passage': doc['genere_le'], 'uid': m['uid'], 'debut': m['debut'],
            'debut_utc': m.get('debut_utc'), 'horodatage': m.get('horodatage'), 'home': m['home'], 'away': m['away'],
            'tournoi': m['tournoi'], 'circuit': m['circuit'], 'surface': m['surface'], 'meilleur_des': m['meilleur_des'],
            'pin_cotes': m.get('pin_cotes'), 'matchs_joues': m.get('matchs_joues'),
            'modele': {'facteurs': doc.get('facteurs_adoptes') or [], 'combinaison': doc.get('combinaison'),
                       'profils_au': doc.get('profils_au'), 'elo_au': doc.get('elo_au')},
            **{k: resume_version(m.get(k)) for k in VERSIONS}, 'direct': m.get('direct')}


def enregistrer_instantanes(racine, doc):
    """Une ligne par match et par passage, dans simulateur/journal_pronostics/AAAA-MM-JJ.jsonl.gz
    (jour UTC du passage ; fichier gzip complété à chaque passage)."""
    import gzip
    dossier = os.path.join(racine, INSTANTANES)
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, doc['genere_le'][:10] + '.jsonl.gz')
    with gzip.open(chemin, 'at', encoding='utf-8') as f:
        for m in doc['matchs']:
            f.write(json.dumps(instantane(doc, m), ensure_ascii=False, separators=(',', ':')) + '\n')
    return len(doc['matchs'])


def lire_instantanes(racine, depuis=None):
    """{uid: [instantanés dans l'ordre des passages]}."""
    import glob
    import gzip
    out = {}
    for p in sorted(glob.glob(os.path.join(racine, INSTANTANES, '*.jsonl.gz'))):
        if depuis and os.path.basename(p)[:10] < depuis:
            continue
        try:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                for l in f:
                    try:
                        r = json.loads(l)
                    except ValueError:
                        continue
                    out.setdefault(r['uid'], []).append(r)
        except (OSError, EOFError):
            continue
    for L in out.values():
        L.sort(key=lambda r: r['passage'])
    return out


def journaliser(racine, doc):
    chemin = os.path.join(racine, LOG)
    deja = set()
    try:
        with open(chemin, encoding='utf-8') as f:
            for l in f:
                try:
                    deja.add(json.loads(l)['uid'])
                except (ValueError, KeyError):
                    continue
    except OSError:
        pass
    n = 0
    with open(chemin, 'a', encoding='utf-8') as f:
        for m in doc['matchs']:
            if m['uid'] in deja:
                continue
            f.write(json.dumps({'uid': m['uid'], 'pronostique_le': doc['genere_le'], 'debut': m['debut'],
                                'debut_utc': m.get('debut_utc'), 'horodatage': m.get('horodatage'),
                                'home': m['home'], 'away': m['away'], 'tournoi': m['tournoi'], 'circuit': m['circuit'],
                                'stats': {'p_home': m['stats']['p_home'], 'sets': m['stats']['sets']},
                                'simulation': ({'p_home': m['simulation']['p_home'], 'sets': m['simulation']['sets']}
                                               if m.get('simulation') else None),
                                'combinaison': ({'p_home': m['combinaison']['p_home'], 'sets': m['combinaison']['sets']}
                                                if m.get('combinaison') else None),
                                'detail': {k: resume_version(m.get(k)) for k in VERSIONS},
                                'pin_cotes': m.get('pin_cotes'), 'surface': m.get('surface'),
                                'meilleur_des': m.get('meilleur_des'), 'matchs_joues': m.get('matchs_joues'),
                                'fiabilite': m.get('fiabilite'),
                                'profil_contexte': (m.get('match_simule') or {}).get('profil_contexte'),
                                'stabilite_score': (m.get('match_simule') or {}).get('stabilite_score'),
                                'feuille': feuille_prevue(m)},
                               ensure_ascii=False) + '\n')
            n += 1
    return n


def bilan(racine, maintenant=None):
    """Taux de vainqueurs devinés sur le journal (matchs joués, résultat connu)."""
    maintenant = maintenant or dt.datetime.utcnow()
    try:
        sr = json.load(open(os.path.join(racine, 'set_results.json'), encoding='utf-8'))
    except (OSError, ValueError):
        sr = {}
    vus, L, journal = set(), [], []
    try:
        lignes = open(os.path.join(racine, LOG), encoding='utf-8').read().splitlines()
    except OSError:
        lignes = []
    try:
        idx_b = FE.Index(FE.lire(racine, depuis=(maintenant - dt.timedelta(days=200)).date().isoformat()))
    except Exception:  # noqa: BLE001 — sans feuilles, on garde tous les matchs
        idx_b = None
    for l in lignes:
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if r['uid'] in vus:
            continue
        vus.add(r['uid'])
        journal.append(r)
        d0 = dt.date.fromisoformat(r['debut'][:10])
        res, sens = NR.resultat(sr, d0, r['home'], r['away'])
        if not res:
            continue
        if idx_b is not None and interruption(idx_b.trouver(r['debut'][:10], r['home'], r['away'])[0]):
            continue                                          # abandon ou forfait : ne juge pas le modèle
        o = (lambda v: v) if sens == 1 else (lambda v: {'home': 'away', 'away': 'home'}.get(v))
        g, s1, s2 = o(res.get('match')), o(res.get('set1')), o(res.get('set2'))
        sets = None
        if s1 in ('home', 'away') and s2 in ('home', 'away') and not (s1 == s2 and g != s1) and len(r['stats']['sets']) == 4:
            sets = ('2-0' if g == 'home' else '0-2') if s1 == s2 else ('2-1' if g == 'home' else '1-2')
        L.append(dict(r, gagnant=g, sets_reel=sets))

    def bloc(items, cle):
        it = [x for x in items if x.get(cle)]
        n = len(it)
        if not n:
            return {'n': 0}
        ok = sum(1.0 if (x[cle]['p_home'] > 0.5) == (x['gagnant'] == 'home') and x[cle]['p_home'] != 0.5 else
                 (0.5 if x[cle]['p_home'] == 0.5 else 0.0) for x in it)
        s = [x for x in it if x['sets_reel']]
        sj = sum(max(x[cle]['sets'], key=x[cle]['sets'].get) == x['sets_reel'] for x in s)
        ll = sum(-math.log(min(max(x[cle]['p_home'] if x['gagnant'] == 'home' else 1 - x[cle]['p_home'], 1e-6), 1))
                 for x in it) / n
        return {'n': n, 'reussite_pct': round(100 * ok / n, 1), 'log_loss': round(ll, 4),
                'score_sets_juste_pct': round(100 * sj / len(s), 1) if s else None, 'n_sets': len(s)}

    def calibration(items, cle):
        """Point 9 : quand le favori est annoncé à 60 %, gagne-t-il 6 fois sur 10 ? (tranches de 10 points)"""
        out = []
        for lo in range(50, 100, 10):
            g = []
            for x in items:
                v = x.get(cle)
                if not v or x['gagnant'] not in ('home', 'away'):
                    continue
                pf = max(v['p_home'], 1 - v['p_home'])
                if lo <= 100 * pf < lo + 10 or (lo == 90 and pf >= 1):
                    g.append((pf, (v['p_home'] >= 0.5) == (x['gagnant'] == 'home')))
            if g:
                out.append({'tranche': f"{lo}–{lo + 10} %", 'n': len(g), 'prevu': round(100 * sum(p for p, _ in g) / len(g), 1),
                            'reel': round(100 * sum(w for _, w in g) / len(g), 1)})
        return out
    VERS = (('combinaison', 'combinaison'), ('simulation', 'simulation'), ('stats_seules', 'stats'))
    depuis7 = (maintenant - dt.timedelta(days=7)).date().isoformat()
    L7 = [x for x in L if x['debut'] >= depuis7]
    doc = {'genere_le': maintenant.isoformat(timespec='seconds') + 'Z', 'pronostiques': len(vus), 'joues_avec_resultat': len(L),
           'tous': {k: bloc(L, c) for k, c in VERS},
           '7_derniers_jours': {k: bloc(L7, c) for k, c in VERS},
           'calibration': {k: calibration(L, c) for k, c in VERS},
           'par_circuit': {ci: {k: bloc([x for x in L if x.get('circuit') == ci], c) for k, c in VERS}
                           for ci in ('ATP', 'WTA', 'CH', 'ITF') if any(x.get('circuit') == ci for x in L)},
           'derniers': [{'debut': x['debut'], 'home': x['home'], 'away': x['away'], 'gagnant': x['gagnant'],
                         'combinaison': (x.get('combinaison') or {}).get('p_home'),
                         'simulation': (x.get('simulation') or {}).get('p_home'),
                         'stats': x['stats']['p_home']}
                        for x in sorted(L, key=lambda x: x['debut'])[-30:]],
           'match_simule_contre_feuille': suivi_feuilles(racine, journal)}
    return doc


def score_reel(fi, inverse):
    """« 6-4 3-6 7-6 » du point de vue home du pronostic, depuis une feuille TennisApi ; None sinon."""
    a, b = (fi.get('score_home') or {}).get('sets') or [], (fi.get('score_away') or {}).get('sets') or []
    if not a or len(a) != len(b):
        return None
    if inverse:
        a, b = b, a
    return ' '.join(f"{x}-{y}" for x, y in zip(a, b))


def juger(v, gagnant, sets, score, jeux):
    """Ce qui était juste dans une version du pronostic."""
    if not v or v.get('p_home') is None:
        return None
    p = v['p_home']
    out = {'p_home': p, 'proba_du_vainqueur': round(p if gagnant == 'home' else 1 - p, 4),
           'vainqueur_juste': None if p == 0.5 else ((p > 0.5) == (gagnant == 'home'))}
    if sets and v.get('sets'):
        out['sets_prevus'] = max(v['sets'], key=v['sets'].get)
        out['sets_justes'] = out['sets_prevus'] == sets
        out['proba_des_sets_reels'] = v['sets'].get(sets)
    sc = [x[0] for x in v.get('scores_probables') or []]
    if sc:
        out['score_prevu'] = sc[0]
        if score:
            out['score_juste'] = sc[0] == score
            out['rang_du_score_reel'] = sc.index(score) + 1 if score in sc else None
    if jeux is not None and v.get('jeux_moyen') is not None:
        out['jeux_prevus'], out['ecart_jeux'] = v['jeux_moyen'], round(jeux - v['jeux_moyen'], 1)
    return out


# ------------------------------------------------------------------ La feuille entière contre les simulations
DIAG_STATS = ('premiere_pct', 'gagnes_1re_pct', 'gagnes_2e_pct', 'aces', 'doubles_fautes', 'breaks', 'jeux')
SERVICE_STATS = ('premiere_pct', 'gagnes_1re_pct', 'gagnes_2e_pct')
DIAG_LIB = {'premiere_pct': '% de 1re balle', 'gagnes_1re_pct': 'points gagnés derrière la 1re',
            'gagnes_2e_pct': 'points gagnés derrière la 2e', 'aces': 'aces', 'doubles_fautes': 'doubles fautes',
            'breaks': 'breaks réussis', 'jeux': 'jeux gagnés'}


def diagnostic(prevue, reelle, gagnant, p_home_sim):
    """Chaque statistique de la vraie feuille placée dans la distribution des simulations (journal, 1re
    prédiction) : prévu (moyenne), fourchette à 80 %, réel, écart réduit z = (réel − prévu) / écart type des
    simulations. Puis CE QUI A FAIT LA DIFFÉRENCE : la statistique de service où un joueur s'est le plus écarté
    de sa simulation dans le sens du vrai résultat (z orienté ≥ 1)."""
    if not prevue or not reelle or gagnant not in ('home', 'away'):
        return None
    st = {}
    for k in DIAG_STATS:
        if k not in prevue:
            continue
        for i, cote in enumerate(('home', 'away')):
            v = reelle[i].get(k)
            if v is None:
                continue
            moy, lo, hi = prevue[k][i]
            et = max((hi - lo) / 2.563, 1e-6)                  # p10–p90 d'une loi normale = 2,563 écarts types
            st.setdefault(k, {})[cote] = {'prevu': round(moy, 1), 'bas': round(lo, 1), 'haut': round(hi, 1),
                                          'reel': round(v, 1), 'z': round((v - moy) / et, 2), 'dans': lo <= v <= hi}
    if not st:
        return None
    cases = [x for d in st.values() for x in d.values()]
    out = {'stats': st, 'dans_fourchette_pct': round(100 * sum(x['dans'] for x in cases) / len(cases), 1),
           'vainqueur_juste': ((p_home_sim >= 0.5) == (gagnant == 'home')) if p_home_sim is not None else None}
    cand = []
    for k in SERVICE_STATS:
        for cote, x in (st.get(k) or {}).items():
            cand.append(((x['z'] if cote == gagnant else -x['z']), k, cote))
    cand.sort(reverse=True)
    if cand and cand[0][0] >= 1:
        z, k, cote = cand[0]
        out['decisif'] = {'stat': k, 'joueur': cote, 'z': round(z, 2), 'prevu': st[k][cote]['prevu'], 'reel': st[k][cote]['reel']}
    return out


def biais(R, min_n=30):
    """Là où la simulation a bon et pas bon, sur tous les matchs joués avec leur feuille : par statistique, écart
    moyen (réel − prévu) et part des réels dans la fourchette, pour le FAVORI et l'OUTSIDER annoncés par la
    simulation, par circuit ; et, quand le vainqueur est faux, la statistique qui a fait la différence.
    Moins de 30 matchs : affiché, mais signalé « ne pas conclure »."""
    D = [m for m in R if m.get('diagnostic') and not (m.get('reel') or {}).get('interrompu')]
    if not D:
        return {'n': 0}

    def bloc(G):
        out = {}
        for k in DIAG_STATS:
            for role in ('favori', 'outsider'):
                xs = []
                for m in G:
                    ph = m.get('p_affiche', m.get('p_simulation'))
                    if ph is None:
                        continue
                    cote = ('home' if ph >= 0.5 else 'away') if role == 'favori' else ('away' if ph >= 0.5 else 'home')
                    x = (m['diagnostic']['stats'].get(k) or {}).get(cote)
                    if x:
                        xs.append(x)
                if xs:
                    out.setdefault(k, {})[role] = {'n': len(xs), 'ecart_moyen': round(sum(x['reel'] - x['prevu'] for x in xs) / len(xs), 2),
                                                    'z_moyen': round(sum(x['z'] for x in xs) / len(xs), 2),
                                                    'dans_fourchette_pct': round(100 * sum(x['dans'] for x in xs) / len(xs), 1)}
        return out
    faux = [m for m in D if m['diagnostic'].get('vainqueur_juste') is False]
    dec = {}
    for m in faux:
        k = (m['diagnostic'].get('decisif') or {}).get('stat') or 'aucune stat nette'
        dec[k] = dec.get(k, 0) + 1
    return {'n': len(D), 'conclure': len(D) >= min_n, 'tous': bloc(D),
            'par_circuit': {c: bloc([m for m in D if m.get('circuit') == c]) for c in ('ATP', 'WTA', 'CH')
                            if any(m.get('circuit') == c for m in D)},
            'erreurs': {'n': len(faux), 'stat_decisive': dict(sorted(dec.items(), key=lambda kv: -kv[1]))}}


def interruption(fi):
    """'abandon' (abandon, disqualification), 'forfait' (walkover) ou None, d'après la feuille TennisApi.
    22/10/2026 : ces matchs ne jugent pas le modèle (un abandon à 3-1 n'est pas une erreur de pronostic)."""
    txt = str(((fi or {}).get('statut') or {}).get('texte') or '').lower()
    return 'abandon' if txt in ('retired', 'defaulted') else 'forfait' if txt == 'walkover' else None


def resoudre(racine, maintenant=None):
    """Chaque match du journal dont le résultat est connu : 1re prédiction, dernière avant le match,
    résultat réel (vainqueur, sets, score en jeux, feuille de stats), et le jugement de chaque version."""
    maintenant = maintenant or dt.datetime.utcnow()
    try:
        sr = json.load(open(os.path.join(racine, 'set_results.json'), encoding='utf-8'))
    except (OSError, ValueError):
        sr = {}
    journal, vus = [], set()
    try:
        for l in open(os.path.join(racine, LOG), encoding='utf-8'):
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if r['uid'] not in vus:
                vus.add(r['uid'])
                journal.append(r)
    except OSError:
        pass
    passes = [r for r in journal if dt.datetime.fromisoformat(r['debut']) < maintenant]
    if not passes:
        return []
    debut_min = (dt.date.fromisoformat(min(r['debut'] for r in passes)[:10]) - dt.timedelta(days=1)).isoformat()
    idx = FE.Index(FE.lire(racine, depuis=debut_min))
    inst = lire_instantanes(racine, depuis=debut_min)
    out = []
    for r in passes:
        d0 = dt.date.fromisoformat(r['debut'][:10])
        res, sens = NR.resultat(sr, d0, r['home'], r['away'])
        fi, inv = idx.trouver(r['debut'][:10], r['home'], r['away'])
        interrompu = interruption(fi)
        if fi is not None and str((fi.get('statut') or {}).get('texte') or '').lower() != 'ended':
            fi = None
        gagnant = sets = None
        if res:
            o = (lambda v: v) if sens == 1 else (lambda v: {'home': 'away', 'away': 'home'}.get(v))
            gagnant = o(res.get('match'))
            s1, s2 = o(res.get('set1')), o(res.get('set2'))
            if r.get('meilleur_des', 3) == 3 and s1 in ('home', 'away') and s2 in ('home', 'away') and not (s1 == s2 and gagnant != s1):
                sets = ('2-0' if gagnant == 'home' else '0-2') if s1 == s2 else ('2-1' if gagnant == 'home' else '1-2')
        score = score_reel(fi, inv) if fi else None
        if gagnant not in ('home', 'away') and fi and fi.get('vainqueur') in (1, 2):
            gagnant = 'home' if (fi['vainqueur'] == 1) != inv else 'away'
        if gagnant not in ('home', 'away'):
            continue
        score_brut = score
        if score:
            g_score = NR.gagnant_score(score, r.get('meilleur_des', 3))
            if g_score == gagnant:
                ns = [tuple(int(v) for v in x.split('-')) for x in score.split()]
                sets = f"{sum(a > b for a, b in ns)}-{sum(b > a for a, b in ns)}"
            else:
                score = None                     # incomplet, impossible ou incohérent : jamais utilisé pour apprendre
        jeux = sum(a + b for a, b in (tuple(int(v) for v in x.split('-')) for x in score.split())) if score else None
        feuille = FE.feuille_reelle(fi, inv) if fi and (not score_brut or score) else None
        avant = [x for x in inst.get(r['uid'], []) if x['passage'][:16] < r['debut'][:16]]
        dernier = avant[-1] if avant else None
        premier = r.get('detail') or {k: r.get(k) for k in VERSIONS}
        p_affiche = next(((premier.get(k) or {}).get('p_home') for k in VERSIONS
                          if (premier.get(k) or {}).get('p_home') is not None), None)
        out.append({'uid': r['uid'], 'debut': r['debut'], 'home': r['home'], 'away': r['away'], 'tournoi': r['tournoi'],
                    'circuit': r.get('circuit'), 'surface': r.get('surface'), 'meilleur_des': r.get('meilleur_des', 3),
                    'pronostique_le': r.get('pronostique_le'), 'matchs_joues': r.get('matchs_joues'),
                    'fiabilite': r.get('fiabilite'), 'profil_contexte': r.get('profil_contexte'),
                    'stabilite_score': r.get('stabilite_score'),
                    'dernier_passage': dernier['passage'] if dernier else None, 'n_passages': len(avant),
                    'reel': {'gagnant': gagnant, 'sets': sets, 'score': score, 'jeux': jeux,
                             'feuille': feuille[0] if feuille else None, 'interrompu': interrompu,
                             'score_invalide': bool(score_brut and not score)},
                    'premier': {k: juger(premier.get(k), gagnant, sets, score, jeux) for k in VERSIONS},
                    'p_simulation': (premier.get('simulation') or {}).get('p_home'), 'p_affiche': p_affiche,
                    'diagnostic': (diagnostic(r.get('feuille'), feuille[0], gagnant, p_affiche)
                                   if feuille and not interrompu else None),
                    'diagnostic_version': (r.get('feuille') or {}).get('version'),
                    'dernier': ({k: juger(dernier.get(k), gagnant, sets, score, jeux) for k in VERSIONS} if dernier else None),
                    'pin_cotes': r.get('pin_cotes')})
    out.sort(key=lambda x: x['debut'], reverse=True)
    return out


def main(argv):
    racine = argv[1] if len(argv) > 1 else os.path.join(ICI, '..')
    doc = construire(racine)
    # Seuls les résultats déjà publiés entrent dans la note : aucun résultat du match à venir,
    # ni résolution nouvellement calculée pendant ce passage, ne peut fuiter dans le pronostic.
    try:
        with open(os.path.join(racine, RESULTATS), encoding='utf-8') as f:
            anciens_resultats = json.load(f)
    except (OSError, ValueError):
        anciens_resultats = {}
    FI.ajouter(doc['matchs'], anciens_resultats)
    os.makedirs(os.path.join(racine, 'Tennis_Edge_Lab', 'live'), exist_ok=True)
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    n = journaliser(racine, doc)
    ni = enregistrer_instantanes(racine, doc)
    b = bilan(racine)
    with open(os.path.join(racine, BILAN), 'w', encoding='utf-8') as f:
        json.dump(b, f, ensure_ascii=False, indent=1)
    R = resoudre(racine)
    with open(os.path.join(racine, RESULTATS), 'w', encoding='utf-8') as f:
        json.dump({'genere_le': doc['genere_le'], 'n': len(R), 'biais': biais(R), 'matchs': R}, f, ensure_ascii=False,
                  separators=(',', ':'))
    print(f"Enregistré : {ni} instantanés ({INSTANTANES}) · {len(R)} matchs joués prédit/réel ({RESULTATS})")
    t = b['tous']
    print(f"Pronostics : {len(doc['matchs'])} matchs dans les {HORIZON_H} h ({n} nouveaux au journal) · "
          f"bilan sur {b['joues_avec_resultat']} matchs joués : stats {t['stats_seules'].get('reussite_pct')} % · "
          f"combinaison {t['combinaison'].get('reussite_pct')} %")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
