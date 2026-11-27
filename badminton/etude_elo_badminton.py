#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_elo_badminton.py — L'ELO TIENT-IL AU BADMINTON ? (27/11/2026, Lucas : première étape du badminton)

Même étude que tennis_de_table/etude_elo_tt.py (paquet 487) : un Elo entité par entité (le joueur en simple, la paire
en double) sur les résultats collectés, jugé avec nos règles habituelles. Rien n'est publié sur le site ; aucune cote
n'est lue ; aucun conseil.

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI :
  Périodes : les 120 premiers jours collectés servent seulement à lancer les classements (non jugés) ;
             APPRENTISSAGE = la suite jusqu'au 31/12/2022 ; JUGEMENT, une seule fois, du 01/01/2023 au dernier jour.
  Candidats (grilles fixées ici, choix du meilleur réglage sur l'apprentissage seulement, toutes épreuves ensemble) :
    E0  K fixe ∈ {16, 24, 32, 48, 64}
    E1  K = a / (n + 5)^c, a ∈ {100, 200, 400}, c ∈ {0,3 ; 0,45 ; 0,6}
    E2  E1 réglé + marge : w ∈ {0,25 ; 0,5}, échelle s ∈ {8, 16}
        (seule adaptation aux manches à 21 : l'échelle. Une victoire nette 21–15, 21–15 fait 58 % des points ;
         s = 16 la compte ≈ 0,79 d'une victoire, s = 8 ≈ 0,66. Au tennis de table : s ∈ {10, 20}.)
  Q1. Le modèle retenu = le plus simple qui n'est pas battu : E1 remplace E0, puis E2 remplace E1, seulement s'il gagne
      au moins 0,001 de log loss par match sur le jugement ET dans le même sens sur l'apprentissage quand on inverse
      (réglé sur le jugement, jugé sur l'apprentissage).
  Q2. « L'Elo tient » pour une épreuve si, sur au moins 1 000 matchs jugés, sa log loss bat le pile ou face (0,6931)
      d'au moins 0,02 ET sa pente d'étalonnage est entre 0,85 et 1,15. Épreuve par épreuve (simple messieurs, simple
      dames, double messieurs, double dames, double mixte), puis tout ensemble.
  Publiés sans décider : Brier, % de bons vainqueurs, favori annoncé contre réel par tranche de %, matchs par épreuve
      et par an, part des matchs où un des deux camps a moins de 5 matchs avant.
  Constat de lecture des données, écrit avant tout essai : une série locale quotidienne hors circuits BWF (« Armenia
      Infinity Cup », 2021–2022 seulement) pèse lourd dans l'apprentissage et n'a aucun match dans le jugement. Elle
      reste dans l'étude (la règle ne change pas) ; le même jugement refait SANS elle est publié sans décider.

Rapport : badminton/rapport_elo_badminton.json — comptes et moyennes seulement, aucun nom de joueur.
Usage : python badminton/etude_elo_badminton.py [racine]
"""
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo_badminton as EB  # noqa: E402

FIN_APPRENTISSAGE = dt.date(2022, 12, 31)
JUGEMENT = dt.date(2023, 1, 1)
CHAUFFE_J = 120
GRILLE_E0 = [16, 24, 32, 48, 64]
GRILLE_E1 = [(a, c) for a in (100, 200, 400) for c in (0.3, 0.45, 0.6)]
GRILLE_E2 = [(w, s) for w in (0.25, 0.5) for s in (8, 16)]
MARGE, MIN_JUGES, MIEUX_QUE_PILE, PENTE_MIN, PENTE_MAX = 0.001, 1000, 0.02, 0.85, 1.15
PEU_CONNU = 5
PILE = math.log(2)
SORTIE = os.path.join(ICI, 'rapport_elo_badminton.json')
TRANCHES = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]


def periodes(M, premier_jour=None):
    """Indices de l'apprentissage et du jugement ; premier_jour = premier jour collecté (défaut : celui de M)."""
    if not M:
        return [], []
    debut = dt.date.fromisoformat(premier_jour or M[0][1]) + dt.timedelta(days=CHAUFFE_J)
    A = [i for i, m in enumerate(M) if debut <= dt.date.fromisoformat(m[1]) < JUGEMENT]
    B = [i for i, m in enumerate(M) if dt.date.fromisoformat(m[1]) >= JUGEMENT]
    return A, B


def regler(M, Y, idx, candidats, fabrique):
    meilleur = None
    for x in candidats:
        P = EB.rejouer(M, **fabrique(x))
        ll = EB.log_loss(P, Y, idx)
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


def matchs_avant(M):
    """Pour chaque match, le nombre de matchs déjà joués par le camp le MOINS connu des deux."""
    N, out = {}, []
    for m in M:
        nh, na = N.get(m[3], 0), N.get(m[4], 0)
        out.append(min(nh, na))
        N[m[3]], N[m[4]] = nh + 1, na + 1
    return out


def decrire(P, Y, idx, avant=None):
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
    d = {'matchs': len(idx), 'log_loss': round(EB.log_loss(P, Y, idx), 5), 'pile_ou_face': round(PILE, 5),
         'brier': round(brier, 5), 'bons_vainqueurs_pct': round(100 * bons / len(idx), 1),
         'pente_etalonnage': round(EB.pente(P, Y, idx), 3), 'par_tranche': tr}
    if avant is not None:
        d['part_peu_connus_pct'] = round(100 * sum(1 for i in idx if avant[i] < PEU_CONNU) / len(idx), 1)
    return d


def tient(d):
    return (d.get('matchs', 0) >= MIN_JUGES and d['log_loss'] <= PILE - MIEUX_QUE_PILE
            and PENTE_MIN <= d['pente_etalonnage'] <= PENTE_MAX)


def juger(M, premier_jour=None):
    """Apprend, compare les familles (Q1), juge une fois (Q2). Renvoie le cœur du rapport, ou None si trop peu."""
    Y = [m[5] for m in M]
    A, B = periodes(M, premier_jour)
    if len(B) < MIN_JUGES or len(A) < MIN_JUGES:
        return {'verdict': 'donnees_insuffisantes', 'apprentissage': len(A), 'jugement': len(B)}
    surA = familles(M, Y, A)                      # réglé sur l'apprentissage
    surB = familles(M, Y, B)                      # réglé sur le jugement (pour le sens inverse)
    choix, ordre, comparaisons = 'E0', ['E0', 'E1', 'E2'], {}
    for prec, cand in zip(ordre, ordre[1:]):
        if prec != choix:
            break
        Pp = EB.rejouer(M, **parametres(prec, surA[prec][0]))
        Pc = surA[cand][2]
        gain = EB.log_loss(Pp, Y, B) - EB.log_loss(Pc, Y, B)
        Pp2 = EB.rejouer(M, **parametres(prec, surB[prec][0]))
        Pc2 = EB.rejouer(M, **parametres(cand, surB[cand][0]))
        inverse = EB.log_loss(Pp2, Y, A) - EB.log_loss(Pc2, Y, A)
        ok = gain >= MARGE and inverse > 0
        comparaisons[f'{cand}_contre_{prec}'] = {'gain_juge': round(gain, 5), 'sens_inverse': round(inverse, 5), 'retenu': ok}
        if ok:
            choix = cand
    P = surA[choix][2]
    avant = matchs_avant(M)
    par_epreuve = {}
    for ep in EB.EPREUVES:
        d = decrire(P, Y, [i for i in B if M[i][2] == ep], avant)
        d['tient'] = tient(d)
        par_epreuve[ep] = d
    tout = decrire(P, Y, B, avant)
    tout['tient'] = tient(tout)
    return {'periodes': {'apprentissage': len(A), 'jugement': len(B),
                         'lancement_non_juge': len(M) - len(A) - len(B)},
            'reglages_appris': {k: {'reglage': v[0], 'log_loss_apprentissage': round(v[1], 5)} for k, v in surA.items()},
            'comparaisons': comparaisons, 'modele_retenu': choix, 'reglage_retenu': surA[choix][0],
            'jugement_toutes_epreuves': tout, 'jugement_par_epreuve': par_epreuve,
            'verdict': 'l_elo_tient' if tout['tient'] else 'l_elo_ne_tient_pas'}


def par_epreuve_et_an(M):
    T = collections.defaultdict(collections.Counter)
    for m in M:
        T[m[2]][m[1][:4]] += 1
    return {ep: dict(sorted(T[ep].items())) for ep in EB.EPREUVES if ep in T}


def etudier(M, comptes=None, journal=print):
    if not M:
        journal('badminton : aucun match gardé')
        return {'verdict': 'donnees_insuffisantes', 'apprentissage': 0, 'jugement': 0}
    coeur = juger(M)
    rep = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'etude': 'elo_badminton',
           'regle_ecrite_le': '2026-11-27',
           'donnees': dict(comptes or {}, premier_jour=M[0][1], dernier_jour=M[-1][1], matchs_gardes=len(M)),
           'matchs_par_epreuve_et_par_an': par_epreuve_et_an(M)}
    rep.update(coeur)
    journal(f"badminton : {len(M)} matchs gardés ({M[0][1]} → {M[-1][1]})"
            + (f", {comptes['matchs_ecartes']} écartés sur {comptes['lignes_lues']} lignes" if comptes else ''))
    if comptes:
        for k, v in comptes['ecartes_par_motif'].items():
            journal(f'  écartés {k} = {v}')
        journal('  épreuve lue par ' + ', '.join(f'{k} = {v}' for k, v in comptes['epreuve_lue_par'].items()))
    if coeur['verdict'] == 'donnees_insuffisantes':
        journal(f"  pas assez de matchs (apprentissage {coeur['apprentissage']}, jugement {coeur['jugement']})")
        return rep
    tout = coeur['jugement_toutes_epreuves']
    journal(f"  lancement {coeur['periodes']['lancement_non_juge']}, apprentissage {coeur['periodes']['apprentissage']}, "
            f"jugement {coeur['periodes']['jugement']}")
    for k, v in coeur['comparaisons'].items():
        journal(f"  {k} = gain jugé {v['gain_juge']:+.5f}, sens inverse {v['sens_inverse']:+.5f} → {'retenu' if v['retenu'] else 'non'}")
    journal(f"  modèle retenu {coeur['modele_retenu']} {coeur['reglage_retenu']} = log loss {tout['log_loss']} "
            f"(pile ou face {round(PILE, 4)}), Brier {tout['brier']}, bons vainqueurs {tout['bons_vainqueurs_pct']} %, "
            f"pente {tout['pente_etalonnage']}, peu connus {tout['part_peu_connus_pct']} % → "
            f"{'l Elo tient' if tout['tient'] else 'l Elo ne tient pas'}")
    for ep, d in coeur['jugement_par_epreuve'].items():
        journal(f"  {ep} = {d['matchs']} matchs, log loss {d.get('log_loss')}, Brier {d.get('brier')}, bons vainqueurs "
                f"{d.get('bons_vainqueurs_pct')} %, pente {d.get('pente_etalonnage')}, peu connus "
                f"{d.get('part_peu_connus_pct')} %{' → tient' if d['tient'] else ' → ne tient pas'}")
    for tr, d in tout['par_tranche'].items():
        journal(f"  favori {tr} = {d['matchs']} matchs, annoncé {d['favori_annonce_pct']} %, réel {d['favori_reel_pct']} %")
    # Publié sans décider : le même jugement sans la série hors circuits (mêmes périodes, mêmes grilles).
    S = [m for m in M if not m[7]]
    if len(S) < len(M):
        sans = juger(S, premier_jour=M[0][1])
        rep['sans_hors_circuit_publie_sans_decider'] = dict(sans, matchs_retires=len(M) - len(S))
        if sans['verdict'] != 'donnees_insuffisantes':
            t2 = sans['jugement_toutes_epreuves']
            journal(f"  sans la série hors circuits ({len(M) - len(S)} matchs retirés, sans décider) = modèle "
                    f"{sans['modele_retenu']} {sans['reglage_retenu']}, log loss {t2['log_loss']}, pente {t2['pente_etalonnage']}")
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
