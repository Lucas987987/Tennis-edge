#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_fatigue_tt.py — TENNIS DE TABLE : FATIGUE ET FORME DU JOUR (27/11/2026, paquet 503, Lucas : « fais les 4 »).

Pourquoi : en Pologne (TT Elite Series) un joueur dispute jusqu'à 5 ou 6 matchs dans la même journée. L'Elo se met à
jour après chaque match, mais il peut manquer ce qui se joue à l'échelle de la journée : la fatigue (matchs déjà
joués), la forme du jour (résultat du match précédent) et le repos (temps depuis le match précédent).

TÉMOIN = le % en production : Elo E2 (réglage lu dans rapport_elo_tt.json, jamais réappris ici), puis, pour les ligues
dont la pente a été retenue à l'étape 2 (lues dans rapport_etape2_tt.json), % = σ(pente · logit p).

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI. Mêmes périodes que 487, 494 et 496 (120 jours de lancement, APPRENTISSAGE
jusqu'au 30/09/2025, JUGEMENT une seule fois du 01/10/2025 au dernier jour).
  TRAITS, calculés pour chaque joueur avec les seuls matchs commencés STRICTEMENT AVANT le début t du match (deux matchs
  au même t ne se voient pas), dans la même journée UTC (le jour du fichier de collecte) :
    x1 = matchs déjà joués ce jour-là, h moins a ;
    x2 = résultat du match précédent du jour (+1 victoire, −1 défaite, 0 s'il n'y en a pas), h moins a ;
    x3 = repos : minutes depuis le début du match précédent du jour, plafonnées à 180 (180 s'il n'y en a pas),
         h moins a, divisé par 60.
  CANDIDAT : logit(p') = logit(p_témoin) + b1·x1 + b2·x2 + b3·x3. Les trois coefficients sont appris ligue par ligue,
  par maximum de vraisemblance (Newton, 25 itérations au plus), sur l'apprentissage seulement. Si la ligue compte moins
  de 200 matchs appris, ou si la matrice de Newton est singulière (un trait toujours nul), les coefficients restent à 0
  (pas de candidat).
  RETENU dans une ligue seulement si, sur au moins 1 000 matchs jugés de cette ligue :
    1. le gain de log loss contre le témoin atteint 0,001 ET 2 erreurs types (différences appariées match par match) ;
    2. MÊME SENS : le candidat réappris sur le jugement et appliqué à l'apprentissage bat aussi le témoin (gain > 0) ;
    3. chaque coefficient NET garde le même signe sur les deux périodes (appris sur l'apprentissage et réappris sur le
       jugement) ; « net » = effet d'au moins 0,02 en logit pour un écart type du trait sur l'apprentissage
       (|b| · écart type ≥ 0,02). Précision du 27/11, avant tout essai : un coefficient quasi nul change de signe par
       simple bruit et ne doit pas bloquer un vrai gain (vu sur données factices) ; il faut au moins un coefficient net.
  Ligues du produit (choix de Lucas) : International et Pologne, jugées séparément. Les autres ligues sont décrites
  mais ne sont JAMAIS « retenues ».
  Publié sans décider : les trois coefficients, le gain de chaque trait utilisé seul (un seul coefficient appris sur
  l'apprentissage, jugé sur le jugement), et le % annoncé du favori (témoin) contre le % réel selon le nombre de matchs
  déjà joués ce jour-là par le favori (0, 1, 2, 3, 4 et plus).
Rapport : tennis_de_table/rapport_fatigue_tt.json (comptes et moyennes, aucun nom, aucun identifiant). Rien n'est
publié sur le site ; le % en production ne change pas tant que Lucas ne l'a pas décidé.
Usage : python tennis_de_table/etude_fatigue_tt.py [racine]
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
import etude_etape3_tt as E3  # noqa: E402

PAQUET = 503
RAPPORT_487 = os.path.join(ICI, 'rapport_elo_tt.json')
SORTIE = os.path.join(ICI, 'rapport_fatigue_tt.json')
LIGUES_PRODUIT = ('International', 'Poland')
MIN_JUGES, MIN_APPRIS, MARGE, ERREURS_TYPES = 1000, 200, 0.001, 2.0
REPOS_MAX_MIN, ITERS = 180.0, 25
NOMS = ('b1_matchs_deja_joues', 'b2_resultat_precedent', 'b3_repos_heures')
TRANCHES_DEJA = ('0', '1', '2', '3', '4+')


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


# ------------------------------------------------------------------ traits du jour (sans regarder devant)
def _vu(etat, joueur, jour, t):
    """(matchs déjà joués ce jour, résultat du précédent, repos en minutes) pour un joueur, avant le match à t."""
    e = etat.get(joueur)
    if not e or e[0] != jour:
        return 0, 0, REPOS_MAX_MIN
    return e[1], e[2], min(max((t - e[3]) / 60.0, 0.0), REPOS_MAX_MIN)


def traits(M):
    """Pour chaque match de M (trié par début) : (x1, x2, x3, déjà joués par h, déjà joués par a).
    Les matchs qui commencent au même t sont lus ensemble AVANT d'être inscrits : ils ne se voient pas."""
    etat, out, i, n = {}, [], 0, len(M)
    while i < n:
        j = i
        while j < n and M[j][0] == M[i][0]:
            j += 1
        for m in M[i:j]:
            nh, rh, sh = _vu(etat, m[3], m[1], m[0])
            na, ra, sa = _vu(etat, m[4], m[1], m[0])
            out.append((nh - na, rh - ra, (sh - sa) / 60.0, nh, na))
        for m in M[i:j]:
            for joueur, gagne in ((m[3], m[5] == 1), (m[4], m[5] == 0)):
                e = etat.get(joueur)
                deja = e[1] if e and e[0] == m[1] else 0
                etat[joueur] = (m[1], deja + 1, 1 if gagne else -1, m[0])
        i = j
    return out


# ------------------------------------------------------------------ apprentissage (Newton)
def _resoudre(H, g):
    """Résout H·x = g (pivot de Gauss) ; None si la matrice est singulière."""
    k = len(g)
    A = [list(H[i]) + [g[i]] for i in range(k)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(A[r][c]))
        if abs(A[p][c]) < 1e-9:
            return None
        A[c], A[p] = A[p], A[c]
        for r in range(k):
            if r != c:
                f = A[r][c] / A[c][c]
                for u in range(c, k + 1):
                    A[r][u] -= f * A[c][u]
    return [A[i][k] / A[i][i] for i in range(k)]


def apprendre(L, actifs=(0, 1, 2)):
    """L = [(logit témoin, (x1, x2, x3), y)] → [b1, b2, b3] (0 pour les traits non actifs), maximum de vraisemblance."""
    b = [0.0, 0.0, 0.0]
    if len(L) < MIN_APPRIS:
        return b
    k = len(actifs)
    for _ in range(ITERS):
        g = [0.0] * k
        H = [[0.0] * k for _ in range(k)]
        for z, x, y in L:
            for j in actifs:
                z += b[j] * x[j]
            q = 1 / (1 + math.exp(-max(min(z, 30), -30)))
            e, w = y - q, q * (1 - q)
            for u in range(k):
                xu = x[actifs[u]]
                if xu:
                    g[u] += e * xu
                    wx = w * xu
                    for v in range(u, k):
                        H[u][v] += wx * x[actifs[v]]
        for u in range(k):
            for v in range(u):
                H[u][v] = H[v][u]
        pas = _resoudre(H, g)
        if pas is None:
            return [0.0, 0.0, 0.0]
        for u in range(k):
            b[actifs[u]] += pas[u]
        if max(abs(x) for x in pas) < 1e-7:
            break
    return b


def _perte(z, y):
    p = min(max(_sg(z), 1e-6), 1 - 1e-6)
    return -math.log(p) if y else -math.log(1 - p)


def comparer(L, b):
    """Gain de log loss du candidat (coefficients b) contre le témoin, différences appariées match par match."""
    if not L:
        return {'matchs': 0}
    d, base = [], 0.0
    for z, x, y in L:
        t = _perte(z, y)
        base += t
        d.append(t - _perte(z + b[0] * x[0] + b[1] * x[1] + b[2] * x[2], y))
    g = sum(d) / len(d)
    et = math.sqrt(sum((x - g) ** 2 for x in d) / max(len(d) - 1, 1)) / math.sqrt(len(d))
    return {'matchs': len(d), 'log_loss_temoin': round(base / len(d), 5), 'log_loss_candidat': round(base / len(d) - g, 5),
            'gain': round(g, 5), 'erreur_type': round(et, 5)}


EFFET_NET = 0.02


def ecarts_types(L):
    n = len(L)
    if n < 2:
        return [0.0, 0.0, 0.0]
    out = []
    for j in range(3):
        m = sum(x[j] for _, x, _ in L) / n
        out.append(math.sqrt(sum((x[j] - m) ** 2 for _, x, _ in L) / (n - 1)))
    return out


def meme_signe(b1, b2, ecarts=(1.0, 1.0, 1.0)):
    """Chaque coefficient net (|b1| · écart type ≥ EFFET_NET) garde son signe ; au moins un coefficient net."""
    nets = [j for j in range(len(b1)) if abs(b1[j]) * ecarts[j] >= EFFET_NET]
    return bool(nets) and all(b1[j] * b2[j] > 0 for j in nets)


# ------------------------------------------------------------------ étude
def temoin(M, reglage_e2, pentes):
    """Le % en production : Elo E2, puis la pente des ligues retenues à l'étape 2."""
    a, c, w, s = reglage_e2
    P = ET.rejouer(M, a=a, c=c, w=w, s=s)
    for i, m in enumerate(M):
        k = pentes.get(m[2])
        if k:
            P[i] = _sg(k * _lg(P[i]))
    return P


def lignes(M, P, X, idx):
    """{ligue: [(logit témoin, (x1, x2, x3), y)]} sur les indices idx."""
    out = {}
    for i in idx:
        out.setdefault(M[i][2], []).append((_lg(P[i]), X[i][:3], M[i][5]))
    return out


def table_favori(M, P, X, idx):
    """Favori du témoin : % annoncé contre % réel selon ses matchs déjà joués ce jour-là (0, 1, 2, 3, 4+)."""
    T = {}
    for i in idx:
        fav_h = P[i] >= 0.5
        k = min(X[i][3] if fav_h else X[i][4], 4)
        t = T.setdefault(k, [0, 0.0, 0])
        t[0] += 1
        t[1] += P[i] if fav_h else 1 - P[i]
        t[2] += 1 if fav_h == bool(M[i][5]) else 0
    return {TRANCHES_DEJA[k]: {'matchs': t[0], 'favori_annonce_pct': round(100 * t[1] / t[0], 1),
                               'favori_reel_pct': round(100 * t[2] / t[0], 1)} for k, t in sorted(T.items())}


def etudier(M, reglage_e2, pentes, journal=print):
    A, B = EE.periodes(M)
    if len(A) < MIN_JUGES or len(B) < MIN_JUGES:
        journal(f'pas assez de matchs (apprentissage {len(A)}, jugement {len(B)})')
        return {'verdict': 'donnees_insuffisantes', 'paquet': PAQUET, 'apprentissage': len(A), 'jugement': len(B)}
    P = temoin(M, reglage_e2, pentes)
    X = traits(M)
    LA, LB = lignes(M, P, X, A), lignes(M, P, X, B)
    res = {}
    for lg in sorted(LB):
        la, lb = LA.get(lg, []), LB[lg]
        produit = lg in LIGUES_PRODUIT
        bA, bB = apprendre(la), apprendre(lb)
        cj, inv = comparer(lb, bA), comparer(la, bB)
        signes = meme_signe(bA, bB, ecarts_types(la))
        ok = bool(produit and cj['matchs'] >= MIN_JUGES and cj['gain'] >= MARGE
                  and cj['gain'] >= ERREURS_TYPES * cj['erreur_type'] and inv.get('gain', 0) > 0 and signes)
        seuls = {}
        for j, nom in enumerate(NOMS):
            bj = apprendre(la, (j,))
            c1 = comparer(lb, bj)
            seuls[nom] = {'coefficient': round(bj[j], 4), 'gain': c1['gain'], 'erreur_type': c1['erreur_type']}
        res[lg] = {'produit': produit, 'apprentissage': len(la), 'jugement': cj,
                   'coefficients_appris': {n: round(v, 4) for n, v in zip(NOMS, bA)},
                   'coefficients_reappris_sur_jugement': {n: round(v, 4) for n, v in zip(NOMS, bB)},
                   'meme_signe': signes, 'sens_inverse': inv.get('gain'), 'retenu': ok,
                   'chaque_trait_seul': seuls,
                   'favori_selon_matchs_deja_joues': table_favori(M, P, X, [i for i in B if M[i][2] == lg])}
    rep = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'paquet': PAQUET,
           'base_E2': list(reglage_e2), 'pentes_par_ligue': pentes, 'apprentissage': len(A), 'jugement': len(B),
           'ligues_produit': list(LIGUES_PRODUIT), 'par_ligue': res,
           'retenu_dans': [lg for lg in LIGUES_PRODUIT if res.get(lg, {}).get('retenu')],
           'verdict': 'retenu' if any(res.get(lg, {}).get('retenu') for lg in LIGUES_PRODUIT) else 'non_retenu'}
    journal(f"fatigue : {len(M)} matchs, apprentissage {len(A)}, jugement {len(B)}, pentes {pentes}")
    for lg in sorted(res, key=lambda k: (not res[k]['produit'], k)):
        v = res[lg]
        j = v['jugement']
        journal(f"  {lg}{' (produit)' if v['produit'] else ' (décrite, jamais retenue)'} : appris {v['apprentissage']}, "
                f"jugés {j['matchs']}, log loss témoin {j['log_loss_temoin']} → candidat {j['log_loss_candidat']}, "
                f"gain {j['gain']} ± {j['erreur_type']}, sens inverse {v['sens_inverse']}, "
                f"même signe {'oui' if v['meme_signe'] else 'non'}{' → RETENU' if v['retenu'] else ' → non retenu'}")
        journal('      coefficients appris / réappris : ' + ' ; '.join(
            f"{n} {v['coefficients_appris'][n]} / {v['coefficients_reappris_sur_jugement'][n]}" for n in NOMS))
        journal('      chaque trait seul (descriptif) : ' + ' ; '.join(
            f"{n} {s['coefficient']} gain {s['gain']} ± {s['erreur_type']}" for n, s in v['chaque_trait_seul'].items()))
        if v['produit']:
            journal('      favori annoncé/réel selon ses matchs déjà joués ce jour : ' + ' ; '.join(
                f"{k} ({t['matchs']}) {t['favori_annonce_pct']}/{t['favori_reel_pct']}"
                for k, t in v['favori_selon_matchs_deja_joues'].items()))
    journal(f"  verdict : {rep['verdict']} {rep['retenu_dans']}")
    return rep


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    with open(RAPPORT_487, encoding='utf-8') as f:
        e2 = json.load(f)['reglages_appris']['E2']['reglage']
    M = ET.matchs(racine)
    rep = etudier(M, e2, E3.pentes_retenues())
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
