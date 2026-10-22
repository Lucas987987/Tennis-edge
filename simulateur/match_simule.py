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


def victoire(pA, pB, sets_gagnants=2, tb_final=None):
    """P(A gagne le match) seule — même calcul que modele.match()['victoire'], sans suivre les jeux
    (états : sets et serveur), donc bien plus rapide pour l'ancrage."""
    if tb_final is None:
        tb_final = 10 if sets_gagnants == 3 else 7
    tot = 0.0
    for a_premier in (True, False):
        etats = {(0, 0, a_premier): 0.5}
        while etats:
            nouv = {}
            for (sa, sb, srv), pr in etats.items():
                decisif = sa == sets_gagnants - 1 and sb == sets_gagnants - 1
                for a, b, x in M.set_issues(pA, pB, srv, tb_final if decisif else 7):
                    na, nb = sa + (a > b), sb + (b > a)
                    m = pr * x
                    if na == sets_gagnants:
                        tot += m
                    elif nb < sets_gagnants:
                        k = (na, nb, srv if (a + b) % 2 == 0 else not srv)
                        nouv[k] = nouv.get(k, 0.0) + m
            etats = nouv
    return tot


def ancrer_rapide(pA, pB, p_cible, sets_gagnants=2, sigma=0.0, iterations=30):
    """Comme modele.ancrer_forme (même mélange de forme, mêmes 13 nœuds), avec victoire() rapide."""
    la, lb = _lg(pA), _lg(pB)
    noeuds = [(0.0, 1.0)] if sigma <= 0 else [(sigma * z, w) for z, w in zip(M._Z, M._W)]
    lo, hi = -6.0, 6.0
    for _ in range(iterations):
        d = (lo + hi) / 2
        v = sum(w * victoire(_sg(la + d + dz), _sg(lb - d - dz), sets_gagnants) for dz, w in noeuds)
        if v < p_cible:
            lo = d
        else:
            hi = d
    d = (lo + hi) / 2
    return _sg(la + d), _sg(lb - d)


def noeuds_de_forme(cA, cB, p_victoire, sets_gagnants, sigma):
    """[(poids, composantes A, composantes B)] : niveau ancré sur p_victoire APRÈS la forme du jour
    (mêmes 13 nœuds que modele.match_forme). Le hasard de la simulation tire un nœud par match."""
    pA0, pB0 = p_service(cA), p_service(cB)
    a, b = ancrer_rapide(pA0, pB0, min(max(p_victoire, 0.005), 0.995), sets_gagnants, sigma)
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
    st = [[0] * 12, [0] * 12]
    r = rnd.random
    sets, ss, breaks, ntb = [], [0, 0], [], 0
    srv = 0 if a_sert else 1

    def point(s):
        f, a, w1, d, w2j = P[s]
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
                if point(s):
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
    out = {'n': n, 'victoire_A': round(vA / n, 4),
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
