#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
entrainement_progressif.py — l'algorithme ré-entraîné SEMAINE APRÈS SEMAINE sur les matchs passés (22/10/2026).

On rejoue la saison des feuilles collectées (depuis juin 2026) comme si l'apprentissage continu avait
tourné dès le début : pour chaque semaine, à partir de la 9e,
  1. les facteurs du match adoptés sont ré-appris sur TOUTES les semaines précédentes seulement ;
  2. la simulation (avec ces facteurs) et l'Elo (tel qu'il était au moment du match) pronostiquent les
     matchs de la semaine — jamais vus ;
  3. le mélange simulation + Elo est ré-appris sur tous les pronostics des semaines précédentes, puis
     appliqué à la semaine.
Chaque pronostic est donc fait avant le match, par un modèle entraîné plusieurs fois, chaque fois sur
le passé seulement. On voit si l'algorithme progresse au fil des semaines.

RÈGLE FIXÉE D'AVANCE : les poids appris ainsi (sur tous les pronostics hors échantillon) remplacent
ceux de l'archive dans les pronostics du jour s'ils trouvent mieux le vainqueur sur les 6 dernières
semaines que les poids de l'archive (même pronostics, log loss plus basse). Les pronostics en direct
(400 matchs, apprentissage_continu.py) restent prioritaires dès qu'ils existent.
"""
import datetime as dt
import math

import elo as E
import match_simule as S

SEMAINES_MIN = 8
MIN_HORS = 600


def part_simulation(w):
    """Part de la simulation dans le mélange, en % (sur les poids en valeur absolue)."""
    a, b = abs(w['simulation']), abs(w['elo'])
    return round(100 * a / (a + b), 1) if a + b else None
FENETRE_JUGE_J = 42


def _ll(L):
    return -sum(math.log(min(max(p, 1e-6), 1 - 1e-6)) for p in L) / len(L) if L else None


def _ok(L):
    return sum(1.0 if p > 0.5 else 0.5 if p == 0.5 else 0.0 for p in L) / len(L) if L else None


def elo_au_moment(M, lignes, options=None, depart_bas=None, experience=None):
    """P(vrai vainqueur) selon l'Elo AVANT chaque match des feuilles (archive rejouée, puis feuilles).
    experience (dict, facultatif) : rempli avec id(ligne) -> (matchs du vrai vainqueur, matchs du perdant)
    AVANT le match — même compte que elo.matchs() dans les pronostics du jour."""
    e = E.Elo(**(options or {}))
    for m in M:
        g, p = E.cle(m['nom_g']), E.cle(m['nom_p'])
        if depart_bas and m['circuit'] in ('CH', 'ITF'):
            e.presenter(g, depart_bas)
            e.presenter(p, depart_bas)
        e.maj(g, p, m['surface'], m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') else None)
    out = []
    for x in sorted(lignes, key=lambda y: y['t']):
        a, b = x['a'], x['b']
        if depart_bas and x['circuit'] == 'CH':
            e.presenter(a, depart_bas)
            e.presenter(b, depart_bas)
        pa = e.proba(a, b, x['surface'])
        out.append((x, pa if x['vainqueur'] == 0 else 1 - pa))
        w, l = (a, b) if x['vainqueur'] == 0 else (b, a)
        if experience is not None:
            experience[id(x)] = (e.matchs(w), e.matchs(l))
        e.maj(w, l, x['surface'])
    return {id(x): p for x, p in out}


def semaine(d, d0):
    return (d - d0).days // 7


# ------------------------------------------------------------------ 22/10/2026 : par circuit, Challenger, nouveaux venus
CIRCUITS = (('ATP', 'ATP'), ('WTA', 'WTA'), ('CH', 'Challenger'))
MIN_CH_AVANT, MIN_CH_JUGE = 300, 150
SEUIL_NOUVEAU = 30          # moins de 30 matchs connus = nouveau venu (même seuil que le Lab)


def _bilan(L):
    return {'n': len(L), 'reussite_pct': round(100 * _ok(L), 1), 'log_loss': round(_ll(L), 4)} if L else None


def par_circuit(hors, P, lim):
    """Fiabilité de chaque circuit joué : tous les pronostics hors échantillon (simulation, Elo), et les 6
    dernières semaines avec le mélange appris avant (même P que la règle d'adoption)."""
    out = {}
    for c, lib in CIRCUITS:
        g = [h for h in hors if h[0]['circuit'] == c]
        if not g:
            continue
        j = [h for h in g if h[0]['jour'] >= lim]
        out[c] = {'circuit': lib, 'simulation': _bilan([h[1] for h in g]), 'elo': _bilan([h[2] for h in g]),
                  'six_dernieres_semaines': {'simulation': _bilan([h[1] for h in j]), 'elo': _bilan([h[2] for h in j]),
                                             'combinaison': _bilan([S.melange(P, h[2], h[1]) for h in j]) if P else None}}
    return out


def poids_circuit(hors, P, lim, ajuster_poids, circuit='CH'):
    """RÈGLE FIXÉE AVANT DE VOIR LE RÉSULTAT (22/10/2026, 23 h 50, pour les Challenger ; étendue telle quelle à l'ATP et
    à la WTA le 29/10/2026, avant le jugement hebdomadaire) : des poids propres au circuit, appris sur ses matchs avant
    les 6 dernières semaines, remplacent les poids communs pour ce circuit s'ils trouvent mieux le vainqueur (log loss
    plus basse) sur ses matchs des 6 dernières semaines. Il faut au moins 300 matchs avant et 150 dans le jugement.
    Puis la stabilité (stabilite.py) : mieux d'au moins 0,001 deux semaines de suite.
    Test du 29/10/2026 sur les pronostics hors échantillon (jugement depuis le 14/09) : ATP 0,6113 → 0,6126 (−0,0013),
    WTA 0,5937 → 0,6029 (−0,0092), Challenger 0,6049 → 0,6046 : non adoptés ; jugés de nouveau chaque semaine."""
    lib = dict(CIRCUITS).get(circuit, circuit)
    g = [h for h in hors if h[0]['circuit'] == circuit]
    av, ju = [h for h in g if h[0]['jour'] < lim], [h for h in g if h[0]['jour'] >= lim]
    if len(av) < MIN_CH_AVANT or len(ju) < MIN_CH_JUGE or not P:
        return {'adopte': False, 'raison': f"pas assez de matchs {lib} ({len(av)} avant, {len(ju)} à juger)"}
    w = ajuster_poids([[_lg(pe), _lg(ps)] for _, ps, pe in av])
    Pc = {'elo': w[0], 'simulation': w[1]}
    l_ch, l_co = _ll([S.melange(Pc, pe, ps) for _, ps, pe in ju]), _ll([S.melange(P, pe, ps) for _, ps, pe in ju])
    ok = l_ch < l_co
    out = {'adopte': bool(ok), 'n_juge': len(ju), 'poids_appris_avant': {k: round(v, 4) for k, v in Pc.items()},
           'll': {'avec': l_ch, 'sans': l_co},
           'raison': (f"{lib} des 6 dernières semaines ({len(ju)} matchs) : poids propres {round(l_ch, 4)} contre poids "
                      f"communs {round(l_co, 4)} ; part de la simulation {part_simulation(Pc)} % contre {part_simulation(P)} %")}
    if ok:
        wf = ajuster_poids([[_lg(pe), _lg(ps)] for _, ps, pe in g])
        out['poids'] = {'elo': round(wf[0], 4), 'simulation': round(wf[1], 4)}
    return out


def poids_challenger(hors, P, lim, ajuster_poids):
    return poids_circuit(hors, P, lim, ajuster_poids, 'CH')


def nouveau(n):
    """0 pour un joueur rodé, jusqu'à 1 pour un joueur jamais vu (décroît jusqu'à 30 matchs)."""
    return max(0.0, 1.0 - n / SEUIL_NOUVEAU)


def _delta(rows, ridge=5.0, tours=30):
    """δ de σ(off + δ·f) (vrai vainqueur y = 1, miroir y = 0) par Newton, ridge vers 0."""
    d = 0.0
    for _ in range(tours):
        g, h = -ridge * d, ridge
        for off, f in rows:
            for sgn, y in ((1, 1), (-1, 0)):
                p = 1 / (1 + math.exp(-max(min(sgn * (off + d * f), 30), -30)))
                g += (y - p) * sgn * f
                h += p * (1 - p) * f * f
        pas = g / h
        d += pas
        if abs(pas) < 1e-9:
            break
    return d


SITUATIONS = {'nouveaux_venus': 'Nouveaux venus', 'qualifies': 'Sortis des qualifications',
              'transition': 'Changement de surface', 'classement': 'Classement du joueur peu connu',
              'classement_relatif': 'Classement relatif quand un joueur est peu connu'}
LIB_SITUATION = {'nouveaux_venus': 'le nouveau venu', 'qualifies': 'le qualifié', 'transition': 'celui qui change de surface',
                 'classement': 'le joueur peu connu mal classé', 'classement_relatif': 'le mieux classé'}
# 28/10/2026 — CLASSEMENT RELATIF quand un joueur est peu connu (rapport des désaccords : l'algo se trompe dans les deux
# sens sur les joueurs peu documentés ; MatchUP montre le classement à côté de chaque joueur). Valeur, vue du joueur 1 :
#     poids × (ln rang du joueur 2 − ln rang du joueur 1),   poids = max(1 − n1/20, 1 − n2/20, 0)
# (n = matchs connus de l'Elo). Seuil 20 CHOISI SUR LA FENÊTRE D'APPRENTISSAGE (20 : 0,61227 ; 30 : 0,61252 ;
# 50 : 0,61360). Test du 28/10 sur les pronostics rejoués, mélange Elo + simulation, jugé depuis le 16/09 :
# log loss 0,60542 → 0,60296 sur 2 263 matchs (peu documentés 0,53022 → 0,51842 ; bien documentés inchangés).
SEUIL_RANG_RELATIF = 20.0


def rang_relatif(n1, n2, r1, r2):
    """Écart de classement (log) pondéré par le manque de documentation, vu du joueur 1 ; 0 sans les deux rangs."""
    if not r1 or not r2:
        return 0.0
    w = max(0.0, 1.0 - (n1 or 0) / SEUIL_RANG_RELATIF, 1.0 - (n2 or 0) / SEUIL_RANG_RELATIF)
    return w * (math.log(r2) - math.log(r1))


def correction_situation(hors, P, lim, valeur, cle_s, poids_finaux=None, min_avant=200, min_juge=100, decalage=None,
                         decalage_final=None):
    """RÈGLE FIXÉE AVANT DE VOIR LE RÉSULTAT (22/10/2026) — même règle pour chaque situation (nouveau venu,
    sorti des qualifications, changement de surface) : le modèle se trompe-t-il TOUJOURS dans le même sens ?
    Correction δ (logit) apprise avant les 6 dernières semaines, sur le mélange :
        z' = z + δ·(situation(vainqueur) − situation(perdant))
    adoptée si la log loss du vainqueur des 6 dernières semaines baisse sur les matchs concernés (au moins 100,
    et 200 avant). valeur(x) -> (situation du vrai vainqueur, du perdant) entre 0 et 1, ou None."""
    lib = LIB_SITUATION[cle_s]
    if not P:
        return {'adopte': False, 'raison': 'pas de mélange'}
    rows = []
    for x, ps, pe in hors:
        v = valeur(x)
        if v is None:
            continue
        # decalage : corrections déjà en place à ajouter au départ (ex. nouveaux venus pour le classement)
        rows.append((x['jour'] >= lim, _lg(S.melange(P, pe, ps)) + (decalage(x) if decalage else 0.0), v[0] - v[1], (x, ps, pe)))
    av = [(o, f) for j, o, f, _ in rows if not j]
    ju = [(o, f) for j, o, f, _ in rows if j and f != 0]
    n_av = sum(1 for _, f in av if f != 0)
    if n_av < min_avant or len(ju) < min_juge:
        return {'adopte': False, 'raison': f"pas assez de matchs concernés ({n_av} avant, {len(ju)} à juger)"}
    d = _delta(av)
    sg_ = lambda z: 1 / (1 + math.exp(-max(min(z, 30), -30)))
    l0, l1 = _ll([sg_(o) for o, _ in ju]), _ll([sg_(o + d * f) for o, f in ju])
    att = sum(1 for o, f in ju if f > 0) / len(ju)          # part des matchs gagnés par celui qui est dans la situation
    ok = l1 < l0
    out = {'adopte': bool(ok), 'delta_appris_avant': round(d, 4), 'n_juge': len(ju), 'll': {'avec': l1, 'sans': l0},
           'raison': (f"{len(ju)} matchs concernés (6 dernières semaines) : log loss {round(l1, 4)} corrigée contre "
                      f"{round(l0, 4)} ; δ = {round(d, 3)} ({lib} est {'sous-estimé' if d > 0 else 'surestimé'})"
                      f" ; {lib} gagne {round(100 * att)} % de ces matchs")}
    if ok:
        Pf = poids_finaux or P
        dfin = decalage_final or decalage
        out['delta'] = round(_delta([(_lg(S.melange(Pf, pe, ps)) + (dfin(x) if dfin else 0.0), f)
                                     for _, _, f, (x, ps, pe) in rows]), 4)
    return out


def nouveaux_venus(hors, P, lim, experience, poids_finaux=None):
    """Moins de 30 matchs connus (nouveau(n) décroît de 1 à 0) — voir correction_situation."""
    if not experience:
        return {'adopte': False, 'raison': 'pas de compte de matchs'}

    def valeur(x):
        e = experience.get(id(x))
        return (nouveau(e[0]), nouveau(e[1])) if e else None
    return correction_situation(hors, P, lim, valeur, 'nouveaux_venus', poids_finaux)


# ------------------------------------------------------------------ 23/10/2026 : des arbres qui combinent tout
VARIABLES = ('z_elo', 'z_sim', 'ecart_nouveau', 'ecart_qualifie', 'ecart_transition',
             'nouveau_max', 'challenger', 'wta', 'terre', 'gazon', 'cinq_sets', 'desaccord', 'ecart_rang_peu_connu')
ECARTS = (0, 1, 2, 3, 4, 12)        # variables « écart » : changent de signe quand on change de côté


def variables_match(p_elo, p_sim, n1, n2, sit1, sit2, circuit, surface, bo, rangs=None):
    """Vu du joueur 1 (en walk-forward : le vrai vainqueur ; en pronostic : home). sit = (qualifié, transition) ;
    rangs = (rang du joueur 1, rang du joueur 2) au jour du match, ou None (28/10/2026)."""
    ze, zs = _lg(p_elo), _lg(p_sim)
    a, b = nouveau(n1), nouveau(n2)
    return [ze, zs, a - b, sit1[0] - sit2[0], sit1[1] - sit2[1], max(a, b), 1.0 if circuit == 'CH' else 0.0,
            1.0 if circuit == 'WTA' else 0.0, 1.0 if surface == 'Clay' else 0.0, 1.0 if surface == 'Grass' else 0.0,
            1.0 if bo == 5 else 0.0, abs(ze - zs), rang_relatif(n1, n2, *(rangs or (None, None)))]


def modele_arbres(hors, P, lim, experience, situations, nv, poids_finaux=None):
    """RÈGLE FIXÉE AVANT DE VOIR LE RÉSULTAT (23/10/2026, 10 h 40) : des arbres (arbres.py) partent du mélange
    et apprennent des corrections avec toutes les variables (Elo, simulation, nouveaux venus, qualifiés,
    changement de surface, circuit, surface, format, désaccord simulation / Elo). Appris avant les 6 dernières
    semaines ; adoptés si la log loss du vainqueur des 6 dernières semaines est plus basse que celle du modèle
    actuel (mélange + correction des nouveaux venus si elle est adoptée). Il faut 1 500 matchs avant et 500 à
    juger. Adoptés, ils sont ré-appris sur tous les pronostics hors échantillon, au-dessus des poids finaux."""
    import arbres as A
    if not P or not experience:
        return {'adopte': False, 'raison': 'pas de mélange ou pas de compte de matchs'}
    lignes = []
    for x, ps, pe in hors:
        e = experience.get(id(x))
        if not e:
            continue
        sv = situations.get(id(x)) or {} if situations else {}
        q, t = sv.get('qualifies') or (0.0, 0.0), sv.get('transition') or (0.0, 0.0)
        v = variables_match(pe, ps, e[0], e[1], (q[0], t[0]), (q[1], t[1]), x.get('circuit'), x.get('surface'), x.get('bo'),
                            sv.get('rangs'))
        lignes.append((x['jour'] >= lim, v, (x, ps, pe), e))
    av = [l for l in lignes if not l[0]]
    ju = [l for l in lignes if l[0]]
    if len(av) < 1500 or len(ju) < 500:
        return {'adopte': False, 'raison': f"pas assez de matchs ({len(av)} avant, {len(ju)} à juger)"}
    off = lambda Pw, h: _lg(S.melange(Pw, h[2], h[1]))
    X, y, o = A.symetriser([(v, off(P, h), ECARTS) for _, v, h, _ in av])
    M = A.apprendre(X, y, o)
    d = (nv or {}).get('delta_appris_avant') if (nv or {}).get('adopte') else None
    sg_ = lambda z: 1 / (1 + math.exp(-max(min(z, 30), -30)))
    actuel = [sg_(off(P, h) + (d * (nouveau(e[0]) - nouveau(e[1])) if d else 0.0)) for _, v, h, e in ju]
    neuf = [A.predire_symetrique(M, v, off(P, h), ECARTS) for _, v, h, _ in ju]
    l0, l1 = _ll(actuel), _ll(neuf)
    ok = l1 < l0
    out = {'adopte': bool(ok), 'n_juge': len(ju), 'variables': list(VARIABLES), 'll': {'avec': l1, 'sans': l0},
           'jugement': {'actuel': _bilan(actuel), 'arbres': _bilan(neuf)},
           'raison': (f"6 dernières semaines ({len(ju)} matchs) : arbres {round(l1, 4)} contre modèle actuel {round(l0, 4)} "
                      f"(vainqueur trouvé {round(100 * _ok(neuf), 1)} % contre {round(100 * _ok(actuel), 1)} %)")}
    if ok:
        Pf = poids_finaux or P
        X, y, o = A.symetriser([(v, off(Pf, h), ECARTS) for _, v, h, _ in lignes])
        out['modele'] = A.apprendre(X, y, o)
        out['poids'] = {k: round(v, 4) for k, v in Pf.items()}       # le mélange de départ, à reprendre tel quel
    return out


# ------------------------------------------------------------------ 29/10/2026 : l'activité récente dans les arbres
VARIABLES_ACTIVITE = VARIABLES + ('ecart_tendance_activite', 'ecart_volume_activite')
ECARTS_ACTIVITE = ECARTS + (len(VARIABLES), len(VARIABLES) + 1)


def variables_match_activite(p_elo, p_sim, n1, n2, sit1, sit2, circuit, surface, bo, rangs=None, activite=None):
    """variables_match + (Δ tendance d'activité, Δ volume) vus du joueur 1 (activite.ecarts) ; (0, 0) sans données."""
    return variables_match(p_elo, p_sim, n1, n2, sit1, sit2, circuit, surface, bo, rangs) + list(activite or (0.0, 0.0))


# 29/10/2026 (après-midi) — LE TOUR DU TABLEAU (qualifications … finale), candidat de la même famille. Étude du 29/10
# (4 821 pronostics hors échantillon, arbres simplifiés, jugement depuis le 14/09) : +0,0014 (WTA +0,0026, Challenger
# +0,0014, ATP −0,0002) ; niveau du tournoi : 0 ; activité : WTA −0,0039. Variables propres au MATCH (pas d'écart).
TOURS = {'qualification round 1': 0, 'qualification round 2': 0, 'qualification round 3': 0, 'qualifications': 0,
         'qualification final': 1, 'round of 128': 2, 'round of 64': 3, 'round of 32': 4, 'round of 16': 5,
         'quarterfinals': 6, 'semifinals': 7, 'final': 8}
TOUR_INCONNU = 4


def variables_tour(nom_tour):
    """(rang du tour / 8, en qualifications 1/0) ; tour inconnu : le 1er tour d'un tableau à 32, hors qualifications."""
    t = TOURS.get(str(nom_tour or '').strip().lower(), TOUR_INCONNU)
    return [t / 8.0, 1.0 if t <= 1 else 0.0]


CANDIDATS_ARBRES = {
    # clé : (situation lue, nombre de variables, indices « écart » ajoutés, valeur neutre, libellé)
    'modele_arbres_activite': ('activite', 2, True, (0.0, 0.0), "l'activité récente"),
    'modele_arbres_tour': ('tour', 2, False, tuple(variables_tour(None)), 'le tour du tableau'),
    # 30/10/2026 — POINTS ATP/WTA DE TOUS LES JOUEURS (classements.ecart_points). Étude du 30/10 (138 657 matchs, appris
    # 2017–2022, jugé 2023–2026, ajouté à l'Elo) : rang + points +0,0023 (Challenger +0,0034, ATP +0,0003, WTA +0,0001) ;
    # le rang seul +0,0005 (ATP −0,0010) : ce sont les points qui portent l'information. MIS EN PRODUCTION PAR
    # DÉCISION DE LUCAS (30/10/2026), sans attendre deux semaines : en place dès le premier modèle appris ; la règle
    # devient la SORTIE (retiré si moins bien que les arbres sans les points deux semaines de suite, stabilite.py).
    'modele_arbres_points': ('points', 1, True, (0.0,), 'les points ATP/WTA de tous les joueurs'),
}
DECISION_CANDIDATS = {'modele_arbres_points': '2026-10-30'}


def ecarts_candidat(cle):
    sit, n, ecart, _, _ = CANDIDATS_ARBRES[cle]
    return ECARTS + (tuple(range(len(VARIABLES), len(VARIABLES) + n)) if ecart else ())


def variables_candidat(cle, p_elo, p_sim, n1, n2, sit1, sit2, circuit, surface, bo, rangs=None, extra=None):
    sit, n, _, neutre, _ = CANDIDATS_ARBRES[cle]
    return variables_match(p_elo, p_sim, n1, n2, sit1, sit2, circuit, surface, bo, rangs) + list(extra if extra is not None else neutre)


def modele_arbres_candidat(cle, hors, P, lim, experience, situations, nv, poids_finaux=None):
    """RÈGLE FIXÉE AVANT DE VOIR LE RÉSULTAT (29/10/2026, 10 h 15 pour l'activité, 11 h pour le tour) : les mêmes arbres
    que modele_arbres (mêmes réglages, même départ, appris sur les mêmes matchs avant les 6 dernières semaines), avec
    en plus les variables du candidat. Comparés aux arbres SANS elles sur les 6 dernières semaines : adoptés si la log
    loss du vainqueur baisse au total ET qu'aucun circuit (ATP, WTA, Challenger) ne perd plus de 0,001 ; puis stabilité
    (stabilite.py) : mieux d'au moins 0,001 deux semaines de suite. Il faut 1 500 matchs avant et 500 à juger. Adoptés,
    ils remplacent les arbres en production (ré-appris sur tous les pronostics hors échantillon)."""
    import arbres as A
    sit_k, n_k, _, neutre, lib = CANDIDATS_ARBRES[cle]
    ec1 = ecarts_candidat(cle)
    if not P or not experience:
        return {'adopte': False, 'raison': 'pas de mélange ou pas de compte de matchs'}
    lignes = []
    for x, ps, pe in hors:
        e = experience.get(id(x))
        if not e:
            continue
        sv = situations.get(id(x)) or {} if situations else {}
        q, t = sv.get('qualifies') or (0.0, 0.0), sv.get('transition') or (0.0, 0.0)
        a = (x.get('circuit'), x.get('surface'), x.get('bo'))
        v0 = variables_match(pe, ps, e[0], e[1], (q[0], t[0]), (q[1], t[1]), *a, sv.get('rangs'))
        v1 = variables_candidat(cle, pe, ps, e[0], e[1], (q[0], t[0]), (q[1], t[1]), *a, sv.get('rangs'), sv.get(sit_k))
        lignes.append((x['jour'] >= lim, v0, v1, (x, ps, pe), sv.get(sit_k) is not None))
    av = [l for l in lignes if not l[0]]
    ju = [l for l in lignes if l[0]]
    if len(av) < 1500 or len(ju) < 500:
        return {'adopte': False, 'raison': f"pas assez de matchs ({len(av)} avant, {len(ju)} à juger)"}
    if not any(l[4] for l in av):
        return {'adopte': False, 'raison': f"pas de données ({lib})"}
    off = lambda Pw, h: _lg(S.melange(Pw, h[2], h[1]))
    X0, y0, o0 = A.symetriser([(v0, off(P, h), ECARTS) for _, v0, _, h, _ in av])
    X1, y1, o1 = A.symetriser([(v1, off(P, h), ec1) for _, _, v1, h, _ in av])
    M0, M1 = A.apprendre(X0, y0, o0), A.apprendre(X1, y1, o1)
    sans = [A.predire_symetrique(M0, v0, off(P, h), ECARTS) for _, v0, _, h, _ in ju]
    avec = [A.predire_symetrique(M1, v1, off(P, h), ec1) for _, _, v1, h, _ in ju]
    l0, l1 = _ll(sans), _ll(avec)
    par = {}
    for c, _ in CIRCUITS:
        ix = [i for i, l in enumerate(ju) if l[3][0].get('circuit') == c]
        if ix:
            par[c] = {'n': len(ix), 'gain': round(_ll([sans[i] for i in ix]) - _ll([avec[i] for i in ix]), 5)}
    pire = min((v['gain'] for v in par.values()), default=0.0)
    ok = l1 < l0 and pire >= -0.001
    out = {'adopte': bool(ok), 'n_juge': len(ju), 'variables': list(VARIABLES) + [f'{sit_k}_{i}' for i in range(n_k)],
           'll': {'avec': l1, 'sans': l0}, 'par_circuit': par,
           'raison': (f"6 dernières semaines ({len(ju)} matchs) : arbres avec {lib} {round(l1, 4)} contre sans "
                      f"{round(l0, 4)} ; " + ', '.join(f"{c} {v['gain']:+.4f}" for c, v in par.items()))}
    if ok or cle in DECISION_CANDIDATS:            # 30/10/2026 : candidat mis en production par décision → modèle toujours appris
        if cle in DECISION_CANDIDATS:
            out['decision'] = DECISION_CANDIDATS[cle]
        Pf = poids_finaux or P
        X, y, o = A.symetriser([(v1, off(Pf, h), ec1) for _, _, v1, h, _ in lignes])
        out['modele'] = A.apprendre(X, y, o)
        out['poids'] = {k: round(v, 4) for k, v in Pf.items()}
    return out


# ------------------------------------------------------------------ 29/10/2026 : désaccords Elo / simulation en WTA
MIN_DESACCORD_AVANT, MIN_DESACCORD_JUGE = 80, 50


def desaccord(pe, ps):
    """L'Elo et la simulation désignent-ils deux vainqueurs différents ?"""
    return (pe >= .5) != (ps >= .5)


def desaccord_wta(hors, P, lim, ajuster_poids, experience, situations, poids_finaux=None):
    """RÈGLE FIXÉE AVANT DE VOIR LE RÉSULTAT (29/10/2026, 13 h 45). Constat (pronostics hors échantillon depuis juin) :
    en WTA, quand l'Elo et la simulation désignent deux vainqueurs différents, l'Elo a raison 60,8 % du temps et
    l'algo affiché 57,5 %. Candidat : sur ces matchs-là seulement, un mélange Elo + simulation PROPRE, appris sur les
    désaccords WTA d'avant les 6 dernières semaines (au moins 80), remplace le pronostic de production (les arbres,
    appris sur la même période). Jugé sur les 6 dernières semaines (au moins 50 désaccords WTA) : adopté si la log
    loss du vainqueur baisse sur l'ensemble des matchs jugés ; puis stabilité (stabilite.py) : mieux d'au moins
    0,001 deux semaines de suite. Aperçu du 29/10 sur le mélange simple : 0,0000 (rien à gagner pour l'instant)."""
    import arbres as A
    if not P or not experience:
        return {'adopte': False, 'raison': 'pas de mélange ou pas de compte de matchs'}
    lignes = []
    for x, ps, pe in hors:
        e = experience.get(id(x))
        if not e:
            continue
        sv = situations.get(id(x)) or {} if situations else {}
        q, t = sv.get('qualifies') or (0.0, 0.0), sv.get('transition') or (0.0, 0.0)
        v0 = variables_match(pe, ps, e[0], e[1], (q[0], t[0]), (q[1], t[1]), x.get('circuit'), x.get('surface'), x.get('bo'),
                             sv.get('rangs'))
        lignes.append((x['jour'] >= lim, v0, (x, ps, pe), x.get('circuit') == 'WTA' and desaccord(pe, ps)))
    av = [l for l in lignes if not l[0]]
    ju = [l for l in lignes if l[0]]
    d_av, d_ju = [l for l in av if l[3]], [l for l in ju if l[3]]
    if len(d_av) < MIN_DESACCORD_AVANT or len(d_ju) < MIN_DESACCORD_JUGE or len(av) < 1500:
        return {'adopte': False, 'raison': f"pas assez de désaccords WTA ({len(d_av)} avant, {len(d_ju)} à juger)"}
    off = lambda Pw, h: _lg(S.melange(Pw, h[2], h[1]))
    X0, y0, o0 = A.symetriser([(v0, off(P, h), ECARTS) for _, v0, h, _ in av])
    M0 = A.apprendre(X0, y0, o0)
    w = ajuster_poids([[_lg(h[2]), _lg(h[1])] for _, _, h, _ in d_av])
    Pd = {'elo': w[0], 'simulation': w[1]}
    sans = [A.predire_symetrique(M0, v0, off(P, h), ECARTS) for _, v0, h, _ in ju]
    avec = [S.melange(Pd, h[2], h[1]) if d else b for (_, _, h, d), b in zip(ju, sans)]
    l0, l1 = _ll(sans), _ll(avec)
    ix = [i for i, l in enumerate(ju) if l[3]]
    ok = l1 < l0
    out = {'adopte': bool(ok), 'n_juge': len(ju), 'n_desaccords_juges': len(ix), 'll': {'avec': l1, 'sans': l0},
           'poids_appris_avant': {k: round(v, 4) for k, v in Pd.items()},
           'raison': (f"{len(ix)} désaccords WTA jugés (6 dernières semaines) : log loss sur eux "
                      f"{round(_ll([avec[i] for i in ix]), 4)} contre {round(_ll([sans[i] for i in ix]), 4)} ; vainqueurs "
                      f"{round(100 * _ok([avec[i] for i in ix]), 1)} % contre {round(100 * _ok([sans[i] for i in ix]), 1)} % ; "
                      f"part de l'Elo {round(100 - part_simulation(Pd), 1)} %")}
    if ok:
        wf = ajuster_poids([[_lg(h[2]), _lg(h[1])] for _, _, h, d in lignes if d])
        out['poids'] = {'elo': round(wf[0], 4), 'simulation': round(wf[1], 4)}
    return out


def modele_arbres_activite(hors, P, lim, experience, situations, nv, poids_finaux=None):
    return modele_arbres_candidat('modele_arbres_activite', hors, P, lim, experience, situations, nv, poids_finaux)


def rejouer_saison(lignes, p_elo, groupes, apprendre, victoire_ligne, ajuster_poids, sigma,
                   poids_archive=None, aujourdhui=None, experience=None, situations=None):
    """Pronostics hors échantillon semaine par semaine ; renvoie le rapport et les poids finaux."""
    if not lignes:
        return {'semaines': [], 'adopte': False, 'raison': 'pas de feuilles'}
    L = sorted(lignes, key=lambda y: y['t'])
    d0 = min(x['jour'] for x in L)
    par_sem = {}
    for x in L:
        par_sem.setdefault(semaine(x['jour'], d0), []).append(x)
    nsem = max(par_sem) + 1
    hors = []                            # (x, p_sim, p_elo)
    export = []                          # pronostics hors échantillon, vus de home (etude_rentabilite_marches.py)
    semaines = []
    poids = None
    for s_ in range(SEMAINES_MIN, nsem):
        passe = [x for k in range(s_) for x in par_sem.get(k, [])]
        coefs = apprendre(passe, groupes) if groupes else {}
        if len(hors) >= 300:
            w = ajuster_poids([[_lg(pe), _lg(ps)] for _, ps, pe in hors])
            poids = {'elo': w[0], 'simulation': w[1]}
        cur = []
        for x in par_sem.get(s_, []):
            ps = victoire_ligne(x, coefs, sigma)
            pe = p_elo.get(id(x))
            if pe is None:
                continue
            cur.append((x, ps, pe))
        if not cur:
            continue
        pc = [S.melange(poids, pe, ps) for _, ps, pe in cur] if poids else None
        for i, (x, ps, pe) in enumerate(cur):          # 23/10/2026 : export (vu de HOME) pour l'étude des marchés
            f = (lambda p: p) if x['vainqueur'] == 0 else (lambda p: 1 - p)
            export.append({'id': x.get('id'), 't': x['t'], 'jour': str(x['jour']), 'circuit': x.get('circuit'),
                           'gagnant': 'home' if x['vainqueur'] == 0 else 'away', 'p_sim': round(f(ps), 4),
                           'p_elo': round(f(pe), 4), 'p_algo': round(f(pc[i]), 4) if pc else None})
        semaines.append({'semaine': s_ + 1, 'debut': str(d0 + dt.timedelta(days=7 * s_)), 'n': len(cur),
                         'simulation': {'reussite_pct': round(100 * _ok([c[1] for c in cur]), 1), 'log_loss': round(_ll([c[1] for c in cur]), 4)},
                         'elo': {'reussite_pct': round(100 * _ok([c[2] for c in cur]), 1), 'log_loss': round(_ll([c[2] for c in cur]), 4)},
                         'combinaison': ({'reussite_pct': round(100 * _ok(pc), 1), 'log_loss': round(_ll(pc), 4)} if pc else None),
                         'poids_simulation_pct': part_simulation(poids) if poids else None})
        hors.extend(cur)
    if len(hors) < MIN_HORS:
        return {'semaines': semaines, 'n_hors_echantillon': len(hors), 'adopte': False, 'export': export,
                'raison': f"pas assez de pronostics hors échantillon ({len(hors)})"}
    w = ajuster_poids([[_lg(pe), _lg(ps)] for _, ps, pe in hors])
    final = {'elo': round(w[0], 4), 'simulation': round(w[1], 4)}
    aujourdhui = aujourdhui or max(x['jour'] for x in L)
    lim = aujourdhui - dt.timedelta(days=FENETRE_JUGE_J)
    avant = [h for h in hors if h[0]['jour'] < lim]
    juge = [h for h in hors if h[0]['jour'] >= lim]
    out = {'semaines': semaines, 'n_hors_echantillon': len(hors), 'poids': final, 'export': export,
           'poids_simulation_pct': part_simulation(final),
           'total': {'simulation': {'reussite_pct': round(100 * _ok([h[1] for h in hors]), 1), 'log_loss': round(_ll([h[1] for h in hors]), 4)},
                     'elo': {'reussite_pct': round(100 * _ok([h[2] for h in hors]), 1), 'log_loss': round(_ll([h[2] for h in hors]), 4)}}}
    if len(avant) < 300 or len(juge) < 200:
        return dict(out, adopte=False, raison='pas assez de matchs pour juger')
    wa = ajuster_poids([[_lg(pe), _lg(ps)] for _, ps, pe in avant])
    P = {'elo': wa[0], 'simulation': wa[1]}
    out['par_circuit'] = par_circuit(hors, P, lim)
    out['poids_challenger'] = poids_challenger(hors, P, lim, ajuster_poids)
    for c_ in ('ATP', 'WTA'):                              # 29/10/2026 : même règle que les Challenger
        out['poids_' + c_] = poids_circuit(hors, P, lim, ajuster_poids, c_)
    out['nouveaux_venus'] = nouveaux_venus(hors, P, lim, experience, final)
    # 23/10/2026 : « classement » = même règle, valeur = niveau_inconnu (classements.py) : le classement ne compte
    # que pour un joueur peu connu ; corrige PAR-DESSUS le mélange, comme les autres situations.
    nv = out.get('nouveaux_venus') or {}

    def dec_nv(d):
        if not d or not experience:
            return None
        return lambda x: d * (nouveau(experience.get(id(x), (99, 99))[0]) - nouveau(experience.get(id(x), (99, 99))[1]))
    def dec_cumul(cles, cle_delta):
        """Corrections déjà en place (nouveaux venus + situations listées), à ajouter au départ."""
        parts = []
        if nv.get('adopte') and nv.get(cle_delta) is not None:
            parts.append(dec_nv(nv.get(cle_delta)))
        for c_ in cles:
            o = out.get(c_) or {}
            if o.get('adopte') and o.get(cle_delta) is not None:
                d_ = o[cle_delta]
                parts.append(lambda x, c_=c_, d_=d_: d_ * (lambda v: (v[0] - v[1]) if v else 0.0)((situations.get(id(x)) or {}).get(c_)))
        parts = [p_ for p_ in parts if p_]
        return (lambda x: sum(p_(x) for p_ in parts)) if parts else None
    for cle_s in ('qualifies', 'transition', 'classement', 'classement_relatif'):
        extra = {}
        if cle_s == 'classement' and nv.get('adopte'):          # par-dessus la correction des nouveaux venus
            extra = {'decalage': dec_nv(nv.get('delta_appris_avant')), 'decalage_final': dec_nv(nv.get('delta'))}
        if cle_s == 'classement_relatif':                       # par-dessus nouveaux venus et classement
            extra = {'decalage': dec_cumul(('classement',), 'delta_appris_avant'),
                     'decalage_final': dec_cumul(('classement',), 'delta')}
        out[cle_s] = (correction_situation(hors, P, lim, lambda x, c=cle_s: (situations.get(id(x)) or {}).get(c), cle_s, final,
                                           **extra)
                      if situations else {'adopte': False, 'raison': 'pas de données'})
    out['modele_arbres'] = modele_arbres(hors, P, lim, experience, situations, out.get('nouveaux_venus'), final)
    out['desaccord_wta'] = desaccord_wta(hors, P, lim, ajuster_poids, experience, situations, final)
    for cle_c in CANDIDATS_ARBRES:                     # 29/10/2026 : activité récente, tour du tableau
        out[cle_c] = modele_arbres_candidat(cle_c, hors, P, lim, experience, situations, out.get('nouveaux_venus'), final)
    l_new = _ll([S.melange(P, pe, ps) for _, ps, pe in juge])
    l_arch = _ll([S.melange(poids_archive, pe, ps) for _, ps, pe in juge]) if poids_archive else None
    l_elo = _ll([pe for _, _, pe in juge])
    ok = l_arch is None or l_new < l_arch
    return dict(out, adopte=bool(ok), ll={'avec': l_new, 'sans': l_arch},
                jugement={'n': len(juge), 'depuis': str(lim), 'log_loss_feuilles': round(l_new, 5),
                                                  'log_loss_poids_archive': round(l_arch, 5) if l_arch is not None else None,
                                                  'log_loss_elo_seul': round(l_elo, 5)},
                raison=(f"6 dernières semaines ({len(juge)} matchs) : poids appris sur les feuilles {round(l_new, 4)} contre "
                        f"poids de l'archive {round(l_arch, 4) if l_arch is not None else '—'} (Elo seul {round(l_elo, 4)}) ; "
                        f"poids de la simulation {out['poids_simulation_pct']} %"))


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))
