#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
forme_scores.py — la FORME du match selon le profil des deux joueurs (28/10/2026).

Constat (test du 28/10, profils de l'archive seule, appris sur juin → 15/09, jugés sur 2 468 matchs depuis le 16/09) :
les profils ne disent rien de plus sur le VAINQUEUR, mais un peu sur la forme du match — deux joueurs qui jouent
beaucoup de tie-breaks en jouent plus que ne le prévoit le modèle (+0,00104 de log-vraisemblance) ; deux joueurs
irréguliers font moins de matchs en 3 sets (+0,00140).

Méthode : la distribution exacte des scores (distribution_exacte.py) est INCLINÉE, à l'intérieur de chaque camp
(victoire de A, victoire de B), par
        poids(score) = exp( b_tb · f_tb · [au moins un tie-break] + (b_3s · f_3s + b_vol · f_vol) · [3 sets] )
puis renormalisée camp par camp : la probabilité de chaque vainqueur est STRICTEMENT inchangée.
  f_tb  = (tie-break % de A + tie-break % de B) − 72 %   (profil_rythme.py)
  f_3s  = (3 sets % de A + 3 sets % de B) − 70 %
  f_vol = régularité moyenne des deux (points de %) − 4,4
Un match dont un joueur n'a pas de profil n'est pas incliné.

RÈGLE FIXÉE LE 28/10/2026, AVANT TOUT RÉSULTAT DE CETTE PROCÉDURE : chaque semaine (facteurs.py), les trois
coefficients sont appris sur la fenêtre d'apprentissage (≤ 1 500 matchs au meilleur des 3, tirés au hasard, graine
fixe), avec des profils arrêtés au début de cette fenêtre ; puis jugés sur la fenêtre de jugement (6 dernières
semaines, profils arrêtés au début du jugement) par la log-vraisemblance de la forme réelle (camp gagnant ×
tie-break oui/non × 2 ou 3 sets). Adoptée si le gain est d'au moins 0,001, deux semaines de suite (stabilite.py).
"""
import math
import random

CENTRE_TB, CENTRE_3S, CENTRE_VOL = 0.72, 0.70, 4.4
MARGE = 0.001
MAX_APPR = 1500
SIGMA = 0.15
RIDGE = 1.0


def caracteristiques(pa, pb):
    """(f_tb, f_3s, f_vol) depuis deux profils (profil_rythme.py), ou None."""
    if not pa or not pb:
        return None
    try:
        f_tb = (pa['tiebreak_pct'] + pb['tiebreak_pct']) / 100 - CENTRE_TB
        f_3s = ((pa.get('trois_sets_pct') or 35.0) + (pb.get('trois_sets_pct') or 35.0)) / 100 - CENTRE_3S
        va = (pa.get('regularite') or {}).get('volatilite_pts')
        vb = (pb.get('regularite') or {}).get('volatilite_pts')
        f_vol = ((va if va is not None else CENTRE_VOL) + (vb if vb is not None else CENTRE_VOL)) / 2 - CENTRE_VOL
    except (KeyError, TypeError):
        return None
    return f_tb, f_3s, f_vol


def _cat(score):
    """(camp gagnant 0/1, tie-break, 3 sets ou plus) d'un score (tuple de sets vus de A)."""
    camp = 0 if score[-1][0] > score[-1][1] else 1
    tb = any(max(a, b) == 7 and min(a, b) == 6 for a, b in score)
    return camp, tb, len(score) >= 3


def _poids(cat, f, c):
    _, tb, trois = cat
    return math.exp(c[0] * f[0] * tb + (c[1] * f[1] + c[2] * f[2]) * trois)


def reponderer(distribution, f, coefs):
    """Distribution inclinée (même format {score: p}) ; masse de chaque camp conservée."""
    if not f or not coefs:
        return distribution
    brut, masse = {}, [0.0, 0.0]
    for s, p in distribution.items():
        cat = _cat(s)
        masse[cat[0]] += p
        brut[s] = p * _poids(cat, f, coefs)
    tot = [0.0, 0.0]
    for s, q in brut.items():
        tot[_cat(s)[0]] += q
    return {s: q * masse[_cat(s)[0]] / tot[_cat(s)[0]] if tot[_cat(s)[0]] else 0.0 for s, q in brut.items()}


# ------------------------------------------------------------------ apprentissage et jugement (chaque semaine)
def masses(distribution):
    """{(camp, tb, 3 sets): probabilité} — 8 cases."""
    out = {}
    for s, p in distribution.items():
        k = _cat(s)
        out[k] = out.get(k, 0.0) + p
    return out


def _proba_obs(m, obs, f, c):
    """P(observation) sous la distribution inclinée, depuis les 8 masses."""
    camp = obs[0]
    cote = [(k, v) for k, v in m.items() if k[0] == camp]
    tot_brut = sum(v for _, v in cote)
    tot_inc = sum(v * _poids(k, f, c) for k, v in cote) if f else tot_brut
    v_obs = m.get(obs, 0.0)
    if not tot_inc or not tot_brut:
        return 1e-9
    return max(tot_brut * v_obs * (_poids(obs, f, c) if f else 1.0) / tot_inc, 1e-9)


def log_vrais(D, c):
    """D : [(masses, observation, f)] ; log-vraisemblance moyenne (négative : plus petit = mieux)."""
    return -sum(math.log(_proba_obs(m, o, f, c)) for m, o, f in D) / len(D) if D else None


def apprendre(D, iterations=60, pas=0.5):
    """Trois coefficients par descente de gradient numérique (petit rappel vers 0)."""
    c = [0.0, 0.0, 0.0]
    D = [x for x in D if x[2]]
    if not D:
        return c

    def obj(cc):
        return log_vrais(D, cc) + RIDGE * sum(v * v for v in cc) / (2 * len(D))
    for _ in range(iterations):
        base = obj(c)
        g = []
        for i in range(3):
            cc = list(c)
            cc[i] += 1e-4
            g.append((obj(cc) - base) / 1e-4)
        nouveau = [ci - pas * gi * 10 for ci, gi in zip(c, g)]
        if obj(nouveau) < base:
            c = nouveau
        else:
            pas /= 2
            if pas < 1e-4:
                break
    return [round(v, 4) for v in c]


def observation(sets):
    """(camp, tb, 3 sets) d'un score réel [(jeux A, jeux B), …]."""
    return _cat(tuple(tuple(s) for s in sets))


def jeu_de_donnees(lignes, profils, scores_reels, max_n=None, graine=7):
    """[(masses, observation, f)] pour les matchs au meilleur des 3 avec score réel complet."""
    import distribution_exacte as DE
    import match_simule as S
    import modele as Mo
    L = [x for x in lignes if x.get('bo') == 3 and scores_reels.get(x.get('id'))]
    if max_n and len(L) > max_n:
        L = random.Random(graine).sample(L, max_n)
    out = []
    for x in L:
        sets = scores_reels[x['id']]
        ca, cb = x['srv'][0]['tx'], x['srv'][1]['tx']
        pv = Mo.match(S.p_service(ca), S.p_service(cb), 2)['victoire']
        d = DE.distribution_forme(ca, cb, 2, SIGMA, p_victoire=pv)
        out.append((masses(d), observation(sets), caracteristiques(profils.get(x['a']), profils.get(x['b']))))
    return out


def juger(appr, juge, profils_appr, profils_juge, scores_reels):
    """Rapport et verdict BRUT de la règle fixée (la stabilité est appliquée par l'appelant)."""
    Da = jeu_de_donnees(appr, profils_appr, scores_reels, MAX_APPR)
    Dj = jeu_de_donnees(juge, profils_juge, scores_reels)
    c = apprendre(Da)
    l0, l1 = log_vrais(Dj, [0.0, 0.0, 0.0]), log_vrais(Dj, c)
    gain = (l0 - l1) if l0 is not None and l1 is not None else None
    return {'coefs': c, 'apprentissage': len(Da), 'jugement': len(Dj),
            'documentes_jugement': sum(1 for x in Dj if x[2]),
            'log_vrais': {'sans': round(l0, 6) if l0 else None, 'avec': round(l1, 6) if l1 else None},
            'gain': round(gain, 6) if gain is not None else None,
            'adopte': bool(gain is not None and gain >= MARGE),
            'regle': ("forme réelle (camp × tie-break × 3 sets) mieux prédite d'au moins 0,001 sur le jugement ; "
                      "vainqueur inchangé par construction ; deux semaines de suite")}
