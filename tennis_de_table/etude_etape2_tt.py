#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_etape2_tt.py — TENNIS DE TABLE, ÉTAPE 2 : PENTE PAR LIGUE ET SIMULATION AUX POINTS (27/11/2026, paquet 494,
Lucas : « fais ça pour le tennis de table »).

Point de départ (étude 487, rapport_elo_tt.json) : l'Elo E2 (K = 400 / (n + 5)^0,6, cible = moitié résultat, moitié part
de points, échelle 20) tient dans l'ensemble (log loss 0,668, 58,2 % de bons vainqueurs, pente 1,03) mais pas ligue par
ligue : trop timide chez les pros (International : pente 1,34 ; Allemagne 1,43), trop sûr de lui en Russie (0,79) et
en Biélorussie (0,65). Un seul Elo pour tout le monde, réglé surtout sur les ligues de volume.

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI. Mêmes périodes que l'étude 487 : les 120 premiers jours lancent les
classements, APPRENTISSAGE jusqu'au 30/09/2025, JUGEMENT une seule fois du 01/10/2025 au dernier jour. Base : E2 avec
ses réglages appris en 487 (lus dans rapport_elo_tt.json, jamais réappris ici).

  A. PENTE PAR LIGUE. Pour chaque ligue, a appris sur l'apprentissage : % corrigé = σ(a · logit p_E2). Retenue dans une
     ligue si, sur au moins 1 000 matchs jugés, le gain de log loss contre E2 atteint 0,001 ET 2 erreurs types, ET si
     le a réappris sur le jugement est du même côté de 1 (même sens). Ligue par ligue.

  B. SIMULATION AUX POINTS. Un second Elo, aux points : chaque joueur a une force « au point » ; la probabilité de gagner
     un point est q = 1 / (1 + 10^(−(Rh − Ra) / 400)) ; après le match, Rh += K · (part de points réelle − q) (et
     l'inverse pour l'adversaire), K = a / (n + 5)^c avec a ∈ {200, 400, 800, 1600}, c ∈ {0,3 ; 0,45 ; 0,6}, réglé sur
     l'apprentissage. Le % du match se calcule ensuite exactement : manches à 11 points (2 d'écart, 10-10 réglé par la
     formule de l'égalité), match en 3 ou 4 manches gagnantes (format lu dans le nombre de manches du vainqueur, connu
     avant le match). Comparée à E2 avec les mêmes règles qu'en A (≥ 1 000 matchs, ≥ 0,001 et 2 erreurs types, même
     sens quand on inverse les périodes), toutes ligues puis ligue par ligue. Publié sans décider : le score en manches
     annoncé contre réel (le plus probable des scores de la simulation).

  C. LIGUES DU PRODUIT (choix de Lucas, 26/11) : International et Pologne. Leur verdict est mis en avant ; Setka (Ukraine),
     Liga Pro (Tchéquie), Russie et Biélorussie sont jugées mais ne sont pas visées par le service.
Rien n'est publié sur le site. Rapport : tennis_de_table/rapport_etape2_tt.json (comptes et moyennes, aucun nom).
Usage : python tennis_de_table/etude_etape2_tt.py [racine]
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo_tt as ET  # noqa: E402
import etude_elo_tt as EE  # noqa: E402

PAQUET = 494
RAPPORT_487 = os.path.join(ICI, 'rapport_elo_tt.json')
SORTIE = os.path.join(ICI, 'rapport_etape2_tt.json')
GRILLE_POINTS = [(a, c) for a in (200, 400, 800, 1600) for c in (0.3, 0.45, 0.6)]
LIGUES_PRODUIT = ('International', 'Poland')
MIN_JUGES, MARGE, ERREURS_TYPES = 1000, 0.001, 2.0


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _ll(p, y):
    p = min(max(p, 1e-9), 1 - 1e-9)
    return -math.log(p if y else 1 - p)


# ------------------------------------------------------------------ du point à la manche, de la manche au match
C = [[math.comb(n, k) for k in range(n + 1)] for n in range(25)]


def p_manche(q):
    """Probabilité de gagner une manche à 11 points (2 d'écart) en gagnant chaque point avec la probabilité q."""
    r = 1 - q
    p = sum(C[10 + k][k] * q ** 11 * r ** k for k in range(10))
    egalite = C[20][10] * q ** 10 * r ** 10
    return p + egalite * (q * q / (q * q + r * r) if q * q + r * r > 0 else 0.5)


def p_match(g, n):
    """Probabilité de gagner un match en n manches gagnantes quand on gagne chaque manche avec la probabilité g."""
    h = 1 - g
    return sum(C[n - 1 + k][k] * g ** n * h ** k for k in range(n))


def scores_manches(g, n):
    """{(manches h, manches a): probabilité} pour un match en n manches gagnantes."""
    h = 1 - g
    out = {}
    for k in range(n):
        out[(n, k)] = C[n - 1 + k][k] * g ** n * h ** k
        out[(k, n)] = C[n - 1 + k][k] * h ** n * g ** k
    return out


_MEMO = {}


def p_match_de_q(q, n):
    """p_match(p_manche(q), n), mémorisé à 1/10 000 près de q (plus d'un million de matchs par passage)."""
    k = (round(q, 4), n)
    v = _MEMO.get(k)
    if v is None:
        v = _MEMO[k] = p_match(p_manche(k[0]), n)
    return v


def rejouer_points(M, a, c):
    """[(p_match_h, q, n)] avant chaque match, Elo aux points."""
    R, N, out = {}, {}, []
    for m in M:
        h, b, sp, n = m[3], m[4], m[6], m[7]
        rh, rb = R.get(h, ET.DEPART), R.get(b, ET.DEPART)
        q = 1.0 / (1.0 + 10 ** (-(rh - rb) / 400.0))
        out.append((p_match_de_q(q, n), q, n))
        nh, nb = N.get(h, 0), N.get(b, 0)
        d = sp - q
        R[h] = rh + a / (nh + 5) ** c * d
        R[b] = rb - a / (nb + 5) ** c * d
        N[h], N[b] = nh + 1, nb + 1
    return out


# ------------------------------------------------------------------ mesures
def comparer(Pb, Pc, Y, idx):
    """Gain moyen de log loss (base − candidat) et son erreur type."""
    d = [_ll(Pb[i], Y[i]) - _ll(Pc[i], Y[i]) for i in idx]
    n = len(d)
    if not n:
        return {'matchs': 0}
    g = sum(d) / n
    et = math.sqrt(sum((x - g) ** 2 for x in d) / max(n - 1, 1)) / math.sqrt(n)
    return {'matchs': n, 'gain': round(g, 5), 'erreur_type': round(et, 5)}


def passe(cmp_j, meme_sens):
    return bool(cmp_j.get('matchs', 0) >= MIN_JUGES and cmp_j.get('gain', 0) >= MARGE
                and cmp_j.get('gain', 0) >= ERREURS_TYPES * cmp_j.get('erreur_type', 1) and meme_sens)


def pente(P, Y, idx):
    return ET.pente(P, Y, idx) if idx else 1.0


def etudier(M, reglage_e2, journal=print):
    Y = [m[5] for m in M]
    A, B = EE.periodes(M)
    if len(A) < MIN_JUGES or len(B) < MIN_JUGES:
        journal(f'pas assez de matchs (apprentissage {len(A)}, jugement {len(B)})')
        return {'verdict': 'donnees_insuffisantes'}
    a, c, w, s = reglage_e2
    P = ET.rejouer(M, a=a, c=c, w=w, s=s)
    ligues = sorted({M[i][2] for i in A + B})
    LA = {lg: [i for i in A if M[i][2] == lg] for lg in ligues}
    LB = {lg: [i for i in B if M[i][2] == lg] for lg in ligues}

    # A. pente par ligue
    pentes = {}
    Pp = list(P)
    for lg in ligues:
        aA, aB = pente(P, Y, LA[lg]), pente(P, Y, LB[lg])
        Pc = {i: _sg(aA * _lg(P[i])) for i in LB[lg]}
        cmp_j = comparer(P, Pc, Y, LB[lg])
        ok = passe(cmp_j, (aA - 1) * (aB - 1) > 0)
        pentes[lg] = {'pente_apprise': round(aA, 3), 'pente_reapprise_sur_jugement': round(aB, 3),
                      'apprentissage': len(LA[lg]), 'jugement': cmp_j, 'retenue': ok}
        if ok:
            for i in LB[lg]:
                Pp[i] = Pc[i]
    # B. simulation aux points
    meilleur = None
    for g in GRILLE_POINTS:
        Q = rejouer_points(M, *g)
        ll = sum(_ll(Q[i][0], Y[i]) for i in A) / len(A)
        if meilleur is None or ll < meilleur[1]:
            meilleur = (g, ll, Q)
    gA, llA, Q = meilleur
    inverse = None
    for g in GRILLE_POINTS:                                  # réglé sur le jugement, pour le sens inverse
        Q2 = rejouer_points(M, *g)
        ll = sum(_ll(Q2[i][0], Y[i]) for i in B) / len(B)
        if inverse is None or ll < inverse[1]:
            inverse = (g, ll, Q2)
    PQ = [x[0] for x in Q]
    PQ2 = [x[0] for x in inverse[2]]
    sens_inverse = (sum(_ll(P[i], Y[i]) for i in A) - sum(_ll(PQ2[i], Y[i]) for i in A)) / len(A)
    global_j = comparer(P, PQ, Y, B)
    points = {'reglage_appris': list(gA), 'reglage_reappris_sur_jugement': list(inverse[0]),
              'toutes_ligues': dict(global_j, sens_inverse=round(sens_inverse, 5),
                                    retenue=passe(global_j, sens_inverse > 0)),
              'par_ligue': {}}
    for lg in ligues:
        cj = comparer(P, PQ, Y, LB[lg])
        si = (sum(_ll(P[i], Y[i]) for i in LA[lg]) - sum(_ll(PQ2[i], Y[i]) for i in LA[lg])) / len(LA[lg]) if LA[lg] else 0.0
        points['par_ligue'][lg] = dict(cj, sens_inverse=round(si, 5), retenue=passe(cj, si > 0))
    # score en manches annoncé (le plus probable de la simulation aux points) contre réel, sur le jugement — descriptif
    sc_ok = {}
    for i in B:
        q, n = Q[i][1], Q[i][2]
        sc = scores_manches(p_manche(q), n)
        prevu = max(sc, key=sc.get)
        lg = M[i][2]
        t = sc_ok.setdefault(lg, [0, 0, 0.0])
        t[0] += 1
        t[1] += prevu == tuple(M[i][8])
        t[2] += sc.get(tuple(M[i][8]), 0.0)
    points['score_en_manches'] = {lg: {'matchs': v[0], 'score_le_plus_probable_juste_pct': round(100 * v[1] / v[0], 1),
                                       'proba_moyenne_du_score_reel_pct': round(100 * v[2] / v[0], 1)}
                                  for lg, v in sc_ok.items()}
    # D. bilan par ligue avec la meilleure combinaison retenue
    resume = {}
    for lg in ligues:
        J = LB[lg]
        if not J:
            continue
        cand = PQ if points['par_ligue'][lg]['retenue'] else Pp
        resume[lg] = {'matchs': len(J), 'modele': 'points' if points['par_ligue'][lg]['retenue'] else
                      ('E2 + pente' if pentes[lg]['retenue'] else 'E2'),
                      'log_loss': round(sum(_ll(cand[i], Y[i]) for i in J) / len(J), 5),
                      'bons_vainqueurs_pct': round(100 * sum(1 for i in J if (cand[i] >= 0.5) == bool(Y[i])) / len(J), 1),
                      'pente_restante': round(pente(cand, Y, J), 3), 'produit': lg in LIGUES_PRODUIT}
    rep = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'paquet': PAQUET,
           'base_E2': list(reglage_e2), 'apprentissage': len(A), 'jugement': len(B),
           'A_pente_par_ligue': pentes, 'B_simulation_aux_points': points, 'bilan_par_ligue': resume,
           'ligues_produit': list(LIGUES_PRODUIT)}
    journal(f"étape 2 : {len(M)} matchs, apprentissage {len(A)}, jugement {len(B)}, base E2 {tuple(reglage_e2)}")
    for lg, v in pentes.items():
        j = v['jugement']
        journal(f"  A {lg} : pente {v['pente_apprise']} (réapprise {v['pente_reapprise_sur_jugement']}), {j.get('matchs')} jugés, "
                f"gain {j.get('gain')} ± {j.get('erreur_type')}{' → retenue' if v['retenue'] else ''}")
    t = points['toutes_ligues']
    journal(f"  B points {tuple(gA)} : toutes ligues {t['matchs']} jugés, gain {t['gain']} ± {t['erreur_type']}, "
            f"sens inverse {t['sens_inverse']}{' → retenue' if t['retenue'] else ''}")
    for lg, v in points['par_ligue'].items():
        journal(f"  B {lg} : {v.get('matchs')} jugés, gain {v.get('gain')} ± {v.get('erreur_type')}, sens inverse "
                f"{v['sens_inverse']}{' → retenue' if v['retenue'] else ''}")
    for lg, v in resume.items():
        journal(f"  bilan {lg}{' (produit)' if v['produit'] else ''} : {v['modele']}, {v['matchs']} matchs, log loss "
                f"{v['log_loss']}, bons vainqueurs {v['bons_vainqueurs_pct']} %, pente restante {v['pente_restante']}")
    return rep


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    with open(RAPPORT_487, encoding='utf-8') as f:
        e2 = json.load(f)['reglages_appris']['E2']['reglage']
    M = ET.matchs(racine)
    rep = etudier(M, e2)
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
