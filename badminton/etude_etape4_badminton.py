#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_etape4_badminton.py — BADMINTON, ÉTAPE 4 : LE VERDICT TIENT-IL SANS LA SÉRIE HORS CIRCUITS ?
(27/11/2026, Lucas : « oui pour l'étape 4 »).

Constat de l'étape 3 (badminton/etude_etape3_badminton.py) : avec a = 400, c = 0,3, w = 1, s = 32 et les doubles au
joueur, l'Elo tient (jugement 2023 → 26/11/2026 : log loss 0,5484, pente 1,094 ; 4 épreuves sur 5). Mais sans la série
locale hors circuits BWF (Armenia Infinity Cup, 8 804 matchs en 2021–2022, aucun dans le jugement), la pente remonte à
1,261 et une seule épreuve tient ; le réglage était au bord de la grille (a, c, w). Rien n'est publié sur le site ;
aucune cote n'est lue ; aucun conseil.

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI :
  Données : celles des étapes 1 à 3, SANS la série hors circuits (retirée partout : lancement, apprentissage, jugement).
  Périodes inchangées : lancement 120 jours à partir du premier jour collecté (01/01/2021), non jugés ; APPRENTISSAGE
      jusqu'au 31/12/2022 ; JUGEMENT une seule fois du 01/01/2023 au dernier jour.
  Départ = le modèle retenu à l'étape 3 : a = 400, c = 0,3, w = 1, s = 32, doubles au joueur, nouveaux à 1 500, sans pente.
  F1  même modèle, grille élargie, réglée sur l'apprentissage seulement :
        a ∈ {300, 400, 600, 800, 1200}, c ∈ {0,3 ; 0,4 ; 0,5 ; 0,6}, w ∈ {0,9 ; 1}, s ∈ {24, 32, 48}.
  F2  le modèle retenu jusque-là + une pente fixe apprise sur l'apprentissage : p → σ(β · logit p).
  F3  le modèle retenu jusque-là, mais un joueur ou une paire jamais vu part de 1 500 − δ (au lieu de 1 500),
        δ ∈ {50, 100, 150, 200} réglé sur l'apprentissage (la pente de F2, si retenue, réapprise avec chaque δ).
  Q1. Dans l'ordre F1, F2, F3 : un candidat remplace le modèle retenu seulement s'il gagne au moins 0,001 de log loss par
      match sur le jugement ET dans le même sens quand on inverse (tout réglé ou appris sur le jugement, jugé sur
      l'apprentissage).
  Q2. Comme aux étapes 1 à 3 : « l'Elo tient » pour une épreuve si, sur au moins 1 000 matchs jugés, la log loss bat le
      pile ou face d'au moins 0,02 ET la pente d'étalonnage du jugement est entre 0,85 et 1,15. Épreuve par épreuve,
      puis tout ensemble.
  DÉCISION écrite avant : on prépare le produit badminton seulement si Q2 dit « tient » tout ensemble ici (sans la
      série hors circuits). Sinon, on s'arrête et on regarde pourquoi.
  Publiés sans décider : Brier, % de bons vainqueurs, favori annoncé contre réel par tranche, le réglage au bord de la
      grille, β et δ appris, la pente du jugement année par année, et le modèle de l'étape 3 tel quel sur ces données.

Rapport : badminton/rapport_etape4_badminton.json — comptes et moyennes seulement, aucun nom de joueur.
Usage : python badminton/etude_etape4_badminton.py [racine]
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
import etude_etape2_badminton as E2  # noqa: E402

DEPART_REGLAGE = (400, 0.3, 1.0, 32)
GRILLE_F1 = list(itertools.product((300, 400, 600, 800, 1200), (0.3, 0.4, 0.5, 0.6), (0.9, 1.0), (24, 32, 48)))
BORDS_F1 = {'a': (300, 1200), 'c': (0.3, 0.6), 'w': (0.9, 1.0), 's': (24, 48)}
GRILLE_F3 = [50, 100, 150, 200]
MARGE, MIN_JUGES = E1.MARGE, E1.MIN_JUGES
SORTIE = os.path.join(ICI, 'rapport_etape4_badminton.json')


def rejouer(M, a, c, w, s, delta=0):
    """Elo des étapes 2–3 (doubles au joueur) ; un joueur ou une paire jamais vu part de 1 500 − delta."""
    d0 = E2.DEPART - delta
    R, N, P = {}, {}, []
    for m in M:
        y, sp = m[5], m[6]
        noms = m[9] if len(m) > 9 else None
        ch, cb = ([('d', x) for x in noms[0]], [('d', x) for x in noms[1]]) if noms else ([m[3]], [m[4]])
        rh = sum(R.get(x, d0) for x in ch) / len(ch)
        rb = sum(R.get(x, d0) for x in cb) / len(cb)
        p = 1.0 / (1.0 + 10 ** (-(rh - rb) / 400.0))
        P.append(p)
        cible = (1 - w) * y + w * (1.0 / (1.0 + math.exp(-(sp - 0.5) * s))) if w else y
        d = cible - p
        for x, sg in [(x, 1) for x in ch] + [(x, -1) for x in cb]:
            n = N.get(x, 0)
            R[x] = R.get(x, d0) + sg * a / (n + 5) ** c * d
            N[x] = n + 1
    return P


def construire(M, Y, idx, reglage, pente, delta, grille_delta=False):
    """(P, β, δ) d'un modèle appris sur idx. grille_delta : δ réglé sur idx dans GRILLE_F3."""
    def un(dl):
        Pb = rejouer(M, *reglage, delta=dl)
        b = round(EB.pente(Pb, Y, idx), 4) if pente else None
        P = E2.appliquer(Pb, b, M) if pente else Pb
        return EB.log_loss(P, Y, idx), P, b, dl
    if not grille_delta:
        _, P, b, dl = un(delta)
        return P, b, dl
    _, P, b, dl = min((un(dl) for dl in GRILLE_F3), key=lambda t: t[0])
    return P, b, dl


def regler_f1(M, Y, idx):
    return min(((x, EB.log_loss(rejouer(M, *x), Y, idx)) for x in GRILLE_F1), key=lambda t: t[1])


def juger(M, premier_jour):
    Y = [m[5] for m in M]
    A, B = E1.periodes(M, premier_jour)
    if len(A) < MIN_JUGES or len(B) < MIN_JUGES:
        return {'verdict': 'donnees_insuffisantes', 'apprentissage': len(A), 'jugement': len(B)}
    avant = E1.matchs_avant(M)
    comparaisons = {}
    # Le modèle de l'étape 3 tel quel (publié sans décider)
    P3 = rejouer(M, *DEPART_REGLAGE)
    etape3 = E1.decrire(P3, Y, B, avant)
    etape3['tient'] = E1.tient(etape3)
    # F1
    f1A, f1B = regler_f1(M, Y, A), regler_f1(M, Y, B)
    gain = EB.log_loss(P3, Y, B) - EB.log_loss(rejouer(M, *f1A[0]), Y, B)
    inverse = EB.log_loss(P3, Y, A) - EB.log_loss(rejouer(M, *f1B[0]), Y, A)
    ok = gain >= MARGE and inverse > 0
    comparaisons['F1'] = {'gain_juge': round(gain, 5), 'sens_inverse': round(inverse, 5), 'retenu': ok}
    regA, regB = (f1A[0], f1B[0]) if ok else (DEPART_REGLAGE, DEPART_REGLAGE)
    pente, delta_grille = False, False
    for nom, chg in (('F2', 'pente'), ('F3', 'delta')):
        cp, cd = (True, delta_grille) if chg == 'pente' else (pente, True)
        PA_ret = construire(M, Y, A, regA, pente, 0, delta_grille)[0]
        PA_can = construire(M, Y, A, regA, cp, 0, cd)[0]
        PB_ret = construire(M, Y, B, regB, pente, 0, delta_grille)[0]
        PB_can = construire(M, Y, B, regB, cp, 0, cd)[0]
        gain = EB.log_loss(PA_ret, Y, B) - EB.log_loss(PA_can, Y, B)
        inverse = EB.log_loss(PB_ret, Y, A) - EB.log_loss(PB_can, Y, A)
        ok = gain >= MARGE and inverse > 0
        comparaisons[nom] = {'gain_juge': round(gain, 5), 'sens_inverse': round(inverse, 5), 'retenu': ok}
        if ok:
            pente, delta_grille = cp, cd
    P, beta, delta = construire(M, Y, A, regA, pente, 0, delta_grille)
    par_epreuve = {}
    for ep in EB.EPREUVES:
        d = E1.decrire(P, Y, [i for i in B if M[i][2] == ep], avant)
        d['tient'] = E1.tient(d)
        par_epreuve[ep] = d
    tout = E1.decrire(P, Y, B, avant)
    tout['tient'] = E1.tient(tout)
    par_an = {}
    for an in sorted({M[i][1][:4] for i in B}):
        J = [i for i in B if M[i][1][:4] == an]
        par_an[an] = {'matchs': len(J), 'pente_etalonnage': round(EB.pente(P, Y, J), 3)}
    return {'periodes': {'apprentissage': len(A), 'jugement': len(B), 'lancement_non_juge': len(M) - len(A) - len(B)},
            'etape3_tel_quel_publie_sans_decider': etape3,
            'f1_reglage_appris': list(f1A[0]), 'f1_au_bord': [k for k, v in zip('acws', f1A[0]) if v in BORDS_F1[k]],
            'comparaisons': comparaisons,
            'modele_retenu': {'reglage': list(regA), 'doubles_au_joueur': True, 'pente': beta, 'delta_nouveaux': delta},
            'jugement_toutes_epreuves': tout, 'jugement_par_epreuve': par_epreuve, 'pente_du_jugement_par_an': par_an,
            'verdict': 'l_elo_tient' if tout['tient'] else 'l_elo_ne_tient_pas',
            'decision': 'preparer_le_produit' if tout['tient'] else 's_arreter_et_regarder_pourquoi'}


def etudier(M, comptes=None, journal=print):
    if not M:
        journal('badminton étape 4 : aucun match gardé')
        return {'verdict': 'donnees_insuffisantes'}
    premier = M[0][1]
    S = [m for m in M if not m[7]]
    coeur = juger(S, premier)
    rep = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'etude': 'etape4_badminton',
           'regle_ecrite_le': '2026-11-27',
           'donnees': dict(comptes or {}, premier_jour=premier, dernier_jour=M[-1][1], matchs_gardes=len(M),
                           hors_circuit_retires=len(M) - len(S), matchs_etudies=len(S))}
    rep.update(coeur)
    journal(f"badminton étape 4 : {len(S)} matchs étudiés ({len(M) - len(S)} hors circuits retirés, {premier} → {M[-1][1]})")
    if coeur['verdict'] == 'donnees_insuffisantes':
        journal('  pas assez de matchs')
        return rep
    p = coeur['periodes']
    journal(f"  lancement {p['lancement_non_juge']}, apprentissage {p['apprentissage']}, jugement {p['jugement']}")
    e3 = coeur['etape3_tel_quel_publie_sans_decider']
    journal(f"  modèle de l'étape 3 tel quel (sans décider) = log loss {e3['log_loss']}, pente {e3['pente_etalonnage']}")
    journal(f"  F1 réglage appris (a, c, w, s) = {coeur['f1_reglage_appris']}, au bord de la grille : {coeur['f1_au_bord'] or 'rien'}")
    for k, v in coeur['comparaisons'].items():
        journal(f"  {k} = gain jugé {v['gain_juge']:+.5f}, sens inverse {v['sens_inverse']:+.5f} → {'retenu' if v['retenu'] else 'non'}")
    mr, tout = coeur['modele_retenu'], coeur['jugement_toutes_epreuves']
    journal(f"  modèle retenu = réglage {mr['reglage']}, doubles au joueur, pente {mr['pente']}, nouveaux à 1500 − {mr['delta_nouveaux']}")
    journal(f"  tout ensemble = {tout['matchs']} matchs, log loss {tout['log_loss']}, Brier {tout['brier']}, bons vainqueurs "
            f"{tout['bons_vainqueurs_pct']} %, pente {tout['pente_etalonnage']} → {'tient' if tout['tient'] else 'ne tient pas'}")
    for ep, d in coeur['jugement_par_epreuve'].items():
        journal(f"  {ep} = {d['matchs']} matchs, log loss {d.get('log_loss')}, Brier {d.get('brier')}, bons vainqueurs "
                f"{d.get('bons_vainqueurs_pct')} %, pente {d.get('pente_etalonnage')}{' → tient' if d['tient'] else ' → ne tient pas'}")
    for tr, d in tout['par_tranche'].items():
        journal(f"  favori {tr} = {d['matchs']} matchs, annoncé {d['favori_annonce_pct']} %, réel {d['favori_reel_pct']} %")
    journal('  pente du jugement par an : ' + ', '.join(f"{an} {v['pente_etalonnage']}" for an, v in coeur['pente_du_jugement_par_an'].items()))
    journal(f"  décision : {coeur['decision']}")
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
