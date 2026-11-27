#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_etape2_badminton.py — BADMINTON, ÉTAPE 2 : GRILLE ÉLARGIE, PENTE APPRISE, DOUBLES AU JOUEUR
(27/11/2026, Lucas : « fais le » après l'étape 1, badminton/etude_elo_badminton.py).

Constat de l'étape 1 (jugement 2023 → 26/11/2026, 42 924 matchs) : l'Elo bat largement le pile ou face partout (log loss
0,5796 contre 0,6931) mais il est trop prudent (pente 1,167 > 1,15) ; les grilles reprises du tennis de table étaient
en butée (K = 64, c = 0,3) ; 40 à 46 % des matchs de double ont une paire presque neuve. Rien n'est publié sur le
site ; aucune cote n'est lue ; aucun conseil.

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI (mêmes données, mêmes filtres et mêmes périodes que l'étape 1 :
lancement 120 jours non jugés, APPRENTISSAGE jusqu'au 31/12/2022, JUGEMENT une seule fois du 01/01/2023 au dernier jour) :
  Départ = le modèle retenu à l'étape 1 : E2 a = 200, c = 0,3, w = 0,25, s = 16 (paires = entités, sans pente).
  C1  même famille, grille élargie, réglée sur l'apprentissage seulement (toutes les combinaisons) :
        a ∈ {100, 200, 400, 800}, c ∈ {0 ; 0,1 ; 0,2 ; 0,3}, w ∈ {0,25 ; 0,5 ; 0,75}, s ∈ {16, 32}.
  C2  le modèle retenu jusque-là + pente apprise : p → σ(β · logit p), β par maximum de vraisemblance sur
        l'apprentissage. C2a : un seul β ; C2b : un β par épreuve (5 valeurs).
  C3  le modèle retenu jusque-là, mais en double un camp = ses DEUX JOUEURS : la note de la paire = la moyenne des notes
        « double » de ses deux joueurs (une note par joueur, tous doubles confondus, départ 1 500) ; chaque joueur bouge
        de K(n du joueur) × l'écart ; le simple ne change pas ; mêmes réglages de l'Elo, la pente (si retenue) réapprise
        de la même façon. Un joueur est reconnu par son nom dans la paire (la source ne donne pas l'identifiant des
        joueurs d'une paire) : deux joueurs de même nom abrégé sont confondus — réserve publiée.
  Q1. Dans l'ordre C1, C2a, C2b (contre C2a), C3 : un candidat remplace le modèle retenu seulement s'il gagne au moins
      0,001 de log loss par match sur le jugement ET dans le même sens quand on inverse (tout réglé ou appris sur le
      jugement, jugé sur l'apprentissage). Pour C3 le gain est compté sur les matchs de DOUBLE (les seuls qui changent),
      au moins 1 000 matchs de double jugés.
  Q2. Comme à l'étape 1 : « l'Elo tient » pour une épreuve si, sur au moins 1 000 matchs jugés, la log loss bat le pile
      ou face d'au moins 0,02 ET la pente d'étalonnage du jugement est entre 0,85 et 1,15. Épreuve par épreuve, puis
      tout ensemble.
  Publiés sans décider : Brier, % de bons vainqueurs, favori annoncé contre réel par tranche, les β appris, la part des
      matchs de double où un camp a moins de 5 matchs avant (paire, puis joueur le moins connu), et le même jugement
      sans la série locale hors circuits (Armenia Infinity Cup, 2021–2022).

Rapport : badminton/rapport_etape2_badminton.json — comptes et moyennes seulement, aucun nom de joueur.
Usage : python badminton/etude_etape2_badminton.py [racine]
"""
import datetime as dt
import itertools
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo_badminton as EB  # noqa: E402
import etude_elo_badminton as E1  # noqa: E402

DEPART_REGLAGE = (200, 0.3, 0.25, 16)
GRILLE_C1 = list(itertools.product((100, 200, 400, 800), (0, 0.1, 0.2, 0.3), (0.25, 0.5, 0.75), (16, 32)))
MARGE, MIN_JUGES = E1.MARGE, E1.MIN_JUGES
DEPART = 1500.0
SORTIE = os.path.join(ICI, 'rapport_etape2_badminton.json')


# ------------------------------------------------------------------ l'Elo (paires ou joueurs du double)
def rejouer(M, a, c, w, s, joueurs=False):
    """p (pour h) avant chaque match. joueurs=False : un camp = une entité (étape 1, identique à elo_tt.rejouer avec
    a, c, w, s). joueurs=True : en double, un camp = ses deux joueurs (note de la paire = moyenne des deux)."""
    R, N, P = {}, {}, []
    for m in M:
        h, b, y, sp = m[3], m[4], m[5], m[6]
        noms = m[9] if joueurs and len(m) > 9 else None
        if noms:
            ch, cb = [('d', x) for x in noms[0]], [('d', x) for x in noms[1]]
        else:
            ch, cb = [h], [b]
        rh = sum(R.get(x, DEPART) for x in ch) / len(ch)
        rb = sum(R.get(x, DEPART) for x in cb) / len(cb)
        p = 1.0 / (1.0 + 10 ** (-(rh - rb) / 400.0))
        P.append(p)
        cible = (1 - w) * y + w * (1.0 / (1.0 + math.exp(-(sp - 0.5) * s))) if w else y
        d = cible - p
        for x in ch:
            n = N.get(x, 0)
            R[x] = R.get(x, DEPART) + a / (n + 5) ** c * d
            N[x] = n + 1
        for x in cb:
            n = N.get(x, 0)
            R[x] = R.get(x, DEPART) - a / (n + 5) ** c * d
            N[x] = n + 1
    return P


def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def appliquer(P, betas, M):
    """betas : None (pas de pente), un nombre (un β) ou {épreuve: β}."""
    if betas is None:
        return list(P)
    out = []
    for p, m in zip(P, M):
        b = betas if isinstance(betas, (int, float)) else betas.get(m[2], 1.0)
        out.append(1.0 / (1.0 + math.exp(-b * logit(p))))
    return out


def apprendre_pente(P, Y, M, idx, par_epreuve):
    if not par_epreuve:
        return round(EB.pente(P, Y, idx), 4)
    out = {}
    for ep in EB.EPREUVES:
        J = [i for i in idx if M[i][2] == ep]
        out[ep] = round(EB.pente(P, Y, J), 4) if J else 1.0
    return out


# ------------------------------------------------------------------ apprendre / juger
def regler_c1(M, Y, idx):
    meilleur = None
    for x in GRILLE_C1:
        ll = EB.log_loss(rejouer(M, *x), Y, idx)
        if meilleur is None or ll < meilleur[1]:
            meilleur = (x, ll)
    return meilleur


def construire(M, Y, idx, modele, reglage_c1=None):
    """Un modèle complet appris sur idx : {'reglage', 'joueurs', 'pente' (None|'une'|'epreuve'), 'betas', 'P'}."""
    reg = reglage_c1 if modele['c1'] else DEPART_REGLAGE
    Pb = rejouer(M, *reg, joueurs=modele['joueurs'])
    betas = None if modele['pente'] is None else apprendre_pente(Pb, Y, M, idx, modele['pente'] == 'epreuve')
    return dict(modele, reglage=reg, betas=betas, P=appliquer(Pb, betas, M))


def juger(M, premier_jour=None):
    Y = [m[5] for m in M]
    A, B = E1.periodes(M, premier_jour)
    if len(A) < MIN_JUGES or len(B) < MIN_JUGES:
        return {'verdict': 'donnees_insuffisantes', 'apprentissage': len(A), 'jugement': len(B)}
    c1A, c1B = regler_c1(M, Y, A), regler_c1(M, Y, B)
    doubles_B = [i for i in B if M[i][2].startswith('double')]
    doubles_A = [i for i in A if M[i][2].startswith('double')]
    retenu = {'c1': False, 'pente': None, 'joueurs': False}
    comparaisons = {}
    etapes = [('C1', {'c1': True}), ('C2a', {'pente': 'une'}), ('C2b', {'pente': 'epreuve'}), ('C3', {'joueurs': True})]
    for nom, chg in etapes:
        if nom == 'C2b' and retenu['pente'] != 'une':
            comparaisons[nom] = {'saute': 'C2a non retenu'}
            continue
        cand = dict(retenu, **chg)
        idxB, idxA = (doubles_B, doubles_A) if nom == 'C3' else (B, A)
        if len(idxB) < MIN_JUGES:
            comparaisons[nom] = {'saute': 'moins de 1 000 matchs jugés'}
            continue
        pA, cA = construire(M, Y, A, retenu, c1A[0]), construire(M, Y, A, cand, c1A[0])
        gain = EB.log_loss(pA['P'], Y, idxB) - EB.log_loss(cA['P'], Y, idxB)
        pB, cB = construire(M, Y, B, retenu, c1B[0]), construire(M, Y, B, cand, c1B[0])
        inverse = EB.log_loss(pB['P'], Y, idxA) - EB.log_loss(cB['P'], Y, idxA)
        ok = gain >= MARGE and inverse > 0
        comparaisons[nom] = {'gain_juge': round(gain, 5), 'sens_inverse': round(inverse, 5), 'matchs_juges': len(idxB),
                             'retenu': ok}
        if ok:
            retenu = cand
    fin = construire(M, Y, A, retenu, c1A[0])
    P = fin['P']
    avant = E1.matchs_avant(M)
    par_epreuve = {}
    for ep in EB.EPREUVES:
        d = E1.decrire(P, Y, [i for i in B if M[i][2] == ep], avant)
        d['tient'] = E1.tient(d)
        par_epreuve[ep] = d
    tout = E1.decrire(P, Y, B, avant)
    tout['tient'] = E1.tient(tout)
    return {'periodes': {'apprentissage': len(A), 'jugement': len(B), 'lancement_non_juge': len(M) - len(A) - len(B)},
            'c1_reglage_appris': list(c1A[0]), 'c1_en_butee': butee(c1A[0]),
            'comparaisons': comparaisons,
            'modele_retenu': {'grille_elargie': retenu['c1'], 'pente': retenu['pente'], 'doubles_au_joueur': retenu['joueurs'],
                              'reglage': list(fin['reglage']), 'betas': fin['betas']},
            'jugement_toutes_epreuves': tout, 'jugement_par_epreuve': par_epreuve,
            'peu_connus_doubles_joueur_pct': peu_connus_joueurs(M, doubles_B),
            'verdict': 'l_elo_tient' if tout['tient'] else 'l_elo_ne_tient_pas'}


def butee(x):
    """Les cases du réglage appris qui sont au bord de la grille (à lire : la grille était peut-être trop étroite)."""
    bords = {'a': (100, 800), 'c': (0, 0.3), 'w': (0.25, 0.75), 's': (16, 32)}
    return [k for k, v in zip('acws', x) if v in bords[k]]


def peu_connus_joueurs(M, idx):
    """Part des matchs de double (idx) où le joueur le moins connu des quatre a moins de 5 matchs de double avant."""
    N, moins = {}, {}
    for i, m in enumerate(M):
        if len(m) > 9 and m[9]:
            js = list(m[9][0]) + list(m[9][1])
            moins[i] = min(N.get(j, 0) for j in js)
            for j in js:
                N[j] = N.get(j, 0) + 1
    J = [i for i in idx if i in moins]
    return round(100 * sum(1 for i in J if moins[i] < E1.PEU_CONNU) / len(J), 1) if J else None


# ------------------------------------------------------------------ rapport
def etudier(M, comptes=None, journal=print):
    if not M:
        journal('badminton étape 2 : aucun match gardé')
        return {'verdict': 'donnees_insuffisantes'}
    coeur = juger(M)
    rep = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'etude': 'etape2_badminton',
           'regle_ecrite_le': '2026-11-27',
           'donnees': dict(comptes or {}, premier_jour=M[0][1], dernier_jour=M[-1][1], matchs_gardes=len(M),
                           doubles_paire_illisible=sum(1 for m in M if m[2].startswith('double') and not m[9]),
                           joueurs_de_double=len({n for m in M if m[9] for x in m[9] for n in x}))}
    rep.update(coeur)
    journal(f"badminton étape 2 : {len(M)} matchs gardés ({M[0][1]} → {M[-1][1]})")
    if coeur['verdict'] == 'donnees_insuffisantes':
        journal('  pas assez de matchs')
        return rep
    journal(f"  C1 réglage appris (a, c, w, s) = {coeur['c1_reglage_appris']}, au bord de la grille : {coeur['c1_en_butee'] or 'rien'}")
    for k, v in coeur['comparaisons'].items():
        if 'saute' in v:
            journal(f"  {k} = sauté ({v['saute']})")
        else:
            journal(f"  {k} = gain jugé {v['gain_juge']:+.5f} sur {v['matchs_juges']} matchs, sens inverse "
                    f"{v['sens_inverse']:+.5f} → {'retenu' if v['retenu'] else 'non'}")
    mr, tout = coeur['modele_retenu'], coeur['jugement_toutes_epreuves']
    journal(f"  modèle retenu = grille élargie {mr['grille_elargie']}, pente {mr['pente']}, doubles au joueur "
            f"{mr['doubles_au_joueur']}, réglage {mr['reglage']}, β {mr['betas']}")
    journal(f"  tout ensemble = {tout['matchs']} matchs, log loss {tout['log_loss']}, Brier {tout['brier']}, bons vainqueurs "
            f"{tout['bons_vainqueurs_pct']} %, pente {tout['pente_etalonnage']} → {'tient' if tout['tient'] else 'ne tient pas'}")
    for ep, d in coeur['jugement_par_epreuve'].items():
        journal(f"  {ep} = {d['matchs']} matchs, log loss {d.get('log_loss')}, Brier {d.get('brier')}, bons vainqueurs "
                f"{d.get('bons_vainqueurs_pct')} %, pente {d.get('pente_etalonnage')}{' → tient' if d['tient'] else ' → ne tient pas'}")
    for tr, d in tout['par_tranche'].items():
        journal(f"  favori {tr} = {d['matchs']} matchs, annoncé {d['favori_annonce_pct']} %, réel {d['favori_reel_pct']} %")
    journal(f"  doubles jugés, joueur le moins connu à moins de 5 matchs = {coeur['peu_connus_doubles_joueur_pct']} %")
    S = [m for m in M if not m[7]]
    if len(S) < len(M):
        sans = juger(S, premier_jour=M[0][1])
        rep['sans_hors_circuit_publie_sans_decider'] = dict(sans, matchs_retires=len(M) - len(S))
        if sans['verdict'] != 'donnees_insuffisantes':
            t2, m2 = sans['jugement_toutes_epreuves'], sans['modele_retenu']
            journal(f"  sans la série hors circuits ({len(M) - len(S)} matchs retirés, sans décider) = pente {m2['pente']}, "
                    f"doubles au joueur {m2['doubles_au_joueur']}, log loss {t2['log_loss']}, pente du jugement "
                    f"{t2['pente_etalonnage']}, épreuves qui tiennent "
                    f"{sum(1 for d in sans['jugement_par_epreuve'].values() if d['tient'])}/5")
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
