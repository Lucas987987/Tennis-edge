#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_score_badminton.py — BADMINTON : LE SCORE EN MANCHES LE PLUS PROBABLE (2-0 OU 2-1) PEUT-IL S'AFFICHER ?
(27/11/2026, paquet 526, Lucas : « lance les 2 études badminton »). Aujourd'hui la page du badminton ne montre que le %.
Rien n'est publié sur le site ; aucune cote n'est lue ; aucun conseil. Le % de victoire ne dépend jamais du score.

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI (mêmes données que l'étape 4 — sans la série hors circuits —, même % de
l'algo : le modèle retenu aux étapes 3 et 4 ; mêmes périodes : lancement 120 jours, APPRENTISSAGE jusqu'au 31/12/2022,
JUGEMENT une seule fois du 01/01/2023 au dernier jour) :
  Quatre scores possibles : h 2-0, h 2-1, a 2-1 (h perd en 3), a 2-0.
  S0  manches indépendantes : la probabilité q que h gagne une manche est celle qui redonne le % du match
      (p = q² (3 − 2q)) ; P(h 2-0) = q², P(h 2-1) = 2 q² (1 − q), P(a 2-1) = 2 q (1 − q)², P(a 2-0) = (1 − q)².
  S1  S0 recalé : pour chaque épreuve et chaque tranche de 5 points du % du favori, la part réelle des matchs en
      3 manches apprise sur l'apprentissage, rétrécie vers celle de S0 avec un poids de 50 matchs ; la part du favori
      dans chaque cas (2-0 / 2-1) suit S0 ; le % du match ne change pas.
  Q1. S1 remplace S0 s'il gagne au moins 0,001 de log loss (sur les 4 scores) par match sur le jugement ET dans le même
      sens quand on inverse (appris sur le jugement, jugé sur l'apprentissage).
  Q2. On AFFICHE le score le plus probable sur la page si, avec le modèle retenu, sur le jugement, la part annoncée de
      matchs en 3 manches est à moins de 3 points de la part réelle, tout ensemble ET dans chaque épreuve qui a au moins
      1 000 matchs jugés.
  Publiés sans décider : le score le plus probable trouvé (en %), les manches décisives annoncées contre réelles par
      tranche du % du favori, épreuve par épreuve.
Rapport : badminton/rapport_score_badminton.json — comptes et moyennes seulement, aucun nom de joueur.
Usage : python badminton/etude_score_badminton.py [racine]
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo_badminton as EB  # noqa: E402
import etude_elo_badminton as E1  # noqa: E402
import etude_etape4_badminton as S4  # noqa: E402

REGLAGE = (400, 0.3, 1.0, 32)
POIDS, MARGE, MIN_JUGES, ECART_MAX = 50, 0.001, 1000, 3.0
SORTIE = os.path.join(ICI, 'rapport_score_badminton.json')
ORDRE = ('h20', 'h21', 'a21', 'a20')


def q_de(p):
    """q tel que q² (3 − 2q) = p (dichotomie)."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mi = (lo + hi) / 2
        if mi * mi * (3 - 2 * mi) < p:
            lo = mi
        else:
            hi = mi
    return (lo + hi) / 2


def s0(p):
    q = q_de(p)
    return {'h20': q * q, 'h21': 2 * q * q * (1 - q), 'a21': 2 * q * (1 - q) ** 2, 'a20': (1 - q) ** 2}


def tranche(p):
    return min(9, int((max(p, 1 - p) - 0.5) * 20))           # 0 = 50–55 %, … 9 = 95–100 %


def apprendre(M, P, idx):
    """{(épreuve, tranche): [matchs, en 3 manches, part S0 en 3 manches cumulée]}."""
    T = {}
    for i in idx:
        d = s0(P[i])
        k = (M[i][2], tranche(P[i]))
        t = T.setdefault(k, [0, 0, 0.0])
        t[0] += 1
        t[1] += int(M[i][10] == 3)
        t[2] += d['h21'] + d['a21']
    return T


def s1(p, ep, T):
    d = s0(p)
    t = T.get((ep, tranche(p)))
    if not t:
        return d
    trois0 = d['h21'] + d['a21']
    trois = (t[1] + POIDS * trois0) / (t[0] + POIDS)          # la part réelle de la case, rétrécie vers celle de S0
    trois = min(max(trois, 1e-4), 1 - 1e-4)
    deux0 = 1 - trois0
    f = lambda x, tot: x / tot if tot > 0 else 0.5
    return {'h20': (1 - trois) * f(d['h20'], deux0), 'a20': (1 - trois) * f(d['a20'], deux0),
            'h21': trois * f(d['h21'], trois0), 'a21': trois * f(d['a21'], trois0)}


def reel(m):
    return ('h' if m[5] == 1 else 'a') + ('21' if m[10] == 3 else '20')


def ll(D, M, idx):
    return sum(-math.log(max(D[i][reel(M[i])], 1e-9)) for i in idx) / len(idx)


def decisives(D, M, idx):
    if not idx:
        return {'matchs': 0}
    ann = sum(D[i]['h21'] + D[i]['a21'] for i in idx) / len(idx)
    r = sum(1 for i in idx if M[i][10] == 3) / len(idx)
    top = sum(1 for i in idx if max(ORDRE, key=lambda k: D[i][k]) == reel(M[i])) / len(idx)
    return {'matchs': len(idx), 'trois_manches_annonce_pct': round(100 * ann, 1), 'trois_manches_reel_pct': round(100 * r, 1),
            'ecart_pts': round(100 * (ann - r), 1), 'score_le_plus_probable_trouve_pct': round(100 * top, 1)}


def juger(M, premier_jour):
    A, B = E1.periodes(M, premier_jour)
    if len(A) < MIN_JUGES or len(B) < MIN_JUGES:
        return {'verdict': 'donnees_insuffisantes', 'apprentissage': len(A), 'jugement': len(B)}
    P = S4.rejouer(M, *REGLAGE)
    D0 = [s0(p) for p in P]
    TA, TB = apprendre(M, P, A), apprendre(M, P, B)
    D1A = [s1(p, m[2], TA) for p, m in zip(P, M)]
    D1B = [s1(p, m[2], TB) for p, m in zip(P, M)]
    gain = ll(D0, M, B) - ll(D1A, M, B)
    inverse = ll(D0, M, A) - ll(D1B, M, A)
    ok = gain >= MARGE and inverse > 0
    D = D1A if ok else D0
    par = {ep: decisives(D, M, [i for i in B if M[i][2] == ep]) for ep in EB.EPREUVES}
    tout = decisives(D, M, B)
    afficher = abs(tout['ecart_pts']) < ECART_MAX and all(abs(d['ecart_pts']) < ECART_MAX for d in par.values()
                                                          if d['matchs'] >= MIN_JUGES)
    tranches = {}
    for ep in list(EB.EPREUVES) + ['tout']:
        I = [i for i in B if ep == 'tout' or M[i][2] == ep]
        tranches[ep] = {f'{50 + 5 * k}–{55 + 5 * k} %': decisives(D, M, [i for i in I if tranche(P[i]) == k])
                        for k in range(10) if any(tranche(P[i]) == k for i in I)}
    return {'periodes': {'apprentissage': len(A), 'jugement': len(B)},
            'comparaison': {'log_loss_S0': round(ll(D0, M, B), 5), 'log_loss_S1': round(ll(D1A, M, B), 5),
                            'gain_juge': round(gain, 5), 'sens_inverse': round(inverse, 5), 'S1_retenu': ok},
            'modele_retenu': 'S1' if ok else 'S0', 'jugement_toutes_epreuves': tout, 'jugement_par_epreuve': par,
            'par_tranche_publie_sans_decider': tranches,
            'verdict': 'afficher_le_score' if afficher else 'ne_pas_afficher_le_score'}


def etudier(M, comptes=None, journal=print):
    if not M or len(M[0]) < 11:
        journal('badminton score : aucun match (ou nombre de manches absent)')
        return {'verdict': 'donnees_insuffisantes'}
    premier = M[0][1]
    S = [m for m in M if not m[7]]
    coeur = juger(S, premier)
    rep = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'etude': 'score_badminton',
           'regle_ecrite_le': '2026-11-27', 'donnees': dict(comptes or {}, matchs_etudies=len(S))}
    rep.update(coeur)
    journal(f'badminton score : {len(S)} matchs étudiés')
    if coeur['verdict'] == 'donnees_insuffisantes':
        journal('  pas assez de matchs')
        return rep
    c = coeur['comparaison']
    journal(f"  S0 {c['log_loss_S0']} · S1 {c['log_loss_S1']} : gain jugé {c['gain_juge']:+.5f}, sens inverse {c['sens_inverse']:+.5f} "
            f"→ modèle retenu {coeur['modele_retenu']}")
    for ep, d in list(coeur['jugement_par_epreuve'].items()) + [('tout', coeur['jugement_toutes_epreuves'])]:
        journal(f"  {ep} = {d['matchs']} matchs, 3 manches annoncé {d.get('trois_manches_annonce_pct')} % / réel "
                f"{d.get('trois_manches_reel_pct')} % (écart {d.get('ecart_pts')} pts), score le plus probable trouvé "
                f"{d.get('score_le_plus_probable_trouve_pct')} %")
    for tr, d in coeur['par_tranche_publie_sans_decider']['tout'].items():
        journal(f"  favori {tr} : {d['matchs']} matchs, 3 manches annoncé {d['trois_manches_annonce_pct']} % / réel {d['trois_manches_reel_pct']} %")
    journal(f"  verdict : {coeur['verdict']}")
    return rep


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    M, comptes = EB.lire(racine)
    rep = etudier(M, comptes)
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
