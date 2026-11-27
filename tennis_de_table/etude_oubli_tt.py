#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_oubli_tt.py — TENNIS DE TABLE : UN ELO QUI OUBLIE PLUS VITE FAIT-IL MIEUX ? (27/11/2026, paquet 503,
Lucas : « fais les 4 »).

Pourquoi : dans l'Elo E2 retenu (étude 487), K = a / (n + 5)^c baisse sans fin avec le nombre n de matchs déjà joués.
Les joueurs polonais ont des milliers de matchs : leur Elo ne bouge presque plus et peut suivre avec retard un vrai
changement de forme.

TÉMOIN (le % en production) : Elo E2 au réglage appris en 487 (lu dans rapport_elo_tt.json), puis la pente propre aux
ligues retenues à l'étape 2 (lue dans rapport_etape2_tt.json : σ(pente · logit p)).

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI. Mêmes périodes que 487, 494 et 496 (120 jours de lancement,
apprentissage jusqu'au 30/09/2025, JUGEMENT une seule fois du 01/10/2025 au dernier jour).
  Candidats (deux familles, grilles fixées ici ; a, c, w, s restent ceux du témoin) :
    O1 « plancher » : K = max(a / (n + 5)^c, a / (N + 5)^c), c'est-à-dire n plafonné à N ; N ∈ {50, 100, 200, 400, 800}.
    O2 « temps »    : avant chaque match, n_eff = n · 0,5^(jours depuis le match précédent du joueur / H),
                      K = a / (n_eff + 5)^c ; H ∈ {30, 90, 180, 365} jours. n continue d'augmenter de 1 par match :
                      l'oubli ne baisse que le n utilisé dans K. Jours = écart entre les heures de début (jamais négatif).
  Réglage : pour chaque famille, le réglage de meilleure log loss sur l'APPRENTISSAGE, TOUTES LIGUES ENSEMBLE (un seul
    réglage, pas un par ligue), la log loss étant celle du % complet (Elo du candidat puis la même pente de production).
    Puis la meilleure des deux familles sur l'apprentissage est LE candidat, unique (à égalité : O1, puis le premier
    réglage de la grille).
  Jugement, ligue par ligue, pour les ligues du produit (International et Pologne ; choix de Lucas). Le candidat est
    RETENU dans une ligue seulement si, sur au moins 1 000 matchs jugés de cette ligue :
      – sa log loss baisse d'au moins 0,001 par rapport au témoin ET d'au moins 2 erreurs types (différences match
        par match, appariées) ;
      – ET même sens : le candidat, au même réglage, bat aussi le témoin sur l'apprentissage de cette ligue (gain > 0).
        Pour cette étude, on ne règle PAS de nouveau le candidat sur le jugement (un seul réglage, appris sur
        l'apprentissage : cela garde l'étude courte et ne regarde pas le jugement une seconde fois).
  Les autres ligues sont publiées pour information, jamais « retenues ».
  Publié sans décider : la pente d'étalonnage du témoin et du candidat sur le jugement, pour les ligues du produit.
  Rien ne change en production avec cette étude : elle dit seulement si le candidat mérite d'être branché.
Rapport : tennis_de_table/rapport_oubli_tt.json (comptes et moyennes, aucun nom, aucun identifiant). Rien n'est publié
sur le site.
Usage : python tennis_de_table/etude_oubli_tt.py [racine]
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
SORTIE = os.path.join(ICI, 'rapport_oubli_tt.json')
LIGUES_PRODUIT = ('International', 'Poland')
GRILLE_O1 = [50, 100, 200, 400, 800]          # N : plafond de n
GRILLE_O2 = [30, 90, 180, 365]                # H : demi-vie en jours
MIN_JUGES, MARGE, ERREURS_TYPES = 1000, 0.001, 2.0
JOUR_S = 86400.0


def rejouer_oubli(M, a, c, w=0.0, s=20.0, plafond=None, demi_vie=None):
    """Elo E2 de ET.rejouer (même logique, même ordre), avec un K qui oublie : plafond (O1) = n plafonné à N ;
    demi_vie (O2) = n réduit de moitié tous les H jours sans match. Renvoie les p (pour h) AVANT chaque match."""
    R, N, T = {}, {}, {}
    P = []
    ap = P.append
    for m in M:
        t, h, b, y, sp = m[0], m[3], m[4], m[5], m[6]
        rh, rb = R.get(h, ET.DEPART), R.get(b, ET.DEPART)
        p = 1.0 / (1.0 + 10 ** (-(rh - rb) / 400.0))
        ap(p)
        if w:
            x = (sp - 0.5) * s
            cible = (1 - w) * y + w * (1.0 / (1.0 + math.exp(-x)))
        else:
            cible = y
        nh, nb = N.get(h, 0), N.get(b, 0)
        eh, eb = nh, nb
        if plafond is not None:
            if eh > plafond:
                eh = plafond
            if eb > plafond:
                eb = plafond
        if demi_vie is not None:
            th, tb = T.get(h), T.get(b)
            if th is not None and t > th:
                eh = eh * 0.5 ** ((t - th) / JOUR_S / demi_vie)
            if tb is not None and t > tb:
                eb = eb * 0.5 ** ((t - tb) / JOUR_S / demi_vie)
            T[h] = T[b] = t
        kh, kb = a / (eh + 5) ** c, a / (eb + 5) ** c
        d = cible - p
        R[h] = rh + kh * d
        R[b] = rb - kb * d
        N[h], N[b] = nh + 1, nb + 1
    return P


def avec_pentes(M, P, pentes):
    """Le % complet : la pente de production pour les ligues qui en ont une, l'Elo tel quel ailleurs."""
    if not pentes:
        return list(P)
    out = []
    for m, p in zip(M, P):
        a = pentes.get(m[2])
        out.append(E3._sg(a * E3._lg(p)) if a else p)
    return out


def parametres(famille, x):
    return {'plafond': x} if famille == 'O1' else {'demi_vie': x}


def regler(M, Y, idx, reglage_e2, pentes):
    """{famille: (réglage, log loss sur idx, P avec pentes)} : un seul réglage par famille, toutes ligues ensemble."""
    a, c, w, s = reglage_e2
    out, essais = {}, {}
    for famille, grille in (('O1', GRILLE_O1), ('O2', GRILLE_O2)):
        meilleur = None
        for x in grille:
            P = avec_pentes(M, rejouer_oubli(M, a, c, w, s, **parametres(famille, x)), pentes)
            ll = ET.log_loss(P, Y, idx)
            essais[f'{famille}_{x}'] = round(ll, 5)
            if meilleur is None or ll < meilleur[1]:
                meilleur = (x, ll, P)
        out[famille] = meilleur
    return out, essais


def comparer(Pt, Pc, Y, idx):
    """Gain de log loss du candidat sur le témoin (différences appariées, match par match) et son erreur type."""
    if not idx:
        return {'matchs': 0}
    d, tt = [], 0.0
    for i in idx:
        y = Y[i]
        pt, pc = min(max(Pt[i], 1e-6), 1 - 1e-6), min(max(Pc[i], 1e-6), 1 - 1e-6)
        lt = -math.log(pt if y else 1 - pt)
        lc = -math.log(pc if y else 1 - pc)
        tt += lt
        d.append(lt - lc)
    n = len(d)
    g = sum(d) / n
    et = math.sqrt(sum((x - g) ** 2 for x in d) / max(n - 1, 1)) / math.sqrt(n)
    return {'matchs': n, 'log_loss_temoin': round(tt / n, 5), 'log_loss_candidat': round(tt / n - g, 5),
            'gain': round(g, 5), 'erreur_type': round(et, 5)}


def etudier(M, reglage_e2, pentes, journal=print):
    A, B = EE.periodes(M)
    if len(A) < MIN_JUGES or len(B) < MIN_JUGES:
        journal(f'pas assez de matchs (apprentissage {len(A)}, jugement {len(B)})')
        return {'verdict': 'donnees_insuffisantes', 'apprentissage': len(A), 'jugement': len(B)}
    Y = [m[5] for m in M]
    a, c, w, s = reglage_e2
    Pt = avec_pentes(M, ET.rejouer(M, a=a, c=c, w=w, s=s), pentes)                 # le témoin : le % en production
    ll_t = ET.log_loss(Pt, Y, A)
    fam, essais = regler(M, Y, A, reglage_e2, pentes)                              # réglé sur l'apprentissage seulement
    choix = 'O1' if fam['O1'][1] <= fam['O2'][1] else 'O2'
    x, ll_c, Pc = fam[choix]
    ligues = sorted({M[i][2] for i in B} | set(LIGUES_PRODUIT))
    res = {}
    for lg in ligues:
        la, lb = [i for i in A if M[i][2] == lg], [i for i in B if M[i][2] == lg]
        produit = lg in LIGUES_PRODUIT
        cj, ca = comparer(Pt, Pc, Y, lb), comparer(Pt, Pc, Y, la)
        ok = bool(produit and cj.get('matchs', 0) >= MIN_JUGES and cj.get('gain', 0) >= MARGE
                  and cj.get('gain', 0) >= ERREURS_TYPES * cj.get('erreur_type', 1) and ca.get('gain', 0) > 0)
        v = dict(cj, produit=produit, matchs_apprentissage=len(la), gain_apprentissage=ca.get('gain'), retenu=ok)
        if produit and len(lb) >= MIN_JUGES:
            v['pente_etalonnage_temoin'] = round(ET.pente(Pt, Y, lb), 3)
            v['pente_etalonnage_candidat'] = round(ET.pente(Pc, Y, lb), 3)
        res[lg] = v
    retenues = [lg for lg in LIGUES_PRODUIT if res[lg]['retenu']]
    rep = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'paquet': PAQUET,
           'base_E2': list(reglage_e2), 'pentes_par_ligue': pentes, 'matchs': len(M), 'apprentissage': len(A),
           'jugement': len(B), 'grilles': {'O1_plafond_N': GRILLE_O1, 'O2_demi_vie_jours': GRILLE_O2},
           'log_loss_apprentissage': dict(essais, temoin=round(ll_t, 5)),
           'reglages_appris': {k: {'reglage': v[0], 'log_loss_apprentissage': round(v[1], 5)} for k, v in fam.items()},
           'candidat': {'famille': choix, 'reglage': x, 'log_loss_apprentissage': round(ll_c, 5),
                        'gain_apprentissage_toutes_ligues': round(ll_t - ll_c, 5)},
           'par_ligue': res, 'ligues_produit': list(LIGUES_PRODUIT), 'ligues_retenues': retenues,
           'verdict': 'candidat_retenu' if retenues else 'candidat_non_retenu'}
    journal(f"Elo qui oublie : {len(M)} matchs, apprentissage {len(A)}, jugement {len(B)}, témoin E2 {list(reglage_e2)}, "
            f"pentes {pentes}")
    journal(f"  apprentissage (toutes ligues) : témoin {ll_t:.5f} ; " + ', '.join(f'{k} {v}' for k, v in essais.items()))
    journal(f"  candidat : {choix} {'N' if choix == 'O1' else 'H'} = {x} (log loss d'apprentissage {ll_c:.5f}, "
            f"gain {ll_t - ll_c:+.5f})")
    for lg in sorted(res, key=lambda k: (not res[k]['produit'], k)):
        v = res[lg]
        if not v.get('matchs'):
            journal(f"  {lg}{' (produit)' if v['produit'] else ''} : aucun match jugé → non retenu")
            continue
        pe = (f" ; pente témoin {v['pente_etalonnage_temoin']}, candidat {v['pente_etalonnage_candidat']}"
              if 'pente_etalonnage_temoin' in v else '')
        journal(f"  {lg}{' (produit)' if v['produit'] else ' (pour information)'} : {v['matchs']} matchs jugés, log loss "
                f"témoin {v['log_loss_temoin']}, candidat {v['log_loss_candidat']}, gain {v['gain']} ± {v['erreur_type']}, "
                f"gain d'apprentissage {v['gain_apprentissage']}{pe}"
                f"{' → RETENU' if v['retenu'] else ' → non retenu' if v['produit'] else ''}")
    journal(f"  verdict : {'candidat retenu pour ' + ', '.join(retenues) if retenues else 'candidat non retenu'}")
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
