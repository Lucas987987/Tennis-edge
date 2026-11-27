#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_face_a_face_tt.py — TENNIS DE TABLE : LE FACE-À-FACE APPORTE-T-IL QUELQUE CHOSE AU-DELÀ DE L'ELO ? (27/11/2026,
paquet 503, Lucas : « fais les 4 »).

Pourquoi : en Pologne les mêmes joueurs se rencontrent des dizaines de fois ; il existe peut-être un effet propre à la
paire (opposition de styles) que l'Elo, joueur par joueur, ne voit pas.

TÉMOIN = le % en production : Elo E2 (étude 487, réglage lu dans rapport_elo_tt.json) puis, pour les ligues dont la
pente est retenue (étape 2, lue dans rapport_etape2_tt.json), p = σ(pente · logit p).

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI. Mêmes périodes que 487, 494 et 496 (120 jours de lancement, apprentissage
jusqu'au 30/09/2025, JUGEMENT une seule fois du 01/10/2025 au dernier jour).
  Mesure : pour chaque match, les rencontres PASSÉES de la MÊME paire seulement (dans un sens ou dans l'autre, toutes
      ligues, lancement compris), strictement avant le début t du match (deux matchs de même t ne se voient pas).
      Résidu d'une rencontre passée r = y − p_témoin, remis dans le sens du joueur h du match courant.
      x = Σ r / (n + k), n = nombre de rencontres passées, k = rétrécissement ; x = 0 sans rencontre passée.
      Aucun oubli des vieilles rencontres (pas de décroissance), aucune autre variable.
  Candidat : logit(p') = logit(p_témoin) + b · x. Ligue par ligue, sur l'apprentissage seulement : pour chaque k de la
      grille {5, 10, 20, 40}, b par maximum de vraisemblance ; on garde le k de plus petite log loss d'apprentissage
      (à égalité, le plus petit k).
  RETENU pour une ligue seulement si, sur au moins 1 000 matchs jugés de cette ligue :
      1. la log loss baisse d'au moins 0,001 par match contre le témoin sur le jugement,
      2. ET d'au moins 2 erreurs types (différences appariées match par match),
      3. ET même sens : le candidat réappris sur le jugement (k et b) puis appliqué à l'apprentissage y bat aussi le
         témoin (gain > 0),
      4. ET le coefficient b appris a le même signe sur les deux périodes.
  Ligues du produit (choix de Lucas) : International et Pologne, jugées séparément. Les autres ligues sont seulement
  décrites : jamais « retenu ».
  Publié sans décider : part des matchs jugés avec au moins 1, 5, 20 rencontres passées, et le gain restreint aux
  matchs avec au moins 5 rencontres passées.
  À garder en tête pour lire le résultat (écrit avant tout essai) : un gain peut aussi venir d'un Elo en retard sur le
  niveau des deux joueurs, pas seulement d'une opposition de styles ; l'étude mesure le gain, pas sa cause.
Rapport : tennis_de_table/rapport_face_a_face_tt.json (comptes, coefficients et moyennes, aucun nom, aucun identifiant).
Rien n'est publié sur le site.
Usage : python tennis_de_table/etude_face_a_face_tt.py [racine]
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
SORTIE = os.path.join(ICI, 'rapport_face_a_face_tt.json')
LIGUES_PRODUIT = ('International', 'Poland')
GRILLE_K = (5, 10, 20, 40)
MIN_JUGES, MARGE, ERREURS_TYPES = 1000, 0.001, 2.0
SEUILS_RENCONTRES = (1, 5, 20)
SEUIL_DESCRIPTIF = 5


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


# ------------------------------------------------------------------ témoin et mesure
def temoin(M, reglage_e2, pentes):
    """Le % en production (pour h) AVANT chaque match : Elo E2 puis pente de la ligue si elle est retenue."""
    a, c, w, s = reglage_e2
    P = ET.rejouer(M, a=a, c=c, w=w, s=s)
    for i, m in enumerate(M):
        pe = pentes.get(m[2])
        if pe:
            P[i] = _sg(pe * _lg(P[i]))
    return P


def rencontres_passees(M, P):
    """[(somme des résidus vus de h, nombre de rencontres passées)] pour chaque match, dans l'ordre de M (trié par t).
    Seules les rencontres de la même paire STRICTEMENT avant t comptent : les matchs de même t sont lus ensemble puis
    ajoutés ensemble."""
    H = {}                                   # (petit id, grand id) → [somme des résidus vus du petit id, nombre]
    out = [None] * len(M)
    i, n_tot = 0, len(M)
    while i < n_tot:
        j = i
        while j < n_tot and M[j][0] == M[i][0]:
            j += 1
        for q in range(i, j):
            h, a = M[q][3], M[q][4]
            e = H.get((h, a) if h < a else (a, h))
            out[q] = (0.0, 0) if e is None else (e[0] if h < a else -e[0], e[1])
        for q in range(i, j):
            h, a = M[q][3], M[q][4]
            r = M[q][5] - P[q]
            e = H.setdefault((h, a) if h < a else (a, h), [0.0, 0])
            e[0] += r if h < a else -r
            e[1] += 1
        i = j
    return out


def lignes(M, P, F, idx, ligue):
    """[(logit du témoin, somme des résidus, rencontres passées, y)] des matchs de la ligue parmi idx."""
    return [(_lg(P[i]), F[i][0], F[i][1], M[i][5]) for i in idx if M[i][2] == ligue]


def _perte(z, y):
    return math.log1p(math.exp(-z)) if y else math.log1p(math.exp(z))


def log_loss(L, k=None, b=0.0):
    """Log loss moyenne ; k = None : le témoin."""
    if not L:
        return float('nan')
    if k is None or not b:
        return sum(_perte(z, y) for z, _, _, y in L) / len(L)
    return sum(_perte(z + b * s / (n + k), y) for z, s, n, y in L) / len(L)


def apprendre_b(L, k, iters=25):
    """b du maximum de vraisemblance de σ(logit témoin + b · x), x = Σ r / (n + k) (Newton, problème concave)."""
    D = [(z, s / (n + k), y) for z, s, n, y in L if n]          # sans rencontre passée : x = 0, rien à apprendre
    b = 0.0
    for _ in range(iters):
        g = h = 0.0
        for z, x, y in D:
            q = _sg(z + b * x)
            g += (y - q) * x
            h -= q * (1 - q) * x * x
        if h >= -1e-12:
            break
        pas = max(min(g / h, 5.0), -5.0)
        b -= pas
        if abs(pas) < 1e-7:
            break
    return b


def apprendre(L):
    """Meilleur (k, b) sur L : {'k', 'b', 'log_loss_par_k'} ; à égalité de log loss, le plus petit k."""
    meilleur, par_k = None, {}
    for k in GRILLE_K:
        b = apprendre_b(L, k)
        ll = log_loss(L, k, b)
        par_k[str(k)] = {'b': round(b, 4), 'log_loss': None if ll != ll else round(ll, 5)}
        if meilleur is None or ll < meilleur[2]:
            meilleur = (k, b, ll)
    return {'k': meilleur[0], 'b': meilleur[1], 'log_loss_par_k': par_k}


def comparer(L, k, b):
    """Gain de log loss du candidat contre le témoin (différences appariées match par match) et son erreur type."""
    if not L:
        return {'matchs': 0}
    d = [_perte(z, y) - _perte(z + b * s / (n + k), y) for z, s, n, y in L]
    g = sum(d) / len(d)
    et = math.sqrt(sum((x - g) ** 2 for x in d) / max(len(d) - 1, 1)) / math.sqrt(len(d))
    lt = log_loss(L)
    return {'matchs': len(d), 'log_loss_temoin': lt, 'log_loss_candidat': lt - g, 'gain': g, 'erreur_type': et}


def _arrondi(c):
    return {k: (round(v, 5) if isinstance(v, float) else v) for k, v in c.items()}


def juger(la, lb, produit):
    """Applique la règle de l'en-tête à une ligue (la = apprentissage, lb = jugement)."""
    sa, sb = apprendre(la), apprendre(lb)
    cj = comparer(lb, sa['k'], sa['b'])
    inv = comparer(la, sb['k'], sb['b'])
    crit = {'au_moins_1000_juges': cj['matchs'] >= MIN_JUGES,
            'gain_au_moins_0_001': cj.get('gain', 0.0) >= MARGE,
            'gain_au_moins_2_erreurs_types': cj.get('gain', 0.0) >= ERREURS_TYPES * cj.get('erreur_type', float('inf')),
            'sens_inverse_positif': inv.get('gain', 0.0) > 0,
            'meme_signe_de_b': sa['b'] * sb['b'] > 0}
    nb = max(len(lb), 1)
    forts = [x for x in lb if x[2] >= SEUIL_DESCRIPTIF]
    desc = {f'part_au_moins_{s}_rencontres_pct': round(100 * sum(1 for x in lb if x[2] >= s) / nb, 1) for s in SEUILS_RENCONTRES}
    desc[f'au_moins_{SEUIL_DESCRIPTIF}_rencontres'] = _arrondi(comparer(forts, sa['k'], sa['b']))
    return {'produit': produit, 'matchs_apprentissage': len(la), 'matchs_juges': len(lb),
            'appris_sur_apprentissage': dict(sa, b=round(sa['b'], 4)),
            'appris_sur_jugement': dict(sb, b=round(sb['b'], 4)),
            'jugement': _arrondi(cj), 'sens_inverse': _arrondi(inv), 'criteres': {k: bool(v) for k, v in crit.items()},
            'retenu': bool(produit and all(crit.values())), 'descriptif': desc}


# ------------------------------------------------------------------ étude
def etudier(M, reglage_e2, pentes, journal=print):
    A, B = EE.periodes(M)
    if len(A) < MIN_JUGES or len(B) < MIN_JUGES:
        journal(f'pas assez de matchs (apprentissage {len(A)}, jugement {len(B)})')
        return {'verdict': 'donnees_insuffisantes'}
    P = temoin(M, reglage_e2, pentes)
    F = rencontres_passees(M, P)
    res = {}
    for lg in sorted({M[i][2] for i in B}):
        res[lg] = juger(lignes(M, P, F, A, lg), lignes(M, P, F, B, lg), lg in LIGUES_PRODUIT)
    retenues = [lg for lg in LIGUES_PRODUIT if res.get(lg, {}).get('retenu')]
    rep = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'paquet': PAQUET,
           'etude': 'face_a_face', 'base_E2': list(reglage_e2), 'pentes_par_ligue': pentes, 'grille_k': list(GRILLE_K),
           'apprentissage': len(A), 'jugement': len(B), 'par_ligue': res, 'ligues_produit': list(LIGUES_PRODUIT),
           'ligues_retenues': retenues, 'verdict': 'retenu' if retenues else 'non_retenu'}
    journal(f"face-à-face : {len(M)} matchs, apprentissage {len(A)}, jugement {len(B)}, pentes {pentes}")
    for lg in sorted(res, key=lambda k: (not res[k]['produit'], k)):
        v = res[lg]
        s, j, d = v['appris_sur_apprentissage'], v['jugement'], v['descriptif']
        f = d[f'au_moins_{SEUIL_DESCRIPTIF}_rencontres']
        journal(f"  {lg}{' (produit)' if v['produit'] else ' (décrit seulement)'} : {v['matchs_juges']} matchs jugés, "
                f"k {s['k']}, b {s['b']} (sur le jugement : k {v['appris_sur_jugement']['k']}, b {v['appris_sur_jugement']['b']}) ; "
                f"log loss témoin {j.get('log_loss_temoin')} → candidat {j.get('log_loss_candidat')}, "
                f"gain {j.get('gain')} ± {j.get('erreur_type')}, sens inverse {v['sens_inverse'].get('gain')}"
                f" → {'RETENU' if v['retenu'] else 'non retenu'}")
        journal('      rencontres passées : ' + ', '.join(f"≥{x} : {d[f'part_au_moins_{x}_rencontres_pct']} %" for x in SEUILS_RENCONTRES)
                + f" ; matchs avec ≥{SEUIL_DESCRIPTIF} ({f['matchs']}) : gain {f.get('gain')} ± {f.get('erreur_type')} (descriptif)")
    journal(f"  verdict : {'retenu pour ' + ', '.join(retenues) if retenues else 'non retenu'}")
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
