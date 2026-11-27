#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_peu_connus_tt.py — TENNIS DE TABLE : LES JOUEURS PEU CONNUS (27/11/2026, paquet 503, Lucas : « fais les 4 »).

Pourquoi : beaucoup de joueurs de l'International ont peu de matchs dans l'historique ; un nouveau joueur part à
1 500 d'Elo, son % peut donc être mal étalonné. La page affiche déjà « Matchs suivis par l'algo : n_h et n_a ». Deux
questions : faut-il prévenir « peu de matchs » (permis SEULEMENT si l'étude montre que le % est moins fiable), et
peut-on corriger le % ?

Témoin = le % de production : Elo E2 (étude 487, réglage lu dans rapport_elo_tt.json), puis la pente de la ligue quand
elle a été retenue (étape 2, paquet 494, lue dans rapport_etape2_tt.json) : p = σ(pente · logit p).
n_min = le plus petit des deux compteurs « matchs déjà joués » (celui de l'Elo E2, tous matchs gardés depuis le premier
jour, toutes ligues) des deux joueurs AVANT le match. Classes fixées ici : moins de 10, 10 à 29, 30 à 99, 100 et plus.

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI. Mêmes périodes que 487, 494 et 496 (120 jours de lancement, apprentissage
jusqu'au 30/09/2025, JUGEMENT une seule fois du 01/10/2025 au dernier jour). Ligue par ligue ; seules les ligues du
produit (International et Pologne) peuvent être « retenues », les autres sont décrites sans décider.
  Q1. DESCRIPTIF (sur le jugement, par ligue et par classe) : matchs, log loss, Brier, % de bons vainqueurs, pente
      d'étalonnage du témoin, favori annoncé contre réel. Une classe est « MOINS FIABLE » si elle compte au moins
      300 matchs jugés ET si sa pente d'étalonnage sort de [0,85 ; 1,15] sur les DEUX périodes, du même côté (les deux
      sous 0,85 ou les deux au-dessus de 1,15). L'avertissement « peu de matchs » sur la page n'est permis que pour une
      classe « moins fiable » d'une ligue du produit.
  Q2. CORRECTION : candidat = une pente par classe, logit(p') = s_classe · logit(p_témoin), s_classe apprise par
      maximum de vraisemblance sur l'apprentissage, par ligue et par classe (classe de moins de 200 matchs sur la
      période d'apprentissage : s = 1). RETENU pour une ligue du produit seulement si, sur au moins 1 000 matchs jugés
      de la ligue : la log loss baisse d'au moins 0,001 par rapport au témoin ET d'au moins 2 erreurs types
      (différences match par match, appariées), ET « même sens » : le candidat réappris sur le jugement et appliqué à
      l'apprentissage bat aussi le témoin (gain > 0), ET les pentes réapprises sur le jugement sont du même côté de 1
      que celles de l'apprentissage pour chaque classe d'au moins 300 matchs dans les deux périodes dont la pente
      apprise s'écarte de 1 d'au moins 0,05 (précision du 27/11, avant tout essai : une classe déjà bien étalonnée a
      une pente proche de 1 qui change de côté par simple bruit, vu sur données factices ; elle ne doit pas bloquer un
      vrai gain). S'il n'existe aucune classe de ce genre, le sens n'est pas vérifiable : pas retenu.
  Le vainqueur annoncé ne change dans aucun cas (une pente positive garde le favori).
Rapport : tennis_de_table/rapport_peu_connus_tt.json (comptes et moyennes, aucun nom, aucun identifiant). Rien n'est
publié sur le site.
Usage : python tennis_de_table/etude_peu_connus_tt.py [racine]
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
SORTIE = os.path.join(ICI, 'rapport_peu_connus_tt.json')
LIGUES_PRODUIT = ('International', 'Poland')
BORNES = (10, 30, 100)
CLASSES = ('moins de 10', '10 à 29', '30 à 99', '100 et plus')
MIN_JUGES, MARGE, ERREURS_TYPES = 1000, 0.001, 2.0
MIN_CLASSE_JUGEE, MIN_CLASSE_APPRISE, MIN_CLASSE_SENS = 300, 200, 300
PENTE_MIN, PENTE_MAX = 0.85, 1.15
ECART_SENS = 0.05                 # Q2 : seules les classes dont la pente apprise s'écarte de 1 d'au moins 0,05 comptent
MIN_PENTE = 30          # en dessous, la pente d'étalonnage n'est pas calculée (descriptif seulement)


def classe(n_min):
    """Indice de la classe de n_min : 0 (< 10), 1 (10–29), 2 (30–99), 3 (≥ 100)."""
    return sum(1 for b in BORNES if n_min >= b)


def compteurs(M):
    """n_min avant chaque match : le plus petit des deux compteurs de l'Elo (N de ET.rejouer, parti de zéro)."""
    N, out = {}, []
    for m in M:
        nh, na = N.get(m[3], 0), N.get(m[4], 0)
        out.append(min(nh, na))
        N[m[3]], N[m[4]] = nh + 1, na + 1
    return out


def temoin(M, reglage_e2, pentes):
    """Le % de production avant chaque match : Elo E2, puis la pente de la ligue quand elle est retenue."""
    a, c, w, s = reglage_e2
    P = ET.rejouer(M, a=a, c=c, w=w, s=s)
    for i, m in enumerate(M):
        k = pentes.get(m[2])
        if k:
            P[i] = E3._sg(k * E3._lg(P[i]))
    return P


def _pente(P, Y, idx):
    if len(idx) < MIN_PENTE:
        return None
    try:
        a = ET.pente(P, Y, idx)
    except (OverflowError, ZeroDivisionError):
        return None
    return a if math.isfinite(a) else None


def _arr(x, n=3):
    return None if x is None else round(x, n)


def _ll(p, y):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p) if y else -math.log(1 - p)


def decrire(P, Y, idx):
    if not idx:
        return {'matchs': 0}
    n = len(idx)
    bons = sum(1 for i in idx if (P[i] >= 0.5) == bool(Y[i]))
    return {'matchs': n, 'log_loss': round(ET.log_loss(P, Y, idx), 5),
            'brier': round(sum((P[i] - Y[i]) ** 2 for i in idx) / n, 5),
            'bons_vainqueurs_pct': round(100 * bons / n, 1), 'pente_etalonnage': _arr(_pente(P, Y, idx)),
            'favori_annonce_pct': round(100 * sum(max(P[i], 1 - P[i]) for i in idx) / n, 1),
            'favori_reel_pct': round(100 * bons / n, 1)}


def hors_bande(a):
    """−1 si la pente est sous 0,85, +1 si elle dépasse 1,15, 0 sinon (ou pente non calculée)."""
    if a is None:
        return 0
    return -1 if a < PENTE_MIN else 1 if a > PENTE_MAX else 0


def moins_fiable(n_juges, pente_a, pente_b):
    return bool(n_juges >= MIN_CLASSE_JUGEE and hors_bande(pente_b) != 0 and hors_bande(pente_a) == hors_bande(pente_b))


def apprendre(P, Y, par_classe):
    """Une pente par classe (maximum de vraisemblance) ; 1 si la classe a moins de 200 matchs."""
    S = []
    for idx in par_classe:
        a = _pente(P, Y, idx) if len(idx) >= MIN_CLASSE_APPRISE else None
        S.append(1.0 if a is None else a)
    return S


def comparer(P, Y, par_classe, S):
    """Gain de log loss du candidat (pentes S) sur le témoin, différences appariées match par match."""
    d, t = [], 0.0
    for k, idx in enumerate(par_classe):
        for i in idx:
            base = _ll(P[i], Y[i])
            t += base
            d.append(base - _ll(E3._sg(S[k] * E3._lg(P[i])), Y[i]) if S[k] != 1.0 else 0.0)
    if not d:
        return {'matchs': 0}
    g = sum(d) / len(d)
    et = math.sqrt(sum((x - g) ** 2 for x in d) / max(len(d) - 1, 1)) / math.sqrt(len(d))
    return {'matchs': len(d), 'gain': round(g, 5), 'erreur_type': round(et, 5), 'log_loss_temoin': round(t / len(d), 5),
            'log_loss_candidat': round(t / len(d) - g, 5), '_gain': g, '_et': et}


def analyser(M, P, NMIN, A, B, journal=print):
    """Q1 et Q2 ligue par ligue, à partir du témoin P et des compteurs NMIN (séparé d'etudier pour les tests)."""
    Y = [m[5] for m in M]

    def ranger(idx):
        out = {}
        for i in idx:
            out.setdefault(M[i][2], [[] for _ in CLASSES])[classe(NMIN[i])].append(i)
        return out

    RA, RB = ranger(A), ranger(B)
    vide = [[] for _ in CLASSES]
    res = {}
    for lg in sorted(RB):
        ca, cb = RA.get(lg, vide), RB[lg]
        produit = lg in LIGUES_PRODUIT
        q1, averties = {}, []
        for k, nom in enumerate(CLASSES):
            pa, pb = _pente(P, Y, ca[k]), _pente(P, Y, cb[k])
            mf = moins_fiable(len(cb[k]), pa, pb)
            if mf:
                averties.append(nom)
            q1[nom] = {'jugement': decrire(P, Y, cb[k]),
                       'apprentissage': {'matchs': len(ca[k]), 'pente_etalonnage': _arr(pa)}, 'moins_fiable': mf}
        SA, SB = apprendre(P, Y, ca), apprendre(P, Y, cb)
        cj, inv = comparer(P, Y, cb, SA), comparer(P, Y, ca, SB)
        comparables = [k for k in range(len(CLASSES)) if min(len(ca[k]), len(cb[k])) >= MIN_CLASSE_SENS
                       and abs(SA[k] - 1) >= ECART_SENS]
        meme_cote = bool(comparables) and all((SA[k] - 1) * (SB[k] - 1) > 0 for k in comparables)
        g, et = cj.pop('_gain', 0.0), cj.pop('_et', 1.0)
        gi = inv.get('_gain')
        regle = bool(cj.get('matchs', 0) >= MIN_JUGES and g >= MARGE and g >= ERREURS_TYPES * et
                     and gi is not None and gi > 0 and meme_cote)
        res[lg] = {'produit': produit, 'matchs_juges': sum(len(x) for x in cb),
                   'matchs_apprentissage': sum(len(x) for x in ca), 'Q1_par_classe': q1,
                   'classes_moins_fiables': averties, 'avertissement_permis': bool(produit and averties),
                   'Q2_correction': dict(cj, pentes_apprises={n: round(s, 3) for n, s in zip(CLASSES, SA)},
                                         pentes_sens_inverse={n: round(s, 3) for n, s in zip(CLASSES, SB)},
                                         sens_inverse=_arr(gi, 5), classes_comparables=[CLASSES[k] for k in comparables],
                                         pentes_du_meme_cote=meme_cote, regle_remplie=regle,
                                         retenu=bool(regle and produit))}
    for lg in sorted(res, key=lambda k: (not res[k]['produit'], k)):
        v = res[lg]
        r = v['Q2_correction']
        journal(f"  {lg}{' (produit)' if v['produit'] else ' (décrit sans décider)'} : {v['matchs_juges']} matchs jugés, "
                f"{v['matchs_apprentissage']} en apprentissage")
        for nom in CLASSES:
            x = v['Q1_par_classe'][nom]
            j = x['jugement']
            if not j['matchs']:
                journal(f"      {nom} : 0 match jugé (apprentissage {x['apprentissage']['matchs']})")
                continue
            journal(f"      {nom} : {j['matchs']} matchs, log loss {j['log_loss']}, Brier {j['brier']}, bons vainqueurs "
                    f"{j['bons_vainqueurs_pct']} %, favori annoncé {j['favori_annonce_pct']} % / réel {j['favori_reel_pct']} %, "
                    f"pente {j['pente_etalonnage']} (apprentissage {x['apprentissage']['pente_etalonnage']} sur "
                    f"{x['apprentissage']['matchs']}){' → MOINS FIABLE' if x['moins_fiable'] else ''}")
        journal(f"      correction : pentes {list(r['pentes_apprises'].values())}, réapprises sur le jugement "
                f"{list(r['pentes_sens_inverse'].values())} ; log loss {r.get('log_loss_temoin')} → {r.get('log_loss_candidat')}, "
                f"gain {r.get('gain')} ± {r.get('erreur_type')}, sens inverse {r['sens_inverse']}, même côté "
                f"{'oui' if r['pentes_du_meme_cote'] else 'non'}{' → RETENU' if r['retenu'] else ' → pas retenu'}")
    return res


def etudier(M, reglage_e2, pentes, journal=print):
    A, B = EE.periodes(M)
    if len(A) < MIN_JUGES or len(B) < MIN_JUGES:
        journal(f'pas assez de matchs (apprentissage {len(A)}, jugement {len(B)})')
        return {'verdict': 'donnees_insuffisantes', 'paquet': PAQUET, 'apprentissage': len(A), 'jugement': len(B)}
    P = temoin(M, reglage_e2, pentes)
    NMIN = compteurs(M)
    journal(f"joueurs peu connus : {len(M)} matchs, apprentissage {len(A)}, jugement {len(B)}, pentes {pentes}")
    res = analyser(M, P, NMIN, A, B, journal)
    return {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'paquet': PAQUET,
            'base_E2': list(reglage_e2), 'pentes_par_ligue': pentes, 'apprentissage': len(A), 'jugement': len(B),
            'classes': list(CLASSES), 'seuils': {'matchs_juges_ligue': MIN_JUGES, 'gain_min': MARGE,
                                                 'erreurs_types': ERREURS_TYPES, 'classe_jugee': MIN_CLASSE_JUGEE,
                                                 'classe_apprise': MIN_CLASSE_APPRISE, 'classe_sens': MIN_CLASSE_SENS,
                                                 'pente_min': PENTE_MIN, 'pente_max': PENTE_MAX},
            'ligues_produit': list(LIGUES_PRODUIT), 'par_ligue': res,
            'retenu': {lg: res[lg]['Q2_correction']['retenu'] for lg in LIGUES_PRODUIT if lg in res},
            'avertissement_permis': {lg: res[lg]['classes_moins_fiables'] for lg in LIGUES_PRODUIT if lg in res}}


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
