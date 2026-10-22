#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
match_simule.py — le match joué AVANT l'heure, 5 000 fois, point par point (22/10/2026).

Le moteur exact (modele.py) donne les probabilités du score. Ici, on rejoue le
match au hasard, point par point, avec le DÉTAIL de chaque service :

    1re balle dans le court ?  (f)        -> sinon 2e balle
    1re balle : ace ? (a)  point gagné ? (w1)
    2e balle  : double faute ? (d)  point gagné si la balle est jouée ? (w2j)

Ces taux viennent du profil de chaque joueur (profils_service.py) et de son
adversaire (un bon relanceur concède moins d'aces et gagne plus de points
derrière la 1re et la 2e balle). Le NIVEAU est ancré sur la probabilité de
victoire de la version choisie (Elo « stats seules » ou Pinnacle « stats +
marché ») avec la même forme du jour que le moteur exact : le pourcentage de
victoire de la simulation retombe sur celui du pronostic (contrôlé par test).

Chaque simulation produit une feuille de match complète, comme les
statistiques en direct : aces, doubles fautes, % de 1re balle, points gagnés
derrière la 1re et la 2e balle, balles de break obtenues / converties, jeux
de service gagnés, points gagnés, jeux, tie-breaks, score set par set.
On en tire la moyenne et la fourchette à 80 % (10e–90e centile) de chaque
statistique, les scores les plus fréquents et un « match type » : la
simulation la plus proche de la médiane parmi celles du score le plus probable.

Règles identiques à modele.py : avantage, tie-break à 7 à 6-6, set décisif à
10 points au meilleur des 5, premier serveur à pile ou face, service alterné
en comptant le tie-break comme un jeu. Bibliothèque standard seulement.
"""
import hashlib
import math
import random

import modele as M

# Index des compteurs par joueur dans une feuille simulée.
SVPT, IN1, W1, W2, ACE, DF, BPF, BPS, SG, SGW, PTS, JEUX = range(12)
NOMS_STATS = ('points_service', 'premieres_dans', 'gagnes_1re', 'gagnes_2e', 'aces', 'doubles_fautes',
              'balles_break_subies', 'balles_break_sauvees', 'jeux_service', 'jeux_service_gagnes',
              'points_gagnes', 'jeux')


def _lg(x):
    x = min(max(x, 1e-6), 1 - 1e-6)
    return math.log(x / (1 - x))


def _sg(z):
    return 1 / (1 + math.exp(-z))


# ------------------------------------------------------------------ composantes
def composantes(serveur, relanceur, moy):
    """Taux du point quand `serveur` sert contre `relanceur`.

    serveur / relanceur / moy : dicts de profil {f, a, d, w1, w2j, ra, r1, r2j} (moy = circuit et surface).
    Le relanceur décale aces, w1 et w2j en logit par rapport à la moyenne du circuit."""
    a = _sg(_lg(serveur['a']) + _lg(relanceur['ra']) - _lg(moy['ra']))
    w1 = _sg(_lg(serveur['w1']) + _lg(relanceur['r1']) - _lg(moy['r1']))
    w2j = _sg(_lg(serveur['w2j']) + _lg(relanceur['r2j']) - _lg(moy['r2j']))
    return borner({'f': serveur['f'], 'a': a, 'w1': w1, 'd': serveur['d'], 'w2j': w2j})


def composantes_ajustees(adj, serveur, relanceur, circuit, surface):
    """Taux du point ajustés au niveau des adversaires rencontrés (ajustement.Ajuste)."""
    return borner(adj.taux(serveur, relanceur, circuit, surface))


def borner(c):
    c = dict(c)
    c['f'] = min(max(c['f'], 0.3), 0.95)
    c['d'] = min(max(c['d'], 0.0), 0.5)
    c['w1'] = min(max(c['w1'], 0.2), 0.99)
    c['w2j'] = min(max(c['w2j'], 0.1), 0.99)
    c['a'] = min(max(c['a'], 0.0), 0.95 * c['w1'])
    return c


def p_service(c):
    """P(le serveur gagne le point) à partir des composantes."""
    return c['f'] * c['w1'] + (1 - c['f']) * (1 - c['d']) * c['w2j']


def ajuster(c, p_cible):
    """Même profil, niveau déplacé : w1 et w2j décalés du même δ (logit) pour que p_service = p_cible.
    Les aces suivent w1 dans la même proportion (un joueur qui domine fait aussi plus d'aces)."""
    l1, l2 = _lg(c['w1']), _lg(c['w2j'])
    f, d = c['f'], c['d']
    lo, hi = -8.0, 8.0
    for _ in range(40):
        m = (lo + hi) / 2
        if f * _sg(l1 + m) + (1 - f) * (1 - d) * _sg(l2 + m) < p_cible:
            lo = m
        else:
            hi = m
    m = (lo + hi) / 2
    w1 = _sg(l1 + m)
    out = dict(c, w1=w1, w2j=_sg(l2 + m), a=min(c['a'] * w1 / c['w1'], 0.95 * w1))
    return out


def tenue(p, p_bp=None):
    """P(le serveur gagne son jeu) quand il gagne chaque point avec p, et p_bp sur BALLE DE BREAK
    (le relanceur est à un point du jeu). p_bp = p redonne modele.p_jeu (22/10/2026)."""
    q = p if p_bp is None else p_bp
    if q == p:
        return M.p_jeu(p)
    memo = {}
    # égalité : D = p² + p(1−p)·D + (1−p)·q·D  (avantage serveur puis point, ou balle de break sauvée)
    den = 1 - p * (1 - p) - (1 - p) * q
    deuce = p * p / den if den > 0 else 0.5

    def v(a, b):
        if a >= 4 and a - b >= 2:
            return 1.0
        if b >= 4 and b - a >= 2:
            return 0.0
        if a >= 3 and b >= 3 and a == b:
            return deuce
        if (a, b) in memo:
            return memo[(a, b)]
        x = q if (b >= 3 and b > a) else p
        memo[(a, b)] = r = x * v(a + 1, b) + (1 - x) * v(a, b + 1)
        return r
    return v(0, 0)


_SET_CACHE = {}


def set_issues_bp(pA, pB, qA, qB, a_sert_premier, cible_tb=7):
    """modele.set_issues avec une probabilité propre aux balles de break (qA, qB)."""
    cle = (pA, pB, qA, qB, a_sert_premier, cible_tb)
    if cle in _SET_CACHE:
        return _SET_CACHE[cle]
    hA, hB = tenue(pA, qA), tenue(pB, qB)
    etats, fin = {(0, 0): 1.0}, {}
    while etats:
        nouv = {}
        for (a, b), pr in etats.items():
            sert_a = ((a + b) % 2 == 0) == a_sert_premier
            if a == 6 and b == 6:
                t = M.p_tiebreak(pA, pB, sert_a, cible_tb)
                fin[(7, 6)] = fin.get((7, 6), 0.0) + pr * t
                fin[(6, 7)] = fin.get((6, 7), 0.0) + pr * (1 - t)
                continue
            w = hA if sert_a else 1 - hB
            for na, nb, x in ((a + 1, b, w), (a, b + 1, 1 - w)):
                if (na >= 6 and na - nb >= 2) or (nb >= 6 and nb - na >= 2):
                    fin[(na, nb)] = fin.get((na, nb), 0.0) + pr * x
                else:
                    nouv[(na, nb)] = nouv.get((na, nb), 0.0) + pr * x
        etats = nouv
    if len(_SET_CACHE) > 20000:
        _SET_CACHE.clear()
    _SET_CACHE[cle] = out = tuple((a, b, pr) for (a, b), pr in sorted(fin.items()))
    return out


def victoire(pA, pB, sets_gagnants=2, tb_final=None, dA=0.0, dB=0.0):
    """P(A gagne le match) seule — même calcul que modele.match()['victoire'], sans suivre les jeux
    (états : sets et serveur), donc bien plus rapide pour l'ancrage.
    dA, dB (22/10/2026) : décalage, en logit, du point de service sur balle de break."""
    if tb_final is None:
        tb_final = 10 if sets_gagnants == 3 else 7
    bp = bool(dA or dB)
    qA, qB = (_sg(_lg(pA) + dA), _sg(_lg(pB) + dB)) if bp else (pA, pB)
    tot = 0.0
    for a_premier in (True, False):
        etats = {(0, 0, a_premier): 0.5}
        while etats:
            nouv = {}
            for (sa, sb, srv), pr in etats.items():
                decisif = sa == sets_gagnants - 1 and sb == sets_gagnants - 1
                issues = (set_issues_bp(pA, pB, qA, qB, srv, tb_final if decisif else 7) if bp
                          else M.set_issues(pA, pB, srv, tb_final if decisif else 7))
                for a, b, x in issues:
                    na, nb = sa + (a > b), sb + (b > a)
                    m = pr * x
                    if na == sets_gagnants:
                        tot += m
                    elif nb < sets_gagnants:
                        k = (na, nb, srv if (a + b) % 2 == 0 else not srv)
                        nouv[k] = nouv.get(k, 0.0) + m
            etats = nouv
    return tot


def ancrer_rapide(pA, pB, p_cible, sets_gagnants=2, sigma=0.0, iterations=30, dA=0.0, dB=0.0):
    """Comme modele.ancrer_forme (même mélange de forme, mêmes 13 nœuds), avec victoire() rapide."""
    la, lb = _lg(pA), _lg(pB)
    noeuds = [(0.0, 1.0)] if sigma <= 0 else [(sigma * z, w) for z, w in zip(M._Z, M._W)]
    lo, hi = -6.0, 6.0
    for _ in range(iterations):
        d = (lo + hi) / 2
        v = sum(w * victoire(_sg(la + d + dz), _sg(lb - d - dz), sets_gagnants, None, dA, dB) for dz, w in noeuds)
        if v < p_cible:
            lo = d
        else:
            hi = d
    d = (lo + hi) / 2
    return _sg(la + d), _sg(lb - d)


def victoire_pure(cA, cB, sets_gagnants=2, sigma=0.0):
    """P(A gagne) de la simulation pure (limite exacte de n → ∞ simulations, même forme du jour)."""
    la, lb = _lg(p_service(cA)), _lg(p_service(cB))
    noeuds = [(0.0, 1.0)] if sigma <= 0 else [(sigma * z, w) for z, w in zip(M._Z, M._W)]
    dA, dB = cA.get('bp', 0.0), cB.get('bp', 0.0)
    return sum(w * victoire(_sg(la + dz), _sg(lb - dz), sets_gagnants, None, dA, dB) for dz, w in noeuds)


def noeuds_de_forme(cA, cB, p_victoire, sets_gagnants, sigma):
    """[(poids, composantes A, composantes B)] : niveau ancré sur p_victoire APRÈS la forme du jour
    (mêmes 13 nœuds que modele.match_forme). Le hasard de la simulation tire un nœud par match.

    p_victoire=None (22/10/2026) : SIMULATION PURE — aucun ancrage ; le match se joue avec les
    seuls taux des deux joueurs (service de l'un contre retour de l'autre) et c'est la
    simulation qui dit qui gagne."""
    pA0, pB0 = p_service(cA), p_service(cB)
    if p_victoire is None:
        a, b = pA0, pB0
    else:
        a, b = ancrer_rapide(pA0, pB0, min(max(p_victoire, 0.005), 0.995), sets_gagnants, sigma,
                             dA=cA.get('bp', 0.0), dB=cB.get('bp', 0.0))
    if sigma <= 0:
        return [(1.0, ajuster(cA, a), ajuster(cB, b))]
    out = []
    for z, w in zip(M._Z, M._W):
        dz = sigma * z
        out.append((w, ajuster(cA, _sg(_lg(a) + dz)), ajuster(cB, _sg(_lg(b) - dz))))
    return out


# ------------------------------------------------------------------ un match
def un_match(cA, cB, sets_gagnants, tb_final, rnd, a_sert):
    """Joue un match. Renvoie (gagnant 0/1, sets [(jA, jB)], feuille [2][12], breaks [(set, jA, jB, 0/1)], tb)."""
    C = (cA, cB)
    P = [(c['f'], c['a'], c['w1'], c['d'], c['w2j']) for c in C]
    # balles de break (22/10/2026) : points gagnés derrière la 1re et la 2e décalés de c['bp'] (logit)
    Pb = [(c['f'], min(c['a'], 0.95 * _sg(_lg(c['w1']) + c['bp'])), _sg(_lg(c['w1']) + c['bp']), c['d'],
           _sg(_lg(c['w2j']) + c['bp'])) if c.get('bp') else None for c in C]
    st = [[0] * 12, [0] * 12]
    r = rnd.random
    sets, ss, breaks, ntb = [], [0, 0], [], 0
    srv = 0 if a_sert else 1

    def point(s, bp=False):
        f, a, w1, d, w2j = Pb[s] if (bp and Pb[s]) else P[s]
        x = st[s]
        x[SVPT] += 1
        if r() < f:
            x[IN1] += 1
            y = r()
            if y < a:
                x[ACE] += 1
                x[W1] += 1
                return True
            if y < w1:
                x[W1] += 1
                return True
            return False
        y = r()
        if y < d:
            x[DF] += 1
            return False
        if r() < w2j:
            x[W2] += 1
            return True
        return False

    while ss[0] < sets_gagnants and ss[1] < sets_gagnants:
        g = [0, 0]
        decisif = ss[0] == sets_gagnants - 1 and ss[1] == sets_gagnants - 1
        while True:
            if g[0] == 6 and g[1] == 6:
                cible = tb_final if decisif else 7
                t = [0, 0]
                k = 0
                while True:
                    s = srv if ((k + 1) // 2) % 2 == 0 else 1 - srv
                    gagne = point(s)
                    v = s if gagne else 1 - s
                    t[v] += 1
                    st[v][PTS] += 1
                    k += 1
                    if t[v] >= cible and t[v] - t[1 - v] >= 2:
                        break
                g[v] += 1
                st[v][JEUX] += 1
                ntb += 1
                srv = 1 - srv
                break
            s, o = srv, 1 - srv
            ps = [0, 0]                       # points du serveur, du relanceur
            st[s][SG] += 1
            while True:
                bp = ps[1] >= 3 and ps[1] > ps[0]
                if bp:
                    st[s][BPF] += 1
                if point(s, bp):
                    ps[0] += 1
                    st[s][PTS] += 1
                    if bp:
                        st[s][BPS] += 1
                else:
                    ps[1] += 1
                    st[o][PTS] += 1
                if ps[0] >= 4 and ps[0] - ps[1] >= 2:
                    v = s
                    break
                if ps[1] >= 4 and ps[1] - ps[0] >= 2:
                    v = o
                    break
            if v == s:
                st[s][SGW] += 1
            else:
                breaks.append((len(sets), g[0], g[1], o))
            g[v] += 1
            st[v][JEUX] += 1
            srv = 1 - srv
            if (g[0] >= 6 or g[1] >= 6) and abs(g[0] - g[1]) >= 2:
                break
        sets.append((g[0], g[1]))
        ss[0 if g[0] > g[1] else 1] += 1
    return (0 if ss[0] > ss[1] else 1), sets, st, breaks, ntb


# ------------------------------------------------------------------ 5 000 matchs
def graine(texte):
    return int(hashlib.sha256(str(texte).encode('utf-8')).hexdigest()[:12], 16)


def _quantile(v, q):
    v = sorted(v)
    if not v:
        return None
    i = q * (len(v) - 1)
    lo = int(math.floor(i))
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (i - lo)


def feuille_derivee(st_j, st_adv):
    """Statistiques lisibles d'un joueur (comme une feuille de match en direct)."""
    sv, in1 = st_j[SVPT], st_j[IN1]
    deux = sv - in1
    return {'aces': st_j[ACE], 'doubles_fautes': st_j[DF],
            'premiere_pct': 100 * in1 / sv if sv else None,
            'gagnes_1re_pct': 100 * st_j[W1] / in1 if in1 else None,
            'gagnes_2e_pct': 100 * st_j[W2] / deux if deux else None,
            'balles_break_obtenues': st_adv[BPF], 'breaks': st_adv[BPF] - st_adv[BPS],
            'balles_break_sauvees': st_j[BPS], 'balles_break_subies': st_j[BPF],
            'jeux_service_gagnes_pct': 100 * st_j[SGW] / st_j[SG] if st_j[SG] else None,
            'points_gagnes': st_j[PTS], 'jeux': st_j[JEUX]}


CLES_FEUILLE = ('aces', 'doubles_fautes', 'premiere_pct', 'gagnes_1re_pct', 'gagnes_2e_pct',
                'balles_break_obtenues', 'breaks', 'jeux_service_gagnes_pct', 'points_gagnes', 'jeux')


CONTEXTE_COLS = ('sim_gazon', 'sim_terre', 'sim_wta', 'sim_5sets', 'elo_gazon', 'elo_terre', 'elo_wta', 'elo_5sets')


def contexte_match(surface, circuit, bo):
    """Indicateurs du contexte (22/10/2026) : gazon, terre, WTA, 5 sets."""
    return {'gazon': 1.0 if surface == 'Grass' else 0.0, 'terre': 1.0 if surface == 'Clay' else 0.0,
            'wta': 1.0 if circuit == 'WTA' else 0.0, '5sets': 1.0 if bo == 5 else 0.0}


def variables_contexte(ctx, z_elo, z_sim):
    return [z_sim * ctx['gazon'], z_sim * ctx['terre'], z_sim * ctx['wta'], z_sim * ctx['5sets'],
            z_elo * ctx['gazon'], z_elo * ctx['terre'], z_elo * ctx['wta'], z_elo * ctx['5sets']]


def melange_contexte(poids, ctx, p_elo, p_sim):
    """Mélange simulation + Elo dont les poids changent selon le contexte (poids['contexte'] = 8 corrections)."""
    ze = _lg(min(max(p_elo, 1e-6), 1 - 1e-6))
    zs = _lg(min(max(p_sim, 1e-6), 1 - 1e-6))
    z = poids['elo'] * ze + poids['simulation'] * zs
    c = poids.get('contexte')
    if c and ctx:
        z += sum(c.get(k, 0.0) * v for k, v in zip(CONTEXTE_COLS, variables_contexte(ctx, ze, zs)))
    return _sg(max(min(z, 30), -30))


# 22/10/2026 — EXCÈS DE CONFIANCE. Favori annoncé 80–90 % → gagne 79,9 % (2025 →). Correction de la
# probabilité finale, symétrique (même traitement pour le favori et l'outsider), en logit :
#   |z'| = |z| + Σ c_i · max(0, |z| − n_i), nœuds n_i = logit de 50, 60, 70, 80, 90 %.
# Une pente par tranche : on peut calmer les 80–90 % sans toucher aux 55 %. c appris sur 2024, jugé
# sur 2025 → (backtest_match_simule.calibration_combinaison).
CALIBRATION_NOEUDS = (0.0, 0.405465, 0.847298, 1.386294, 2.197225)


def variables_calibration(z):
    a = abs(z)
    s = 1.0 if z >= 0 else -1.0
    return [s * max(0.0, a - n) for n in CALIBRATION_NOEUDS]


def calibrer(p, c):
    """Probabilité corrigée (c = 5 pentes) ; c vide : inchangée. Toujours croissante : pente plancher 0,1."""
    if not c:
        return p
    z = _lg(min(max(p, 1e-6), 1 - 1e-6))
    a, out, debut, pente = abs(z), 0.0, 0.0, 1.0
    bornes = list(CALIBRATION_NOEUDS[1:]) + [float('inf')]
    for ci, fin_ in zip(c, bornes):                    # pente de chaque tranche = 1 + Σ c jusque-là
        pente += ci
        if a <= debut:
            break
        out += max(pente, 0.1) * (min(a, fin_) - debut)
        debut = fin_
    return _sg(max(min(out if z >= 0 else -out, 30), -30))


def amplifier(c, moyen, k):
    """22/10/2026 — la simulation est trop timide (favori annoncé 64 % → gagne 69 %) : l'écart de chaque
    taux du point à la moyenne du circuit (en logit) est multiplié par k. k = 1 : inchangé. Réglage choisi
    sur 2024, jugé sur 2025 → (backtest_match_simule.choisir_reglage)."""
    if not k or k == 1.0:
        return c
    out = dict(c)
    for x in ('f', 'a', 'w1', 'd', 'w2j'):
        if x in c and x in moyen:
            m = _lg(min(max(moyen[x], 1e-4), 1 - 1e-4))
            out[x] = _sg(m + k * (_lg(min(max(c[x], 1e-4), 1 - 1e-4)) - m))
    return borner(out)


def melange(poids, p_elo, p_sim):
    """Combinaison simulation + Elo (backtest_match_simule.combinaison) : σ(a·logit p_elo + b·logit p_sim)."""
    z = poids['elo'] * _lg(min(max(p_elo, 1e-6), 1 - 1e-6)) + poids['simulation'] * _lg(min(max(p_sim, 1e-6), 1 - 1e-6))
    return _sg(max(min(z, 30), -30))


def appliquer_facteurs(c, d_service=0.0, d_aces=0.0, d_bp=0.0):
    """Facteurs du jour (facteurs.py) : décalages en logit des points gagnés au service (1re et 2e),
    des aces, et du point de service sur balle de break."""
    if not (d_service or d_aces or d_bp):
        return c
    out = dict(c, w1=_sg(_lg(c['w1']) + d_service), w2j=_sg(_lg(c['w2j']) + d_service), a=_sg(_lg(c['a']) + d_aces))
    out = borner(out)
    if d_bp:
        out['bp'] = c.get('bp', 0.0) + d_bp
    return out


def appliquer_reglages(c, reglages):
    """Réglages adoptés (reglage_match_simule.py) : facteur sur le taux d'aces."""
    if not reglages or not reglages.get('ace_facteur'):
        return c
    return borner(dict(c, a=c['a'] * reglages['ace_facteur']))


def simuler(cA, cB, p_victoire, sets_gagnants=2, n=5000, sigma=0.15, cle='', tb_final=None, garder=False,
            reglages=None):
    """Le match joué n fois. cA, cB : composantes « au niveau du profil » (avant ancrage).

    reglages (facultatif, 22/10/2026) : {'ace_facteur': x, 'tau_f': t} — aces recalés et
    % de 1re balle qui varie d'un match à l'autre (écart en logit tiré par joueur et par
    simulation, comme une forme du jour propre à la 1re balle).

    Renvoie un résumé : victoire, sets, scores complets, jeux, tie-breaks, feuille de stats
    (moyenne et fourchette 80 %) pour chaque joueur, match type. garder=True : renvoie aussi
    les feuilles brutes (pour les tests et le backtest)."""
    if tb_final is None:
        tb_final = 10 if sets_gagnants == 3 else 7
    cA, cB = appliquer_reglages(cA, reglages), appliquer_reglages(cB, reglages)
    tau_f = float((reglages or {}).get('tau_f') or 0.0)
    noeuds = noeuds_de_forme(cA, cB, p_victoire, sets_gagnants, sigma)
    cum, tot = [], 0.0
    for w, _, _ in noeuds:
        tot += w
        cum.append(tot)
    rnd = random.Random(graine(cle))
    vA, sets_c, scores_c, tbs, jeux = 0, {}, {}, 0, []
    set1A, remA, remB = 0, 0, 0
    F = [{k: [] for k in CLES_FEUILLE}, {k: [] for k in CLES_FEUILLE}]
    brut = []
    for _ in range(n):
        x = rnd.random() * tot
        j = 0
        while j < len(cum) - 1 and x > cum[j]:
            j += 1
        _, ca, cb = noeuds[j]
        if tau_f > 0:
            ca = dict(ca, f=min(max(_sg(_lg(ca['f']) + rnd.gauss(0, tau_f)), 0.3), 0.95))
            cb = dict(cb, f=min(max(_sg(_lg(cb['f']) + rnd.gauss(0, tau_f)), 0.3), 0.95))
        g, sets, st, br, ntb = un_match(ca, cb, sets_gagnants, tb_final, rnd, rnd.random() < 0.5)
        vA += g == 0
        a1 = sets[0][0] > sets[0][1]
        set1A += a1
        remA += g == 0 and not a1
        remB += g == 1 and a1
        ks = f"{sum(a > b for a, b in sets)}-{sum(b > a for a, b in sets)}"
        sets_c[ks] = sets_c.get(ks, 0) + 1
        sc = ' '.join(f"{a}-{b}" for a, b in sets)
        scores_c[sc] = scores_c.get(sc, 0) + 1
        tbs += ntb > 0
        jeux.append(sum(a + b for a, b in sets))
        fa, fb = feuille_derivee(st[0], st[1]), feuille_derivee(st[1], st[0])
        for k in CLES_FEUILLE:
            if fa[k] is not None:
                F[0][k].append(fa[k])
            if fb[k] is not None:
                F[1][k].append(fb[k])
        brut.append((sc, fa, fb, br, sets))
    resume = lambda v: {'moy': round(sum(v) / len(v), 2), 'p10': round(_quantile(v, 0.1), 1),
                        'p90': round(_quantile(v, 0.9), 1)} if v else None
    top = sorted(scores_c.items(), key=lambda kv: -kv[1])
    out = {'n': n, 'victoire_A': round(vA / n, 4), 'set1_A': round(set1A / n, 4),
           'remontee': [round(remA / n, 4), round(remB / n, 4)],
           'sets': {k: round(v / n, 4) for k, v in sorted(sets_c.items(), key=lambda kv: (-int(kv[0][0]), kv[0]))},
           'scores': [[s, round(c / n, 4)] for s, c in top[:5]],
           'jeux': resume(jeux), 'tiebreak': round(tbs / n, 3),
           'feuille': [{k: resume(F[i][k]) for k in CLES_FEUILLE} for i in (0, 1)],
           'match_type': match_type(brut, top[0][0] if top else None, F)}
    if garder:
        out['_brut'] = brut
    return out


def match_type(brut, score, F):
    """Parmi les simulations du score le plus fréquent, celle dont la feuille est la plus proche
    des médianes (écart normalisé par l'écart interquartile) : un match plausible, pas une moyenne."""
    if not score:
        return None
    med = [{k: _quantile(F[i][k], 0.5) for k in CLES_FEUILLE} for i in (0, 1)]
    eiq = [{k: max((_quantile(F[i][k], 0.75) or 0) - (_quantile(F[i][k], 0.25) or 0), 1.0) for k in CLES_FEUILLE}
           for i in (0, 1)]
    best, bd = None, None
    for sc, fa, fb, br, sets in brut:
        if sc != score:
            continue
        dist = 0.0
        for i, f in ((0, fa), (1, fb)):
            for k in ('aces', 'doubles_fautes', 'premiere_pct', 'gagnes_1re_pct', 'gagnes_2e_pct', 'breaks'):
                if f[k] is not None and med[i][k] is not None:
                    dist += ((f[k] - med[i][k]) / eiq[i][k]) ** 2
        if bd is None or dist < bd:
            best, bd = (sc, fa, fb, br, sets), dist
    sc, fa, fb, br, sets = best
    arr = lambda f: {k: (round(v, 1) if isinstance(v, float) else v) for k, v in f.items()}
    return {'score': sc, 'sets': [list(s) for s in sets], 'breaks': [list(b) for b in br],
            'feuille': [arr(fa), arr(fb)]}
