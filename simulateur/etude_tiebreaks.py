#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_tiebreaks.py — notre prévision « au moins un tie-break » est-elle trop basse ? (05/11/2026, demande de Lucas :
en direct, ATP 44 % prévus pour 52 % réels sur 6 semaines, pas encore significatif).

Rejoue sur l'archive Sackmann, matchs au meilleur des 3 sets 2023 → juin 2026 (ATP, WTA, Challenger, sans abandon),
EXACTEMENT le calcul de la fiche (pronostics_du_jour.pronostic) : service / retour ajustés aux adversaires
(ajustement.ajuster, refait chaque trimestre, point-in-time), niveau ancré sur la probabilité Elo du jour (approximation
de la combinaison, qui pèse 78 % d'Elo), forme du jour σ du circuit (ATP 0,15, WTA 0,15, Challenger 0,22),
modele.match_forme → P(au moins un tie-break).

RÈGLE FIXÉE LE 05/11/2026, AVANT DE REGARDER LE RÉSULTAT, circuit par circuit :
  un décalage δ (logit) de P(tie-break) est appris sur 2023–2024 ; il est retenu pour un FANTÔME de la ligne
  « tie-break » (jugé ensuite en direct, deux semaines) si sur 2025 → juin 2026 :
    a) la log loss de l'événement « au moins un tie-break » baisse d'au moins 0,001 sur au moins 1 000 matchs, ET
    b) l'écart réel − prévu a le même signe sur les deux périodes.
Usage : python simulateur/etude_tiebreaks.py /tmp/sackmann .
"""
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import ajustement as AJ  # noqa: E402
import match_simule as MS  # noqa: E402
import modele as M  # noqa: E402

DEBUT, COUPURE, FIN = dt.date(2023, 1, 1), dt.date(2025, 1, 1), dt.date(2026, 7, 1)
SIGMA = {'ATP': 0.15, 'WTA': 0.15, 'CH': 0.22}
MIN_JUGES, MARGE = 1000, 0.001
SORTIE = os.path.join(ICI, 'rapport_tiebreaks.json')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-z))


def trimestres():
    d, out = DEBUT, []
    while d < FIN:
        out.append(d)
        d = dt.date(d.year + (d.month + 3 > 12), (d.month + 2) % 12 + 1, 1)
    return out


_SI = {}


def _issues(pA, pB, srv):
    k = (round(pA, 4), round(pB, 4), srv)
    if k not in _SI:
        if len(_SI) > 200000:
            _SI.clear()
        _SI[k] = M.set_issues(k[0], k[1], srv, 7)
    return _SI[k]


def p_tiebreak_match(pA, pB, sigma):
    """P(au moins un tie-break), au meilleur des 3, forme du jour (13 nœuds) — même chaîne que modele.match,
    calculée au niveau des sets (plus rapide)."""
    la, lb = _lg(pA), _lg(pB)
    tot = 0.0
    for z, w in zip(M._Z, M._W):
        a, b = _sg(la + sigma * z), _sg(lb - sigma * z)
        sans = 0.0
        for premier in (True, False):
            etats = {(0, 0, premier): 0.5}
            while etats:
                nouv = {}
                for (sa, sb, srv), pr in etats.items():
                    for x, y, q in _issues(a, b, srv):
                        if (x, y) in ((7, 6), (6, 7)):
                            continue
                        na, nb = sa + (x > y), sb + (y > x)
                        if na == 2 or nb == 2:
                            sans += pr * q
                        else:
                            k_ = (na, nb, srv if (x + y) % 2 == 0 else not srv)
                            nouv[k_] = nouv.get(k_, 0.0) + pr * q
                etats = nouv
        tot += w * (1 - sans)
    return tot


def a_un_tb(sets):
    return any((a, b) in ((7, 6), (6, 7)) for a, b in sets)


def lignes(archive):
    import donnees as DN
    import elo as E
    with open(os.path.join(ICI, 'choix_simulation.json'), encoding='utf-8') as f:
        ch = json.load(f)
    n0, n0c = float(ch.get('n0') or AJ.N0), ch.get('n0_par_composante') or None
    Mt = DN.charger(archive, 2018)
    Mt.sort(key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    T = trimestres()
    k = E.cle
    el, jour, attente, rows, A, ti = E.Elo(), None, [], [], None, -1
    for m in Mt:
        d = m['date']
        if d != jour:
            for g, p, s, gc in attente:
                el.maj(g, p, s, gc, None)
            attente, jour = [], d
        while ti + 1 < len(T) and d >= T[ti + 1]:
            ti += 1
            A = AJ.ajuster(Mt, T[ti], k, n0=n0, n0_par_composante=n0c)
            print(f"ajustement au {T[ti]}", flush=True)
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m['surface']
        if c in ('CH', 'ITF'):
            el.presenter(g, 1200.0)
            el.presenter(p, 1200.0)
        if (A is not None and DEBUT <= d < FIN and c in SIGMA and m.get('bo') == 3 and m.get('complet')
                and not m.get('abandon') and m.get('sets') and el.matchs(g) >= 10 and el.matchs(p) >= 10):
            pe = el.proba(g, p, s)
            pa0 = AJ._p_service(A.taux(g, p, c, s))
            pb0 = AJ._p_service(A.taux(p, g, c, s))
            a, b = MS.ancrer_rapide(pa0, pb0, min(max(pe, 0.01), 0.99), 2, SIGMA[c], iterations=20)
            ptb = p_tiebreak_match(a, b, SIGMA[c])
            rows.append({'d': d, 'c': c, 'p': ptb, 'y': int(a_un_tb(m['sets']))})
        attente.append((g, p, s, m.get('niveau') == 'G'))
    return rows


def ll(R, delta=0.0):
    return sum(-math.log(min(max(_sg(_lg(r['p']) + delta) if r['y'] else 1 - _sg(_lg(r['p']) + delta), 1e-9), 1))
               for r in R) / max(1, len(R))


def apprendre(R):
    lo, hi = -2.0, 2.0
    for _ in range(50):                     # dérivée de la log loss en δ : moyenne de (q − y)
        mid = (lo + hi) / 2
        g = sum(_sg(_lg(r['p']) + mid) - r['y'] for r in R)
        lo, hi = (mid, hi) if g < 0 else (lo, mid)
    return (lo + hi) / 2


def juger(rows):
    out = {}
    for c in SIGMA:
        R = [r for r in rows if r['c'] == c]
        av, ju = [r for r in R if r['d'] < COUPURE], [r for r in R if r['d'] >= COUPURE]
        bloc = {}
        for nom, X in (('2023–2024', av), ('2025 → juin 2026', ju)):
            n = len(X)
            pm, rm = sum(r['p'] for r in X) / max(1, n), sum(r['y'] for r in X) / max(1, n)
            se = math.sqrt(max(pm * (1 - pm), 1e-6) / max(1, n))
            bloc[nom] = {'matchs': n, 'prevu_pct': round(100 * pm, 1), 'reel_pct': round(100 * rm, 1),
                         'ecart_pts': round(100 * (rm - pm), 1), 'z': round((rm - pm) / se, 1)}
        delta = apprendre(av)
        gain = ll(ju) - ll(ju, delta)
        e1, e2 = bloc['2023–2024']['ecart_pts'], bloc['2025 → juin 2026']['ecart_pts']
        bloc.update({'delta_appris': round(delta, 4), 'gain_log_loss_juge': round(gain, 5),
                     'retenu_pour_fantome': bool(len(ju) >= MIN_JUGES and gain >= MARGE and e1 * e2 > 0)})
        tr = collections.defaultdict(lambda: [0, 0.0, 0])          # étalonnage par tranche, période jugée
        for r in ju:
            t = min(int(r['p'] * 10), 9)
            tr[t][0] += 1
            tr[t][1] += r['p']
            tr[t][2] += r['y']
        bloc['etalonnage_juge'] = [{'tranche': f"{10 * t}–{10 * t + 10} %", 'matchs': n, 'prevu': round(100 * sp / n, 1),
                                    'reel': round(100 * y / n, 1)} for t, (n, sp, y) in sorted(tr.items()) if n >= 30]
        out[c] = bloc
    return out


def main(argv):
    archive = argv[1]
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("par circuit : δ appris 2023–2024 ; fantôme si −0,001 de log loss sur ≥ 1 000 matchs 2025 → et "
                     "écart de même signe sur les deux périodes"),
           'circuits': juger(lignes(archive))}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
