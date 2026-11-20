#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_set_decisif.py — le « bilan au set décisif » d'un joueur prédit-il le prochain ? (05/11/2026, demande de Lucas
après un visuel MatchUp : « 88 % 7V-1D +34 % contre 20 % 1V-4D −33 % »).

Archive Sackmann 2015 → juin 2026, ATP, WTA, Challenger, matchs complets sans abandon, arrivés au set décisif
(3e set au meilleur des 3, 5e au meilleur des 5). Le gagnant du set décisif est le gagnant du match.

ATTENDU d'un set décisif : P(gagner un set) tirée de la probabilité Elo du match d'avant (point-in-time) — au meilleur
des 3, p = q²(3 − 2q) ; au meilleur des 5, la formule à 3 sets gagnants. Les deux joueurs sont ordonnés par leur clé
(ni favori ni vainqueur en premier).

DEUX MESURES du joueur, calculées avec ses sets décisifs des 3 années d'avant (jamais le match jugé) :
  — « brut » (ce qu'affichent les sites) : (victoires − défaites) / 2 / (n + 10) ;
  — « ajusté » (notre manière) : Σ (résultat − attendu) / (n + 10) — ce qu'il a fait au-delà de son niveau.
Variable du match : mesure de A − mesure de B.

RÈGLE FIXÉE LE 05/11/2026, AVANT DE REGARDER LE RÉSULTAT, circuit par circuit et pour chaque mesure :
  un coefficient β (logit, en plus de l'attendu) est appris sur 2018–2022 ; la mesure est RETENUE si sur
  2023 → juin 2026 :
    a) la log loss des sets décisifs baisse d'au moins 0,001 sur au moins 1 000 sets décisifs, ET
    b) β appris sur 2023 → juin 2026 a le même signe que sur 2018–2022.
  Retenue → candidate pour la fiche (bilan affiché avec l'attendu) et pour un fantôme du simulateur.
  Non retenue → le bilan au set décisif n'est qu'une description, sans valeur de prévision.
Aussi, pour information : FIDÉLITÉ (corrélation, entre joueurs ayant au moins 10 sets décisifs dans chaque moitié,
du « au-delà de l'attendu » des sets décisifs pairs et impairs, 2018 → 2026) ; étalonnage de l'attendu lui-même.
Usage : python simulateur/etude_set_decisif.py /tmp/sackmann
"""
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

DEBUT, COUPURE, FIN = dt.date(2018, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
FENETRE_J, K_RAPPEL = 3 * 365, 10.0
MIN_JUGES, MARGE = 1000, 0.001
CIRCUITS = ('ATP', 'WTA', 'CH')
MESURES = ('brut', 'ajuste')
SORTIE = os.path.join(ICI, 'rapport_set_decisif.json')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-z))


def p_match(q, bo):
    """P(gagner le match) quand chaque set est gagné avec q, indépendamment."""
    n = 3 if bo == 5 else 2
    return sum(math.comb(n - 1 + k, k) * q ** n * (1 - q) ** k for k in range(n))


def q_set(p, bo):
    """P(gagner un set) qui donne P(match) = p."""
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if p_match(mid, bo) < p else (lo, mid)
    return (lo + hi) / 2


def est_decisif(m):
    s = m.get('sets') or []
    return len(s) == (5 if m.get('bo') == 5 else 3)


class Bilans:
    """Sets décisifs passés de chaque joueur : (date, gagné 0/1, attendu)."""

    def __init__(self):
        self.h = collections.defaultdict(list)

    def ajouter(self, j, d, y, q):
        self.h[j].append((d, y, q))

    def mesures(self, j, d):
        L = [(y, q) for dd, y, q in self.h.get(j, ()) if 0 < (d - dd).days <= FENETRE_J]
        n = len(L)
        v = sum(y for y, _ in L)
        return {'n': n, 'v': v, 'brut': (v - (n - v)) / 2 / (n + K_RAPPEL),
                'ajuste': sum(y - q for y, q in L) / (n + K_RAPPEL)}


def lignes(archive):
    import donnees as DN
    import elo as E
    Mt = DN.charger(archive, 2015)
    Mt.sort(key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    k = E.cle
    el, B = E.Elo(), Bilans()
    jour, attente, rows = None, [], []
    for m in Mt:
        d = m['date']
        if d != jour:
            for g, p, s, gc, dec in attente:
                el.maj(g, p, s, gc, None)
                if dec:
                    B.ajouter(g, dec[0], 1, dec[1])
                    B.ajouter(p, dec[0], 0, 1 - dec[1])
            attente, jour = [], d
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m['surface']
        if c in ('CH', 'ITF'):
            el.presenter(g, 1200.0)
            el.presenter(p, 1200.0)
        dec = None
        if c in CIRCUITS and m.get('complet') and not m.get('abandon') and m.get('sets') and est_decisif(m):
            bo = 5 if m.get('bo') == 5 else 3
            qg = q_set(min(max(el.proba(g, p, s), 0.01), 0.99), bo)
            dec = (d, qg)
            if DEBUT <= d < FIN and el.matchs(g) >= 10 and el.matchs(p) >= 10:
                a, b, qa, y = (g, p, qg, 1) if g < p else (p, g, 1 - qg, 0)
                ma, mb = B.mesures(a, d), B.mesures(b, d)
                rows.append({'d': d, 'c': c, 'q': qa, 'y': y, 'na': ma['n'], 'nb': mb['n'],
                             'brut': ma['brut'] - mb['brut'], 'ajuste': ma['ajuste'] - mb['ajuste']})
        attente.append((g, p, s, m.get('niveau') == 'G', dec))
    return rows, B


def ll(R, x=None, b=0.0):
    t = 0.0
    for r in R:
        z = _lg(r['q']) + (b * r[x] if x else 0.0)
        pr = _sg(z)
        t -= math.log(max(pr if r['y'] else 1 - pr, 1e-9))
    return t / max(1, len(R))


def apprendre(R, x):
    """β qui minimise la log loss (Newton, attendu en décalage)."""
    b = 0.0
    for _ in range(30):
        g = h = 0.0
        for r in R:
            pr = _sg(_lg(r['q']) + b * r[x])
            g += (r['y'] - pr) * r[x]
            h += pr * (1 - pr) * r[x] ** 2
        if h <= 0:
            break
        pas = g / (h + 1e-9)
        b += pas
        if abs(pas) < 1e-8:
            break
    return b


def fidelite(B):
    """Corrélation pair/impair du « au-delà de l'attendu » (joueurs ≥ 10 sets décisifs dans chaque moitié)."""
    xs, ys = [], []
    for L in B.h.values():
        L = [e for e in L if DEBUT <= e[0] < FIN]
        a, b = L[0::2], L[1::2]
        if len(a) >= 10 and len(b) >= 10:
            xs.append(sum(y - q for _, y, q in a) / len(a))
            ys.append(sum(y - q for _, y, q in b) / len(b))
    n = len(xs)
    if n < 20:
        return {'joueurs': n}
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx, vy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
    return {'joueurs': n, 'correlation': round(cov / math.sqrt(vx * vy), 3)}


def juger(rows):
    out = {}
    for c in CIRCUITS:
        R = [r for r in rows if r['c'] == c]
        av, ju = [r for r in R if r['d'] < COUPURE], [r for r in R if r['d'] >= COUPURE]
        bloc = {'sets_decisifs': {'2018–2022': len(av), '2023 → juin 2026': len(ju)}}
        # l'attendu lui-même : le favori gagne-t-il le set décisif aussi souvent que prévu ?
        fav = [(max(r['q'], 1 - r['q']), r['y'] if r['q'] >= 0.5 else 1 - r['y']) for r in ju]
        if fav:
            bloc['favori_au_set_decisif_juge'] = {'prevu_pct': round(100 * sum(a for a, _ in fav) / len(fav), 1),
                                                   'reel_pct': round(100 * sum(b for _, b in fav) / len(fav), 1)}
        for x in MESURES:
            b1 = apprendre(av, x)
            b2 = apprendre(ju, x)
            gain = ll(ju) - ll(ju, x, b1)
            # « gros écart » façon visuel : un joueur à ≥ 8 sets décisifs, l'autre aussi, mesures opposées
            forts = [r for r in ju if r['na'] >= 8 and r['nb'] >= 8 and abs(r[x]) >= 0.15]
            bloc[x] = {'beta_2018_2022': round(b1, 3), 'beta_2023_2026': round(b2, 3),
                       'gain_log_loss_juge': round(gain, 5),
                       'retenue': bool(len(ju) >= MIN_JUGES and gain >= MARGE and b1 * b2 > 0),
                       'gros_ecarts_juges': {
                           'sets_decisifs': len(forts),
                           'meilleur_bilan_gagne_pct': round(100 * sum((r['y'] if r[x] > 0 else 1 - r['y']) for r in forts)
                                                             / len(forts), 1) if forts else None,
                           'attendu_pct': round(100 * sum((r['q'] if r[x] > 0 else 1 - r['q']) for r in forts)
                                                / len(forts), 1) if forts else None}}
        out[c] = bloc
    return out


def main(argv):
    archive = argv[1]
    rows, B = lignes(archive)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("par circuit et par mesure : β appris 2018–2022 ; retenue si −0,001 de log loss sur ≥ 1 000 sets "
                     "décisifs 2023 → juin 2026 et β de même signe sur les deux périodes"),
           'fidelite_pair_impair': fidelite(B),
           'circuits': juger(rows)}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
