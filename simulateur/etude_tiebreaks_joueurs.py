#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_tiebreaks_joueurs.py — certains joueurs ont-ils « l'habitude » de gagner (ou de perdre) les tie-breaks, et
cela prédit-il le prochain ? (05/11/2026, question de Lucas, dans la suite de etude_set_decisif.py).

Archive Sackmann 2015 → juin 2026, ATP, WTA, Challenger, matchs complets sans abandon : CHAQUE tie-break joué
(set 7-6 ou 6-7) est une observation. Les deux joueurs sont ordonnés par leur clé.

ATTENDU d'un tie-break : un tie-break est plus serré qu'un set ; P(gagner le tie-break) = σ(α · logit q), q = P(gagner
un set) tirée de la probabilité Elo d'avant match ; α appris sur 2018–2022, par circuit.

DEUX MESURES du joueur, sur ses tie-breaks des 3 années d'avant (jamais le jour même) :
  — « brut » (ce qu'affichent les sites) : (gagnés − perdus) / 2 / (n + 10) ;
  — « ajusté » : Σ (résultat − attendu) / (n + 10).
Variable : mesure de A − mesure de B.

RÈGLE FIXÉE LE 05/11/2026, AVANT DE REGARDER LE RÉSULTAT (la même que pour le set décisif), circuit par circuit et
par mesure : β appris sur 2018–2022 ; RETENUE si sur 2023 → juin 2026 la log loss des tie-breaks baisse d'au moins
0,001 sur au moins 1 000 tie-breaks ET β appris sur 2023 → juin 2026 a le même signe.
Aussi : fidélité pair/impair (joueurs ≥ 15 tie-breaks dans chaque moitié) ; les « gros écarts » (deux joueurs à
≥ 10 tie-breaks, mesures opposées) comme sur les visuels des autres sites.
Usage : python simulateur/etude_tiebreaks_joueurs.py /tmp/sackmann
"""
import bisect
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_set_decisif as SD  # noqa: E402

DEBUT, COUPURE, FIN = SD.DEBUT, SD.COUPURE, SD.FIN
FENETRE_J, K_RAPPEL = 3 * 365, 10.0
MIN_JUGES, MARGE = 1000, 0.001
CIRCUITS, MESURES = SD.CIRCUITS, SD.MESURES
SORTIE = os.path.join(ICI, 'rapport_tiebreaks_joueurs.json')
_lg, _sg = SD._lg, SD._sg


def tiebreaks(sets):
    """[1 si le vainqueur du match a gagné ce tie-break, 0 sinon] pour chaque set 7-6 / 6-7."""
    return [1 if a > b else 0 for a, b in sets if (a, b) in ((7, 6), (6, 7))]


def evenements(archive):
    """Tie-breaks chronologiques : (date, circuit, joueur A, joueur B, q set de A, A gagne, jugeable)."""
    import donnees as DN
    import elo as E
    Mt = DN.charger(archive, 2015)
    Mt.sort(key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    k = E.cle
    el, jour, attente, ev = E.Elo(), None, [], []
    for m in Mt:
        d = m['date']
        if d != jour:
            for g, p, s, gc in attente:
                el.maj(g, p, s, gc, None)
            attente, jour = [], d
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m['surface']
        if c in ('CH', 'ITF'):
            el.presenter(g, 1200.0)
            el.presenter(p, 1200.0)
        if c in CIRCUITS and m.get('complet') and not m.get('abandon') and m.get('sets'):
            T = tiebreaks(m['sets'])
            if T:
                bo = 5 if m.get('bo') == 5 else 3
                qg = SD.q_set(min(max(el.proba(g, p, s), 0.01), 0.99), bo)
                ok = el.matchs(g) >= 10 and el.matchs(p) >= 10
                for y in T:
                    a, b, qa, ya = (g, p, qg, y) if g < p else (p, g, 1 - qg, 1 - y)
                    ev.append((d, c, a, b, qa, ya, ok))
        attente.append((g, p, s, m.get('niveau') == 'G'))
    return ev


def apprendre_alpha(R):
    """α de P(tie-break) = σ(α · logit q), par Newton."""
    a = 1.0
    for _ in range(30):
        g = h = 0.0
        for q, y in R:
            x = _lg(q)
            pr = _sg(a * x)
            g += (y - pr) * x
            h += pr * (1 - pr) * x * x
        if h <= 0:
            break
        pas = g / h
        a += pas
        if abs(pas) < 1e-8:
            break
    return a


def lignes(ev):
    alpha = {}
    for c in CIRCUITS:
        alpha[c] = apprendre_alpha([(q, y) for d, cc, a, b, q, y, ok in ev if cc == c and DEBUT <= d < COUPURE])
    H = collections.defaultdict(list)            # joueur → [(date, gagné, attendu)]
    rows = []

    def mesures(j, d):
        L = H.get(j, [])
        i0 = bisect.bisect_left(L, (d - dt.timedelta(days=FENETRE_J),))
        i1 = bisect.bisect_left(L, (d,))
        X = L[i0:i1]
        n, v = len(X), sum(e[1] for e in X)
        return n, (v - (n - v)) / 2 / (n + K_RAPPEL), sum(e[1] - e[2] for e in X) / (n + K_RAPPEL)

    for d, c, a, b, q, y, ok in ev:
        pa = _sg(alpha[c] * _lg(q))
        if ok and DEBUT <= d < FIN:
            na, ba, ja = mesures(a, d)
            nb, bb, jb = mesures(b, d)
            rows.append({'d': d, 'c': c, 'q': pa, 'y': y, 'na': na, 'nb': nb, 'brut': ba - bb, 'ajuste': ja - jb})
        H[a].append((d, y, pa))
        H[b].append((d, 1 - y, 1 - pa))
    return rows, H, alpha


def fidelite(H):
    xs, ys = [], []
    for L in H.values():
        L = [e for e in L if DEBUT <= e[0] < FIN]
        u, v = L[0::2], L[1::2]
        if len(u) >= 15 and len(v) >= 15:
            xs.append(sum(y - q for _, y, q in u) / len(u))
            ys.append(sum(y - q for _, y, q in v) / len(v))
    n = len(xs)
    if n < 20:
        return {'joueurs': n}
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx, vy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
    return {'joueurs': n, 'correlation': round(cov / math.sqrt(vx * vy), 3)}


def juger(rows, alpha):
    out = {}
    for c in CIRCUITS:
        R = [r for r in rows if r['c'] == c]
        av, ju = [r for r in R if r['d'] < COUPURE], [r for r in R if r['d'] >= COUPURE]
        bloc = {'tiebreaks': {'2018–2022': len(av), '2023 → juin 2026': len(ju)}, 'alpha': round(alpha[c], 3)}
        for x in MESURES:
            b1, b2 = SD.apprendre(av, x), SD.apprendre(ju, x)
            gain = SD.ll(ju) - SD.ll(ju, x, b1)
            forts = [r for r in ju if r['na'] >= 10 and r['nb'] >= 10 and abs(r[x]) >= 0.10]
            bloc[x] = {'beta_2018_2022': round(b1, 3), 'beta_2023_2026': round(b2, 3),
                       'gain_log_loss_juge': round(gain, 5),
                       'retenue': bool(len(ju) >= MIN_JUGES and gain >= MARGE and b1 * b2 > 0),
                       'gros_ecarts_juges': {
                           'tiebreaks': len(forts),
                           'meilleur_bilan_gagne_pct': round(100 * sum((r['y'] if r[x] > 0 else 1 - r['y']) for r in forts)
                                                             / len(forts), 1) if forts else None,
                           'attendu_pct': round(100 * sum((r['q'] if r[x] > 0 else 1 - r['q']) for r in forts)
                                                / len(forts), 1) if forts else None}}
        out[c] = bloc
    return out


def main(argv):
    rows, H, alpha = lignes(evenements(argv[1]))
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("par circuit et par mesure : β appris 2018–2022 ; retenue si −0,001 de log loss sur ≥ 1 000 "
                     "tie-breaks 2023 → juin 2026 et β de même signe sur les deux périodes"),
           'fidelite_pair_impair': fidelite(H),
           'circuits': juger(rows, alpha)}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
