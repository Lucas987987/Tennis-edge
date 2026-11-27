#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_outsider_confirme2.py — L'OUTSIDER CONFIRMÉ COMPARÉ AUX AUTRES OUTSIDERS DE MÊME % (27/11/2026, paquet 523,
Lucas : « oui fais le » après etude_outsider_confirme.py). LECTURE SEULE : aucune cote, rien ne change dans l'algo ;
un rapport de comptes et de moyennes, sans nom.

Constat de la première étude (paquet 522) : comparer l'outsider confirmé au % BRUT de l'Elo mélange deux choses — l'effet
cherché et le réglage général de chaque Elo (au tennis il sous-estime tous les outsiders, au ping International et au
badminton il les surestime). Ici, l'outsider confirmé est comparé aux AUTRES OUTSIDERS de même %.

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI (mêmes données, même % de l'algo, mêmes définitions, mêmes périodes et
mêmes groupes que la première étude — voir son en-tête) :
  Observations : tous les outsiders (% < 50) des périodes d'apprentissage et de jugement ; c = 1 si c'est un outsider
    confirmé (précédent match dans le même tournoi, au plus FENETRE jours avant, gagné en étant outsider), 0 sinon.
  Deux modèles appris sur l'apprentissage, groupe par groupe, par maximum de vraisemblance :
    M0 : logit q = a + b · logit p                     (le réglage général des outsiders du groupe)
    M1 : logit q = a + b · logit p + β · c             (en plus : être un outsider confirmé)
  RETENU pour un groupe si, sur au moins 1 000 outsiders confirmés jugés, M1 fait gagner au moins 0,001 de log loss par
    outsider confirmé sur le jugement (par rapport à M0) ET si β appris sur le jugement a le même signe que β appris
    sur l'apprentissage. Moins de 1 000 cas jugés : « trop peu de cas ». Groupe par groupe (tennis : ATP, WTA ; tennis de
    table : International, Pologne ; badminton : les 5 épreuves), puis tout le sport.
  Publiés sans décider : par tranche du % annoncé (moins de 20 %, 20–30, 30–40, 40–50), les victoires réelles des
    outsiders confirmés et des autres outsiders, sur chaque période.
Rapport : rapport_outsider_confirme2.json (racine du dépôt).
Usage : python scripts/etude_outsider_confirme2.py [racine] [tennis,tt,badminton]
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_outsider_confirme as E1  # noqa: E402

MARGE, MIN_CAS = 0.001, 1000
TRANCHES = ((0.0, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.5))
_lg, _sg = E1._lg, E1._sg


def observations(out):
    """[(groupe, période, p, gagné, c)] : tous les outsiders, c = 1 pour les outsiders confirmés."""
    conf = {}
    for g, per, p, w in out['confirme']:
        conf[(g, per, p, w)] = conf.get((g, per, p, w), 0) + 1
    L = []
    for g, per, p, w in out['outsiders']:
        k = (g, per, p, w)
        c = 1 if conf.get(k, 0) > 0 else 0
        if c:
            conf[k] -= 1
        L.append((g, per, p, w, c))
    return L


def ajuster(O, avec_c, iters=40):
    """(a, b, β) par maximum de vraisemblance (Newton, 2 ou 3 paramètres). O : [(x = logit p, y, c)]."""
    th = [0.0, 1.0, 0.0]
    k = 3 if avec_c else 2
    for _ in range(iters):
        g = [0.0] * k
        H = [[0.0] * k for _ in range(k)]
        for x, y, c in O:
            v = (1.0, x, float(c))[:k]
            q = _sg(th[0] + th[1] * x + th[2] * c)
            r = y - q
            w = q * (1 - q)
            for i in range(k):
                g[i] += r * v[i]
                for j in range(k):
                    H[i][j] -= w * v[i] * v[j]
        pas = resoudre(H, g)
        if pas is None:
            break
        for i in range(k):
            th[i] -= pas[i]
        if max(abs(x) for x in pas) < 1e-9:
            break
    return th


def resoudre(H, g):
    n = len(g)
    A = [row[:] + [g[i]] for i, row in enumerate(H)]
    for i in range(n):
        piv = max(range(i, n), key=lambda r: abs(A[r][i]))
        if abs(A[piv][i]) < 1e-12:
            return None
        A[i], A[piv] = A[piv], A[i]
        for r in range(n):
            if r != i:
                f = A[r][i] / A[i][i]
                for j in range(i, n + 1):
                    A[r][j] -= f * A[i][j]
    return [A[i][n] / A[i][i] for i in range(n)]


def ll(O, th):
    t = 0.0
    for x, y, c in O:
        q = min(max(_sg(th[0] + th[1] * x + th[2] * c), 1e-9), 1 - 1e-9)
        t -= math.log(q) if y else math.log(1 - q)
    return t / len(O) if O else float('nan')


def tranches(L):
    out = {}
    for lo, hi in TRANCHES:
        cle = f'{int(lo * 100)}–{int(hi * 100)} %'
        d = {}
        for nom, cc in (('confirmes', 1), ('autres', 0)):
            S = [(p, w) for p, w, c in L if c == cc and lo <= p < hi]
            d[nom] = ({'cas': len(S), 'gagnes_pct': round(100 * sum(w for _, w in S) / len(S), 1),
                       'annonce_pct': round(100 * sum(p for p, _ in S) / len(S), 1)} if S else {'cas': 0})
        out[cle] = d
    return out


def juger(L):
    """L : [(période, p, gagné, c)] d'un groupe."""
    A = [(_lg(p), int(w), c) for per, p, w, c in L if per == 'A']
    B = [(_lg(p), int(w), c) for per, p, w, c in L if per == 'B']
    nA, nB = sum(c for *_, c in A), sum(c for *_, c in B)
    d = {'outsiders': {'apprentissage': len(A), 'jugement': len(B)}, 'confirmes': {'apprentissage': nA, 'jugement': nB},
         'par_tranche': {'apprentissage': tranches([(p, w, c) for per, p, w, c in L if per == 'A']),
                         'jugement': tranches([(p, w, c) for per, p, w, c in L if per == 'B'])}}
    if nA < 30 or nB < 30:
        d['verdict'] = 'trop_peu_de_cas'
        return d
    m0, m1 = ajuster(A, False), ajuster(A, True)
    m1B = ajuster(B, True)
    Bc = [o for o in B if o[2]]
    gain = ll(Bc, m0) - ll(Bc, m1)
    d.update(reglage_general_appris=[round(m0[0], 4), round(m0[1], 4)], beta_appris=round(m1[2], 4),
             beta_jugement=round(m1B[2], 4), gain_juge_par_cas=round(gain, 5),
             confirmes_jugement={'gagnes_pct': round(100 * sum(y for _, y, _ in Bc) / len(Bc), 1),
                                 'attendu_M0_pct': round(100 * sum(_sg(m0[0] + m0[1] * x) for x, _, _ in Bc) / len(Bc), 1)})
    if nB < MIN_CAS:
        d['verdict'] = 'trop_peu_de_cas'
    else:
        d['verdict'] = 'retenu' if gain >= MARGE and (m1[2] > 0) == (m1B[2] > 0) else 'non_retenu'
    return d


def etudier(racine, sports=('tennis', 'tt', 'badminton'), journal=print):
    rep = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'regle_ecrite_le': '2026-11-27',
           'etude': 'outsider_confirme_contre_autres_outsiders', 'sports': {}}
    for sp in sports:
        try:
            M, groupes = E1.SPORTS[sp](racine)
        except (OSError, ValueError, ImportError) as e:
            journal(f'{sp} : données indisponibles ({type(e).__name__})')
            continue
        O = observations(E1.cas(M, E1.FENETRE_J[sp]))
        r = {}
        for g in list(groupes) + ['tout']:
            r[g] = juger([(per, p, w, c) for gg, per, p, w, c in O if g == 'tout' or gg == g])
        rep['sports'][sp] = r
        journal(f'{sp} : {len(M)} matchs')
        for g, d in r.items():
            cj = d.get('confirmes_jugement') or {}
            journal(f"  {g} : confirmés {d['confirmes']['apprentissage']} / {d['confirmes']['jugement']} (apprentissage / "
                    f"jugement) ; jugement {cj.get('gagnes_pct', '—')} % gagnés, attendu comme les autres outsiders "
                    f"{cj.get('attendu_M0_pct', '—')} % ; β {d.get('beta_appris')} / {d.get('beta_jugement')}, gain "
                    f"{d.get('gain_juge_par_cas')} → {d['verdict']}")
    return rep


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    sports = tuple(argv[2].split(',')) if len(argv) > 2 else ('tennis', 'tt', 'badminton')
    rep = etudier(racine, sports)
    with open(os.path.join(racine, 'rapport_outsider_confirme2.json'), 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
