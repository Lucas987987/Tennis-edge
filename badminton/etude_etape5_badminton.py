#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_etape5_badminton.py — BADMINTON, ÉTAPE 5 : L'ELO BOUGE-T-IL TROP APRÈS UNE SURPRISE ?
(27/11/2026, paquet 526, Lucas : « lance les 2 études badminton »).

Constat des études « outsider confirmé » (paquets 522–523) : au badminton, sur 2023 → 2026, l'outsider qui vient de
gagner un match en étant outsider, et qui est encore outsider au tour suivant, gagne 3 à 4 points de moins que les
autres outsiders de même % (retenu en double messieurs et en double mixte). Explication possible : après une surprise,
l'Elo (a = 400, c = 0,3 : il bouge vite) remonte trop fort le vainqueur. Rien n'est publié sur le site ; aucune cote
n'est lue ; aucun conseil.

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI (mêmes données que l'étape 4 — sans la série hors circuits —, mêmes
périodes : lancement 120 jours non jugés, APPRENTISSAGE jusqu'au 31/12/2022, JUGEMENT une seule fois du 01/01/2023 au
dernier jour) :
  Départ = le modèle retenu aux étapes 3 et 4 : a = 400, c = 0,3, w = 1, s = 32, doubles au joueur.
  H1  après une SURPRISE (le vainqueur avait moins de 50 % avant le match), la mise à jour des notes des joueurs du
      match est multipliée par m, m ∈ {0,5 ; 0,6 ; 0,7 ; 0,8 ; 0,9} réglé sur l'apprentissage ; sinon inchangée.
  Q1. H1 est RETENU s'il gagne au moins 0,001 de log loss par match sur le jugement ET dans le même sens quand on
      inverse (m réglé sur le jugement, jugé sur l'apprentissage).
  Q2. Comme aux étapes précédentes : « l'Elo tient » pour une épreuve si, sur au moins 1 000 matchs jugés, la log loss
      bat le pile ou face d'au moins 0,02 ET la pente d'étalonnage est entre 0,85 et 1,15 ; épreuve par épreuve, puis
      tout ensemble — pour le modèle retenu à la fin.
  Publiés sans décider : le même gain mesuré sur les seuls matchs des outsiders confirmés (comme les études 522–523), et
      sur les matchs qui suivent une surprise (l'un des deux joueurs a gagné son match précédent en outsider).
Rapport : badminton/rapport_etape5_badminton.json — comptes et moyennes seulement, aucun nom de joueur.
Usage : python badminton/etude_etape5_badminton.py [racine]
"""
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo_badminton as EB  # noqa: E402
import etude_elo_badminton as E1  # noqa: E402
import etude_etape2_badminton as E2  # noqa: E402

DEPART_REGLAGE = (400, 0.3, 1.0, 32)
GRILLE_M = [0.5, 0.6, 0.7, 0.8, 0.9]
MARGE, MIN_JUGES = E1.MARGE, E1.MIN_JUGES
FENETRE_S = 7 * 86400
SORTIE = os.path.join(ICI, 'rapport_etape5_badminton.json')


def rejouer(M, a, c, w, s, m_surprise=1.0):
    """Elo des étapes 3–4 (doubles au joueur) ; après une surprise, la mise à jour est multipliée par m_surprise."""
    import math
    d0 = E2.DEPART
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
        if (y == 1 and p < 0.5) or (y == 0 and p > 0.5):
            d *= m_surprise
        for x, sg in [(x, 1) for x in ch] + [(x, -1) for x in cb]:
            n = N.get(x, 0)
            R[x] = R.get(x, d0) + sg * a / (n + 5) ** c * d
            N[x] = n + 1
    return P


def apres_surprise(M, P):
    """(indices des matchs qui suivent une surprise, indices des outsiders confirmés) — le match précédent d'un camp
    (même épreuve) au plus 7 jours avant, gagné en outsider."""
    dernier, suit, conf = {}, [], []
    for i, m in enumerate(M):
        p = P[i]
        cs = [(m[3], p, m[5] == 1), (m[4], 1 - p, m[5] == 0)]
        s_ = c_ = False
        for e, pe, _ in cs:
            d = dernier.get(e)
            if d and 0 <= m[0] - d[0] <= FENETRE_S and d[1]:
                s_ = True
                if pe < 0.5:
                    c_ = True
        if s_:
            suit.append(i)
        if c_:
            conf.append(i)
        for e, pe, g in cs:
            dernier[e] = (m[0], g and pe < 0.5)
    return suit, conf


def juger(M, premier_jour):
    Y = [m[5] for m in M]
    A, B = E1.periodes(M, premier_jour)
    if len(A) < MIN_JUGES or len(B) < MIN_JUGES:
        return {'verdict': 'donnees_insuffisantes', 'apprentissage': len(A), 'jugement': len(B)}
    P0 = rejouer(M, *DEPART_REGLAGE)
    essais = {mm: rejouer(M, *DEPART_REGLAGE, m_surprise=mm) for mm in GRILLE_M}
    mA = min(GRILLE_M, key=lambda mm: EB.log_loss(essais[mm], Y, A))
    mB = min(GRILLE_M, key=lambda mm: EB.log_loss(essais[mm], Y, B))
    gain = EB.log_loss(P0, Y, B) - EB.log_loss(essais[mA], Y, B)
    inverse = EB.log_loss(P0, Y, A) - EB.log_loss(essais[mB], Y, A)
    ok = gain >= MARGE and inverse > 0
    P = essais[mA] if ok else P0
    suit, conf = apres_surprise(M, P0)
    sB, cB = [i for i in suit if i in set(B)], [i for i in conf if i in set(B)]
    sousens = {}
    for nom, idx in (('apres_une_surprise', sB), ('outsiders_confirmes', cB)):
        if idx:
            sousens[nom] = {'matchs': len(idx), 'gain_par_match': round(EB.log_loss(P0, Y, idx) - EB.log_loss(essais[mA], Y, idx), 5)}
    avant = E1.matchs_avant(M)
    par_epreuve = {}
    for ep in EB.EPREUVES:
        d = E1.decrire(P, Y, [i for i in B if M[i][2] == ep], avant)
        d['tient'] = E1.tient(d)
        par_epreuve[ep] = d
    tout = E1.decrire(P, Y, B, avant)
    tout['tient'] = E1.tient(tout)
    return {'periodes': {'apprentissage': len(A), 'jugement': len(B), 'lancement_non_juge': len(M) - len(A) - len(B)},
            'm_appris': mA, 'm_jugement': mB,
            'log_loss_par_m_apprentissage': {str(mm): round(EB.log_loss(essais[mm], Y, A), 5) for mm in GRILLE_M},
            'comparaison': {'gain_juge': round(gain, 5), 'sens_inverse': round(inverse, 5), 'retenu': ok},
            'publie_sans_decider': sousens,
            'modele_retenu': {'reglage': list(DEPART_REGLAGE), 'm_surprise': mA if ok else 1.0},
            'jugement_toutes_epreuves': tout, 'jugement_par_epreuve': par_epreuve,
            'verdict': 'l_elo_tient' if tout['tient'] else 'l_elo_ne_tient_pas'}


def etudier(M, comptes=None, journal=print):
    if not M:
        journal('badminton étape 5 : aucun match gardé')
        return {'verdict': 'donnees_insuffisantes'}
    premier = M[0][1]
    S = [m for m in M if not m[7]]
    coeur = juger(S, premier)
    rep = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'etude': 'etape5_badminton',
           'regle_ecrite_le': '2026-11-27', 'donnees': dict(comptes or {}, matchs_etudies=len(S), hors_circuit_retires=len(M) - len(S))}
    rep.update(coeur)
    journal(f"badminton étape 5 : {len(S)} matchs étudiés")
    if coeur['verdict'] == 'donnees_insuffisantes':
        journal('  pas assez de matchs')
        return rep
    c = coeur['comparaison']
    journal(f"  m appris {coeur['m_appris']} (sur le jugement : {coeur['m_jugement']}) ; log loss par m (apprentissage) "
            f"{coeur['log_loss_par_m_apprentissage']}")
    journal(f"  H1 = gain jugé {c['gain_juge']:+.5f}, sens inverse {c['sens_inverse']:+.5f} → {'retenu' if c['retenu'] else 'non'}")
    for k, v in coeur['publie_sans_decider'].items():
        journal(f"  sans décider · {k} : {v['matchs']} matchs, gain {v['gain_par_match']:+.5f} par match")
    tout = coeur['jugement_toutes_epreuves']
    journal(f"  modèle retenu {coeur['modele_retenu']} : log loss {tout['log_loss']}, bons vainqueurs {tout['bons_vainqueurs_pct']} %, "
            f"pente {tout['pente_etalonnage']} → {'tient' if tout['tient'] else 'ne tient pas'}")
    for ep, d in coeur['jugement_par_epreuve'].items():
        journal(f"  {ep} = {d['matchs']} matchs, log loss {d.get('log_loss')}, pente {d.get('pente_etalonnage')}"
                f"{' → tient' if d['tient'] else ' → ne tient pas'}")
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
