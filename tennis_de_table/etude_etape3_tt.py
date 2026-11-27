#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_etape3_tt.py — TENNIS DE TABLE, ÉTAPE 3 : LES SCORES EN MANCHES SONT-ILS BIEN ÉTALONNÉS ? (27/11/2026, paquet 496,
Lucas : « fais le »).

Point de départ : le % retenu = Elo E2 (étude 487), avec la pente propre à l'International et à l'Allemagne (étape 2,
paquet 494, lue dans rapport_etape2_tt.json : seules les pentes « retenues »). La simulation aux points n'a pas été
retenue pour le % ; on s'en sert ici seulement pour le SCÉNARIO, ancré sur le % : pour chaque match, on cherche la
probabilité de gagner un point q qui donne EXACTEMENT le % retenu (manches à 11, 2 d'écart ; match en 3 ou 4 manches
gagnantes, format connu avant le match), puis on en tire la distribution des scores en manches. Le scénario reste donc
cohérent avec le %, comme au tennis.

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI. Mêmes périodes que 487 et 494 (120 jours de lancement, apprentissage
jusqu'au 30/09/2025, JUGEMENT une seule fois du 01/10/2025 au dernier jour). Ligue par ligue :
  Q1. ÉTALONNAGE (descriptif, sur le jugement) : vu du favori, chaque score possible (favori 3-0, 3-1, 3-2, outsider 3-2,
      3-1, 3-0 ; de même en 4 manches gagnantes) : probabilité moyenne annoncée contre fréquence réelle, et la manche
      décisive. « Étalonné » si, sur au moins 1 000 matchs jugés, aucun score ne s'écarte de plus de 2 points.
  Q2. RECALAGE : une table apprise sur l'apprentissage (ligue × format × tranche de 5 points du % du favori : fréquence
      réelle de chaque score, rétrécie vers la distribution ancrée avec un poids de 50 matchs) remplace la distribution
      ancrée. Retenue si, sur au moins 1 000 matchs jugés, la log loss du score réel baisse d'au moins 0,001 ET de 2
      erreurs types, ET si la table apprise sur le jugement fait aussi mieux sur l'apprentissage (même sens).
  Le vainqueur annoncé et le % ne changent dans aucun cas (le recalage ne touche que la répartition des scores).
  Écartés de l'étude des scores (ajout du 27/11 après un run rouge, avant tout résultat) : les matchs dont le score en
  manches est à égalité (donnée incomplète) et les formats rares (2 ou 5 manches gagnantes) — 26 matchs sur 1,42 million.
  Ligues du produit (choix de Lucas) : International et Pologne, mises en avant.
Rapport : tennis_de_table/rapport_etape3_tt.json (comptes et moyennes, aucun nom). Rien n'est publié sur le site.
Usage : python tennis_de_table/etude_etape3_tt.py [racine]
"""
import bisect
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo_tt as ET  # noqa: E402
import etude_elo_tt as EE  # noqa: E402
import etude_etape2_tt as E2  # noqa: E402

PAQUET = 496
RAPPORT_487 = os.path.join(ICI, 'rapport_elo_tt.json')
RAPPORT_494 = os.path.join(ICI, 'rapport_etape2_tt.json')
SORTIE = os.path.join(ICI, 'rapport_etape3_tt.json')
LIGUES_PRODUIT = ('International', 'Poland')
MIN_JUGES, MARGE, ERREURS_TYPES, ECART_MAX_PTS, POIDS_A_PRIORI, TRANCHE = 1000, 0.001, 2.0, 2.0, 50.0, 0.05


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


# ------------------------------------------------------------------ distribution ancrée sur le %
QS = [0.2 + i * 1e-4 for i in range(6001)]                 # q de 0,20 à 0,80
TABLES = {}


def _table(n):
    if n not in TABLES:
        TABLES[n] = [E2.p_match(E2.p_manche(q), n) for q in QS]
    return TABLES[n]


def q_ancre(p, n):
    """q tel que p_match(p_manche(q), n) = p (table croissante, interpolation linéaire)."""
    T = _table(n)
    if p <= T[0]:
        return QS[0]
    if p >= T[-1]:
        return QS[-1]
    i = bisect.bisect_left(T, p)
    t0, t1 = T[i - 1], T[i]
    return QS[i - 1] + (QS[i] - QS[i - 1]) * ((p - t0) / (t1 - t0) if t1 > t0 else 0)


def categories(n):
    """Scores vus du favori : ('F', k) = favori gagne n-k ; ('O', k) = outsider gagne n-k."""
    return [('F', k) for k in range(n)] + [('O', k) for k in reversed(range(n))]


_MEMO = {}


def distribution(p_fav, n):
    """{('F'|'O', k): probabilité} ancrée sur le % du favori (mémorisée à 1/10 000 près du %)."""
    cle = (round(p_fav, 4), n)
    D = _MEMO.get(cle)
    if D is None:
        g = E2.p_manche(q_ancre(cle[0], n))
        S = E2.scores_manches(g, n)
        D = _MEMO[cle] = {('F', k): S[(n, k)] for k in range(n)} | {('O', k): S[(k, n)] for k in range(n)}
    return D


def categorie_reelle(m, fav_h, n):
    mh, ma = m[8]
    f, o = (mh, ma) if fav_h else (ma, mh)
    return ('F', o) if f == n else ('O', f)


# ------------------------------------------------------------------ étude
def pentes_retenues():
    try:
        with open(RAPPORT_494, encoding='utf-8') as f:
            A = json.load(f)['A_pente_par_ligue']
        return {lg: v['pente_apprise'] for lg, v in A.items() if v.get('retenue')}
    except (OSError, ValueError, KeyError):
        return {}


def lignes(M, P, pentes, idx):
    """[(ligue, n, p_fav, catégorie réelle)] sur les indices idx."""
    out = []
    for i in idx:
        m = M[i]
        mh, ma = m[8]
        if mh == ma or max(mh, ma) != m[7] or m[7] not in (3, 4):
            continue          # 27/11 : égalité de manches (donnée incomplète) ou format rare (2, 5 manches) — écartés
                              # de l'étude des scores (26 matchs sur 1,42 million) ; l'Elo, lui, est rejoué comme en 487
        p = P[i]
        a = pentes.get(m[2])
        if a:
            p = _sg(a * _lg(p))
        fav_h = p >= 0.5
        n = m[7]
        out.append((m[2], n, p if fav_h else 1 - p, categorie_reelle(m, fav_h, n)))
    return out


def etalonnage(L):
    if not L:
        return {'matchs': 0}
    par_n = {}
    for lg, n, p, c in L:
        D = distribution(p, n)
        t = par_n.setdefault(n, {'matchs': 0, 'annonce': {k: 0.0 for k in categories(n)}, 'reel': {k: 0 for k in categories(n)}})
        t['matchs'] += 1
        for k, v in D.items():
            t['annonce'][k] += v
        t['reel'][c] += 1
    out, ecart_max = {}, 0.0
    for n, t in par_n.items():
        d = {}
        for k in categories(n):
            a, r = 100 * t['annonce'][k] / t['matchs'], 100 * t['reel'][k] / t['matchs']
            nom = f"{'favori' if k[0] == 'F' else 'outsider'} {n}-{k[1]}"
            d[nom] = {'annonce_pct': round(a, 1), 'reel_pct': round(r, 1)}
            ecart_max = max(ecart_max, abs(a - r))
        dec = [k for k in d if k.endswith(f'-{n - 1}')]
        out[f'{n}_manches_gagnantes'] = {'matchs': t['matchs'], 'scores': d,
                                         'manche_decisive_annoncee_pct': round(sum(d[k]['annonce_pct'] for k in dec), 1),
                                         'manche_decisive_reelle_pct': round(sum(d[k]['reel_pct'] for k in dec), 1)}
    n_tot = len(L)
    return {'matchs': n_tot, 'par_format': out, 'ecart_max_pts': round(ecart_max, 1),
            'etalonne': bool(n_tot >= MIN_JUGES and ecart_max <= ECART_MAX_PTS)}


def tranche(p):
    return min(int((p - 0.5) / TRANCHE), int(0.5 / TRANCHE) - 1)


def apprendre_table(L):
    """{(ligue, n, tranche): {catégorie: comptes}} + totaux."""
    T = {}
    for lg, n, p, c in L:
        k = (lg, n, tranche(p))
        t = T.setdefault(k, {'n': 0, 'c': {}})
        t['n'] += 1
        t['c'][c] = t['c'].get(c, 0) + 1
    return T


def proba_recalee(T, lg, n, p, c):
    D = distribution(p, n)
    t = T.get((lg, n, tranche(p)))
    if not t:
        return D[c]
    return (t['c'].get(c, 0) + POIDS_A_PRIORI * D[c]) / (t['n'] + POIDS_A_PRIORI)


def comparer(L, T):
    d = []
    for lg, n, p, c in L:
        base = distribution(p, n)[c]
        rec = proba_recalee(T, lg, n, p, c)
        d.append(-math.log(max(base, 1e-12)) + math.log(max(rec, 1e-12)))
    if not d:
        return {'matchs': 0}
    g = sum(d) / len(d)
    et = math.sqrt(sum((x - g) ** 2 for x in d) / max(len(d) - 1, 1)) / math.sqrt(len(d))
    return {'matchs': len(d), 'gain': round(g, 5), 'erreur_type': round(et, 5),
            'log_loss_score_ancre': round(sum(-math.log(max(distribution(p, n)[c], 1e-12)) for _, n, p, c in L) / len(L), 4)}


def etudier(M, reglage_e2, pentes, journal=print):
    A, B = EE.periodes(M)
    if len(A) < MIN_JUGES or len(B) < MIN_JUGES:
        journal(f'pas assez de matchs (apprentissage {len(A)}, jugement {len(B)})')
        return {'verdict': 'donnees_insuffisantes'}
    a, c, w, s = reglage_e2
    P = ET.rejouer(M, a=a, c=c, w=w, s=s)
    LA, LB = lignes(M, P, pentes, A), lignes(M, P, pentes, B)
    TA, TB = apprendre_table(LA), apprendre_table(LB)
    ligues = sorted({x[0] for x in LB})
    res = {}
    for lg in ligues:
        la, lb = [x for x in LA if x[0] == lg], [x for x in LB if x[0] == lg]
        cj = comparer(lb, TA)
        inv = comparer(la, TB)
        ok = bool(cj.get('matchs', 0) >= MIN_JUGES and cj.get('gain', 0) >= MARGE
                  and cj.get('gain', 0) >= ERREURS_TYPES * cj.get('erreur_type', 1) and inv.get('gain', 0) > 0)
        res[lg] = {'produit': lg in LIGUES_PRODUIT, 'Q1_etalonnage': etalonnage(lb),
                   'Q2_recalage': dict(cj, sens_inverse=inv.get('gain'), retenu=ok)}
    rep = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'paquet': PAQUET,
           'base_E2': list(reglage_e2), 'pentes_par_ligue': pentes, 'apprentissage': len(A), 'jugement': len(B),
           'par_ligue': res, 'ligues_produit': list(LIGUES_PRODUIT)}
    journal(f"étape 3 : {len(M)} matchs, apprentissage {len(A)}, jugement {len(B)}, pentes {pentes}")
    for lg in sorted(res, key=lambda k: (not res[k]['produit'], k)):
        v = res[lg]
        e, r = v['Q1_etalonnage'], v['Q2_recalage']
        journal(f"  {lg}{' (produit)' if v['produit'] else ''} : {e['matchs']} matchs, écart max {e.get('ecart_max_pts')} pts"
                f"{' → étalonné' if e.get('etalonne') else ''} ; recalage gain {r.get('gain')} ± {r.get('erreur_type')}, "
                f"sens inverse {r.get('sens_inverse')}{' → retenu' if r['retenu'] else ''}")
        for f, x in e.get('par_format', {}).items():
            sc = ', '.join(f"{k} {y['annonce_pct']}/{y['reel_pct']}" for k, y in x['scores'].items())
            journal(f"      {f} ({x['matchs']}) : {sc} ; manche décisive {x['manche_decisive_annoncee_pct']}/{x['manche_decisive_reelle_pct']}")
    return rep


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    with open(RAPPORT_487, encoding='utf-8') as f:
        e2 = json.load(f)['reglages_appris']['E2']['reglage']
    M = ET.matchs(racine)
    rep = etudier(M, e2, pentes_retenues())
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
