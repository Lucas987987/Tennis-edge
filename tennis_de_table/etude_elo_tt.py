#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_elo_tt.py — L'ELO TIENT-IL AU TENNIS DE TABLE ? (26/11/2026, paquet 487, Lucas : « lance » le ping-pong)

Première étape du ping-pong : un Elo joueur par joueur sur les résultats collectés, jugé avec nos règles habituelles.
Rien n'est publié sur le site ; aucune cote n'est lue ; aucun conseil.

RÈGLE ÉCRITE LE 26/11/2026, AVANT TOUT ESSAI :
  Périodes : les 120 premiers jours collectés servent seulement à lancer les classements (non jugés) ;
             APPRENTISSAGE = la suite jusqu'au 30/09/2025 ; JUGEMENT, une seule fois, du 01/10/2025 au dernier jour.
  Candidats (grilles fixées ici, choix du meilleur réglage sur l'apprentissage seulement) :
    E0  K fixe ∈ {16, 24, 32, 48, 64}
    E1  K = a / (n + 5)^c, a ∈ {100, 200, 400}, c ∈ {0,3 ; 0,45 ; 0,6}
    E2  E1 réglé + marge : w ∈ {0,25 ; 0,5}, échelle s ∈ {10, 20}
  Q1. Le modèle retenu = le plus simple qui n'est pas battu : E1 remplace E0, puis E2 remplace E1, seulement s'il gagne
      au moins 0,001 de log loss par match sur le jugement ET dans le même sens sur l'apprentissage quand on inverse
      (réglé sur le jugement, jugé sur l'apprentissage).
  Q2. « L'Elo tient » dans une ligue si, sur au moins 1 000 matchs jugés, sa log loss bat le pile ou face (0,6931)
      d'au moins 0,02 ET sa pente d'étalonnage est entre 0,85 et 1,15. Ligue par ligue, puis toutes ligues.
  Publiés sans décider : Brier, % de bons vainqueurs, favori annoncé contre réel par tranche de %, matchs par ligue.
  Suite si l'Elo tient : modèle aux points (probabilité de gagner un point → manches à 11 → match), jugé de même.

Rapport : tennis_de_table/rapport_elo_tt.json — comptes et moyennes seulement, aucun nom de joueur.
Usage : python tennis_de_table/etude_elo_tt.py [racine]
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo_tt as ET  # noqa: E402

JUGEMENT = dt.date(2025, 10, 1)
CHAUFFE_J = 120
GRILLE_E0 = [16, 24, 32, 48, 64]
GRILLE_E1 = [(a, c) for a in (100, 200, 400) for c in (0.3, 0.45, 0.6)]
GRILLE_E2 = [(w, s) for w in (0.25, 0.5) for s in (10, 20)]
MARGE, MIN_JUGES, MIEUX_QUE_PILE, PENTE_MIN, PENTE_MAX = 0.001, 1000, 0.02, 0.85, 1.15
PILE = math.log(2)
SORTIE = os.path.join(ICI, 'rapport_elo_tt.json')
TRANCHES = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]


def periodes(M):
    if not M:
        return [], []
    debut = dt.date.fromisoformat(M[0][1]) + dt.timedelta(days=CHAUFFE_J)
    A = [i for i, m in enumerate(M) if debut <= dt.date.fromisoformat(m[1]) < JUGEMENT]
    B = [i for i, m in enumerate(M) if dt.date.fromisoformat(m[1]) >= JUGEMENT]
    return A, B


def regler(M, Y, idx, candidats, fabrique):
    meilleur = None
    for x in candidats:
        P = ET.rejouer(M, **fabrique(x))
        ll = ET.log_loss(P, Y, idx)
        if meilleur is None or ll < meilleur[1]:
            meilleur = (x, ll, P)
    return meilleur


def familles(M, Y, idx):
    """Réglage des trois familles sur idx : {nom: (réglage, log loss sur idx, P)}."""
    e0 = regler(M, Y, idx, GRILLE_E0, lambda k: {'k': k})
    e1 = regler(M, Y, idx, GRILLE_E1, lambda x: {'a': x[0], 'c': x[1]})
    a, c = e1[0]
    e2 = regler(M, Y, idx, GRILLE_E2, lambda x: {'a': a, 'c': c, 'w': x[0], 's': x[1]})
    return {'E0': e0, 'E1': e1, 'E2': ((a, c) + e2[0], e2[1], e2[2])}


def parametres(nom, x):
    return {'k': x} if nom == 'E0' else {'a': x[0], 'c': x[1]} if nom == 'E1' else {'a': x[0], 'c': x[1], 'w': x[2], 's': x[3]}


def decrire(P, Y, idx):
    if not idx:
        return {'matchs': 0}
    bons = sum(1 for i in idx if (P[i] >= 0.5) == bool(Y[i]))
    brier = sum((P[i] - Y[i]) ** 2 for i in idx) / len(idx)
    tr = {}
    for lo, hi in TRANCHES:
        J = [i for i in idx if lo <= max(P[i], 1 - P[i]) < hi]
        if J:
            ann = sum(max(P[i], 1 - P[i]) for i in J) / len(J)
            reel = sum(1 for i in J if (P[i] >= 0.5) == bool(Y[i])) / len(J)
            tr[f'{int(lo * 100)}–{min(int(hi * 100), 100)} %'] = {'matchs': len(J), 'favori_annonce_pct': round(100 * ann, 1),
                                                                   'favori_reel_pct': round(100 * reel, 1)}
    return {'matchs': len(idx), 'log_loss': round(ET.log_loss(P, Y, idx), 5), 'pile_ou_face': round(PILE, 5),
            'brier': round(brier, 5), 'bons_vainqueurs_pct': round(100 * bons / len(idx), 1),
            'pente_etalonnage': round(ET.pente(P, Y, idx), 3), 'par_tranche': tr}


def tient(d):
    return (d.get('matchs', 0) >= MIN_JUGES and d['log_loss'] <= PILE - MIEUX_QUE_PILE
            and PENTE_MIN <= d['pente_etalonnage'] <= PENTE_MAX)


def etudier(M, journal=print):
    Y = [m[5] for m in M]
    A, B = periodes(M)
    if len(B) < MIN_JUGES or len(A) < MIN_JUGES:
        journal(f'tennis de table : pas assez de matchs (apprentissage {len(A)}, jugement {len(B)})')
        return {'verdict': 'donnees_insuffisantes', 'apprentissage': len(A), 'jugement': len(B)}
    surA = familles(M, Y, A)                      # réglé sur l'apprentissage
    surB = familles(M, Y, B)                      # réglé sur le jugement (pour le sens inverse)
    choix, ordre, comparaisons = 'E0', ['E0', 'E1', 'E2'], {}
    for prec, cand in zip(ordre, ordre[1:]):
        if prec != choix:
            break
        Pp = ET.rejouer(M, **parametres(prec, surA[prec][0]))
        Pc = surA[cand][2]
        gain = ET.log_loss(Pp, Y, B) - ET.log_loss(Pc, Y, B)
        Pp2 = ET.rejouer(M, **parametres(prec, surB[prec][0]))
        Pc2 = ET.rejouer(M, **parametres(cand, surB[cand][0]))
        inverse = ET.log_loss(Pp2, Y, A) - ET.log_loss(Pc2, Y, A)
        ok = gain >= MARGE and inverse > 0
        comparaisons[f'{cand}_contre_{prec}'] = {'gain_juge': round(gain, 5), 'sens_inverse': round(inverse, 5), 'retenu': ok}
        if ok:
            choix = cand
    P = surA[choix][2]
    ligues = sorted({M[i][2] for i in B})
    par_ligue = {}
    for lg in ligues:
        J = [i for i in B if M[i][2] == lg]
        d = decrire(P, Y, J)
        d['tient'] = tient(d)
        par_ligue[lg] = d
    tout = decrire(P, Y, B)
    tout['tient'] = tient(tout)
    rep = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'paquet': 487,
           'donnees': {'premier_jour': M[0][1], 'dernier_jour': M[-1][1], 'matchs_gardes': len(M),
                       'apprentissage': len(A), 'jugement': len(B)},
           'reglages_appris': {k: {'reglage': v[0], 'log_loss_apprentissage': round(v[1], 5)} for k, v in surA.items()},
           'comparaisons': comparaisons, 'modele_retenu': choix,
           'jugement_toutes_ligues': tout, 'jugement_par_ligue': par_ligue,
           'verdict': 'l_elo_tient' if tout['tient'] else 'l_elo_ne_tient_pas'}
    journal(f"tennis de table : {len(M)} matchs gardés ({M[0][1]} → {M[-1][1]}), apprentissage {len(A)}, jugement {len(B)}")
    for k, v in comparaisons.items():
        journal(f"  {k} : gain jugé {v['gain_juge']:+.5f}, sens inverse {v['sens_inverse']:+.5f} → {'retenu' if v['retenu'] else 'non'}")
    journal(f"  modèle retenu {choix} {surA[choix][0]} : log loss {tout['log_loss']} (pile ou face {round(PILE, 4)}), "
            f"bons vainqueurs {tout['bons_vainqueurs_pct']} %, pente {tout['pente_etalonnage']} → "
            f"{'l Elo tient' if tout['tient'] else 'l Elo ne tient pas'}")
    for lg, d in par_ligue.items():
        journal(f"  {lg} : {d['matchs']} matchs, log loss {d.get('log_loss')}, bons vainqueurs {d.get('bons_vainqueurs_pct')} %, "
                f"pente {d.get('pente_etalonnage')}{' → tient' if d['tient'] else ''}")
    return rep


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    M = ET.matchs(racine)
    rep = etudier(M)
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
