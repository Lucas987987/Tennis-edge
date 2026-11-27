#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_etape3_badminton.py — BADMINTON, ÉTAPE 3 : PENTE GLISSANTE, GRILLE DE LA MARGE ÉLARGIE
(27/11/2026, Lucas : « lance l'étape 3 »).

Constat de l'étape 2 (badminton/etude_etape2_badminton.py, jugement 2023 → 26/11/2026, 42 924 matchs) : modèle retenu
= grille élargie (a = 200, c = 0,2, w = 0,75, s = 32, w et s au bord de la grille) + doubles au joueur ; log loss
0,5546, 70,5 % de bons vainqueurs, mais pente 1,189 (trop prudent) ; la pente apprise sur 2021–2022 (1,13) ne suffit
pas (gain 0,00095) alors que le jugement en demande ~1,19, à peu près stable d'une année à l'autre. Rien n'est publié
sur le site ; aucune cote n'est lue ; aucun conseil.

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI (mêmes données, filtres et périodes que les étapes 1 et 2 : lancement
120 jours non jugés, APPRENTISSAGE jusqu'au 31/12/2022, JUGEMENT une seule fois du 01/01/2023 au dernier jour) :
  Départ = le modèle retenu à l'étape 2 : a = 200, c = 0,2, w = 0,75, s = 32, doubles au joueur, sans pente.
  D1  même modèle, grille élargie (doubles au joueur), réglée sur l'apprentissage seulement :
        a ∈ {100, 200, 400}, c ∈ {0,1 ; 0,2 ; 0,3}, w ∈ {0,6 ; 0,75 ; 0,9 ; 1}, s ∈ {24, 32, 48, 64}.
  D2a le modèle retenu jusque-là + PENTE GLISSANTE : p → σ(β · logit p), β réappris au début de chaque mois sur les
        matchs des 365 jours précédents (le passé seulement), s'il y en a au moins 1 000 ; sinon β = 1.
  D2b comme D2a, mais un β par épreuve (au moins 1 000 matchs de l'épreuve sur les 365 jours ; sinon le β de D2a).
  Q1. Dans l'ordre D1, D2a, D2b (contre D2a) : un candidat remplace le modèle retenu seulement s'il gagne au moins 0,001
      de log loss par match sur le jugement ET dans le même sens sur l'autre période. Pour D1 l'autre période = réglé
      sur le jugement, jugé sur l'apprentissage (comme avant). Pour D2a et D2b, la pente glissante n'utilise que le
      passé : l'autre période = le gain mesuré sur l'apprentissage, avec les réglages de l'Elo du modèle retenu.
  Q2. Comme aux étapes 1 et 2 : « l'Elo tient » pour une épreuve si, sur au moins 1 000 matchs jugés, la log loss bat le
      pile ou face d'au moins 0,02 ET la pente d'étalonnage du jugement est entre 0,85 et 1,15. Épreuve par épreuve,
      puis tout ensemble.
  Publiés sans décider : Brier, % de bons vainqueurs, favori annoncé contre réel par tranche, les β mensuels (moyenne,
      plus bas, plus haut sur le jugement), le réglage D1 au bord de la grille, la pente du jugement année par année,
      et le même jugement sans la série locale hors circuits (Armenia Infinity Cup, 2021–2022).

Rapport : badminton/rapport_etape3_badminton.json — comptes et moyennes seulement, aucun nom de joueur.
Usage : python badminton/etude_etape3_badminton.py [racine]
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

DEPART_REGLAGE = (200, 0.2, 0.75, 32)
GRILLE_D1 = list(itertools.product((100, 200, 400), (0.1, 0.2, 0.3), (0.6, 0.75, 0.9, 1.0), (24, 32, 48, 64)))
BORDS_D1 = {'a': (100, 400), 'c': (0.1, 0.3), 'w': (0.6, 1.0), 's': (24, 64)}
FENETRE_J, MIN_FENETRE = 365, 1000
MARGE, MIN_JUGES = E1.MARGE, E1.MIN_JUGES
SORTIE = os.path.join(ICI, 'rapport_etape3_badminton.json')


def mois_de(m):
    return m[1][:7]


def debut_du_mois(mois):
    return dt.date.fromisoformat(mois + '-01')


def pentes_glissantes(P, Y, M, par_epreuve=False):
    """{mois: β} (ou {mois: {épreuve: β}}) appris au début de chaque mois sur les 365 jours précédents (passé seul)."""
    jours = [dt.date.fromisoformat(m[1]) for m in M]
    out, i0 = {}, 0
    for mois in sorted({mois_de(m) for m in M}):
        d = debut_du_mois(mois)
        lo = d - dt.timedelta(days=FENETRE_J)
        while i0 < len(M) and jours[i0] < lo:
            i0 += 1
        idx = []
        i = i0
        while i < len(M) and jours[i] < d:
            idx.append(i)
            i += 1
        b = EB.pente(P, Y, idx) if len(idx) >= MIN_FENETRE else 1.0
        if not par_epreuve:
            out[mois] = b
            continue
        par = {}
        for ep in EB.EPREUVES:
            J = [k for k in idx if M[k][2] == ep]
            par[ep] = EB.pente(P, Y, J) if len(J) >= MIN_FENETRE else b
        out[mois] = par
    return out


def appliquer_glissant(P, M, betas, par_epreuve=False):
    out = []
    for p, m in zip(P, M):
        b = betas.get(mois_de(m), 1.0)
        if par_epreuve:
            b = b.get(m[2], 1.0) if isinstance(b, dict) else b
        out.append(1.0 / (1.0 + math.exp(-b * E2.logit(p))))
    return out


def regler_d1(M, Y, idx):
    meilleur = None
    for x in GRILLE_D1:
        ll = EB.log_loss(E2.rejouer(M, *x, joueurs=True), Y, idx)
        if meilleur is None or ll < meilleur[1]:
            meilleur = (x, ll)
    return meilleur


def predire(M, Y, reglage, pente):
    """P d'un modèle : réglage de l'Elo (doubles au joueur) + pente None | 'une' | 'epreuve' (glissante)."""
    Pb = E2.rejouer(M, *reglage, joueurs=True)
    if pente is None:
        return Pb, None
    pe = pente == 'epreuve'
    betas = pentes_glissantes(Pb, Y, M, pe)
    return appliquer_glissant(Pb, M, betas, pe), betas


def resume_betas(betas, M, idx):
    mois = sorted({mois_de(M[i]) for i in idx})
    if not betas or not mois:
        return None
    vals = [betas[m] for m in mois if m in betas]
    if vals and isinstance(vals[0], dict):
        return {ep: {'moyenne': round(sum(v[ep] for v in vals) / len(vals), 3), 'plus_bas': round(min(v[ep] for v in vals), 3),
                     'plus_haut': round(max(v[ep] for v in vals), 3)} for ep in EB.EPREUVES}
    return {'moyenne': round(sum(vals) / len(vals), 3), 'plus_bas': round(min(vals), 3), 'plus_haut': round(max(vals), 3)}


def juger(M, premier_jour=None):
    Y = [m[5] for m in M]
    A, B = E1.periodes(M, premier_jour)
    if len(A) < MIN_JUGES or len(B) < MIN_JUGES:
        return {'verdict': 'donnees_insuffisantes', 'apprentissage': len(A), 'jugement': len(B)}
    comparaisons = {}
    # D1 : grille élargie (réglée sur l'apprentissage ; sens inverse = réglée sur le jugement, jugée sur l'apprentissage)
    d1A, d1B = regler_d1(M, Y, A), regler_d1(M, Y, B)
    P0 = E2.rejouer(M, *DEPART_REGLAGE, joueurs=True)
    P1A, P1B = E2.rejouer(M, *d1A[0], joueurs=True), E2.rejouer(M, *d1B[0], joueurs=True)
    gain = EB.log_loss(P0, Y, B) - EB.log_loss(P1A, Y, B)
    inverse = EB.log_loss(P0, Y, A) - EB.log_loss(P1B, Y, A)
    ok = gain >= MARGE and inverse > 0
    comparaisons['D1'] = {'gain_juge': round(gain, 5), 'sens_inverse': round(inverse, 5), 'retenu': ok}
    reglage = d1A[0] if ok else DEPART_REGLAGE
    pente = None
    P, betas = predire(M, Y, reglage, None)
    for nom, cand in (('D2a', 'une'), ('D2b', 'epreuve')):
        if nom == 'D2b' and pente != 'une':
            comparaisons[nom] = {'saute': 'D2a non retenu'}
            continue
        Pc, bc = predire(M, Y, reglage, cand)
        gain = EB.log_loss(P, Y, B) - EB.log_loss(Pc, Y, B)
        autre = EB.log_loss(P, Y, A) - EB.log_loss(Pc, Y, A)
        ok = gain >= MARGE and autre > 0
        comparaisons[nom] = {'gain_juge': round(gain, 5), 'sens_inverse': round(autre, 5), 'retenu': ok}
        if ok:
            pente, P, betas = cand, Pc, bc
    avant = E1.matchs_avant(M)
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
            'd1_reglage_appris': list(d1A[0]),
            'd1_au_bord': [k for k, v in zip('acws', d1A[0]) if v in BORDS_D1[k]],
            'comparaisons': comparaisons,
            'modele_retenu': {'reglage': list(reglage), 'doubles_au_joueur': True, 'pente_glissante': pente,
                              'betas_sur_le_jugement': resume_betas(betas, M, B)},
            'jugement_toutes_epreuves': tout, 'jugement_par_epreuve': par_epreuve, 'pente_du_jugement_par_an': par_an,
            'verdict': 'l_elo_tient' if tout['tient'] else 'l_elo_ne_tient_pas'}


def etudier(M, comptes=None, journal=print):
    if not M:
        journal('badminton étape 3 : aucun match gardé')
        return {'verdict': 'donnees_insuffisantes'}
    coeur = juger(M)
    rep = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'etude': 'etape3_badminton',
           'regle_ecrite_le': '2026-11-27',
           'donnees': dict(comptes or {}, premier_jour=M[0][1], dernier_jour=M[-1][1], matchs_gardes=len(M))}
    rep.update(coeur)
    journal(f"badminton étape 3 : {len(M)} matchs gardés ({M[0][1]} → {M[-1][1]})")
    if coeur['verdict'] == 'donnees_insuffisantes':
        journal('  pas assez de matchs')
        return rep
    journal(f"  D1 réglage appris (a, c, w, s) = {coeur['d1_reglage_appris']}, au bord de la grille : {coeur['d1_au_bord'] or 'rien'}")
    for k, v in coeur['comparaisons'].items():
        if 'saute' in v:
            journal(f"  {k} = sauté ({v['saute']})")
        else:
            journal(f"  {k} = gain jugé {v['gain_juge']:+.5f}, autre période {v['sens_inverse']:+.5f} → {'retenu' if v['retenu'] else 'non'}")
    mr, tout = coeur['modele_retenu'], coeur['jugement_toutes_epreuves']
    journal(f"  modèle retenu = réglage {mr['reglage']}, doubles au joueur, pente glissante {mr['pente_glissante']}, "
            f"β sur le jugement {mr['betas_sur_le_jugement']}")
    journal(f"  tout ensemble = {tout['matchs']} matchs, log loss {tout['log_loss']}, Brier {tout['brier']}, bons vainqueurs "
            f"{tout['bons_vainqueurs_pct']} %, pente {tout['pente_etalonnage']} → {'tient' if tout['tient'] else 'ne tient pas'}")
    for ep, d in coeur['jugement_par_epreuve'].items():
        journal(f"  {ep} = {d['matchs']} matchs, log loss {d.get('log_loss')}, Brier {d.get('brier')}, bons vainqueurs "
                f"{d.get('bons_vainqueurs_pct')} %, pente {d.get('pente_etalonnage')}{' → tient' if d['tient'] else ' → ne tient pas'}")
    for tr, d in tout['par_tranche'].items():
        journal(f"  favori {tr} = {d['matchs']} matchs, annoncé {d['favori_annonce_pct']} %, réel {d['favori_reel_pct']} %")
    journal('  pente du jugement par an : ' + ', '.join(f"{an} {v['pente_etalonnage']}" for an, v in coeur['pente_du_jugement_par_an'].items()))
    S = [m for m in M if not m[7]]
    if len(S) < len(M):
        sans = juger(S, premier_jour=M[0][1])
        rep['sans_hors_circuit_publie_sans_decider'] = dict(sans, matchs_retires=len(M) - len(S))
        if sans['verdict'] != 'donnees_insuffisantes':
            t2, m2 = sans['jugement_toutes_epreuves'], sans['modele_retenu']
            journal(f"  sans la série hors circuits ({len(M) - len(S)} matchs retirés, sans décider) = pente glissante "
                    f"{m2['pente_glissante']}, log loss {t2['log_loss']}, pente du jugement {t2['pente_etalonnage']}, "
                    f"épreuves qui tiennent {sum(1 for d in sans['jugement_par_epreuve'].values() if d['tient'])}/5")
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
