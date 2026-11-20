#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_fourchette.py — la fourchette du % est-elle trop large ? (11/11/2026, paquet 220, demande de Lucas)

QUESTION. La fourchette (fourchette.py) ajoute au % l'incertitude sur le NIVEAU des joueurs. Sa part Elo (de loin la
plus grande) suit une règle de Glicko posée à la main : RD = max(45, 350 / √(1 + matchs)) par joueur. Le plancher de
45 points garde une fourchette large même pour des joueurs vus des centaines de fois. Est-ce justifié par les données ?

MESURE (aucune cote). Pour chaque match de l'archive, on compare l'écart Elo des deux joueurs AU MOMENT du match (z_t,
en logit) à l'écart que l'Elo leur donne 90 JOURS PLUS TARD (z_h), une fois vus d'autres matchs, l'effet du match
lui-même retiré. d = z_h − z_t contient l'erreur d'estimation du niveau ET le vrai changement de niveau en 90 jours :
sa variance est donc une BORNE HAUTE de l'incertitude sur le niveau. Une fourchette calée dessus ne peut pas être trop
étroite.

RÈGLE (fixée avant de regarder les résultats) :
  — modèle : Var(d) = α + β · v, avec v = 1/(n_a + 5) + 1/(n_b + 5) (n = matchs déjà joués), α, β ≥ 0, ajusté par
    moindres carrés sur 20 classes de v, sur 2018–2022 seulement ;
  — jugé sur 2023 → juin 2026, circuit par circuit (ATP, WTA, Challenger) : la nouvelle part Elo est ADOPTÉE pour un
    circuit si l'intervalle z_t ± 1,2816 · √(α + β v) contient z_h dans au moins 78 % des matchs (cible 80 %, tolérance
    2 points) ET s'il est plus étroit en moyenne que l'intervalle actuel ; sinon le circuit garde la règle actuelle ;
  — au moins 1 000 matchs jugés par circuit.
Sortie : simulateur/rapport_fourchette.json (public : aucune cote, aucun nom de joueur).
"""
import bisect
import datetime as dt
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import donnees as D  # noqa: E402
import elo as E  # noqa: E402
import fourchette as FO  # noqa: E402

HORIZON = 90
APPRENTISSAGE_FIN = dt.date(2022, 12, 31)
JUGEMENT = (dt.date(2023, 1, 1), dt.date(2026, 6, 30))
COUVERTURE_MIN, MATCHS_MIN, Z80 = 78.0, 1000, 1.2816
CLASSES = 20
CIRCUITS = ('ATP', 'WTA', 'CH')


def rejouer(matchs):
    el = E.Elo(poids_surface=0.3, welo='norme', incertitude=0.0)
    ordre = sorted(matchs, key=lambda m: (m['date'], m.get('ordre', 0)))
    snap_dates, snaps = [], []
    prochain = dt.date(ordre[0]['date'].year, ordre[0]['date'].month, 1)
    lignes = []
    rnd = random.Random(20261111)
    for m in ordre:
        while m['date'] >= prochain:
            snap_dates.append(prochain)
            snaps.append((dict(el.g), dict(el.s)))
            prochain = dt.date(prochain.year + (prochain.month == 12), prochain.month % 12 + 1, 1)
        w, l, s = m['gagnant'], m['perdant'], m.get('surface')
        a, b = (w, l) if rnd.random() < 0.5 else (l, w)
        za = (el.note(a, s) - el.note(b, s)) / FO.ELO_LOGIT
        avant = {j: (el._g(j), el._s(j, s)) for j in (a, b)}
        part = E.part_jeux(m['sets']) if m.get('sets') else None
        el.maj(w, l, s, m.get('niveau') == 'G', part)
        delta = {j: (el._g(j) - avant[j][0], el._s(j, s) - avant[j][1]) for j in (a, b)}
        lignes.append({'date': m['date'], 'circuit': m['circuit'], 'a': a, 'b': b, 's': s, 'z': za,
                       'na': el.n.get(a, 1) - 1, 'nb': el.n.get(b, 1) - 1, 'delta': delta})
    snap_dates.append(prochain)
    snaps.append((dict(el.g), dict(el.s)))
    return lignes, snap_dates, snaps, el


def note_snap(snap, j, s, delta, ps=0.3):
    g, S = snap
    if j not in g:
        return None
    gg = g[j] - delta[0]
    if s in E.SURFACES and (j, s) in S:
        return (1 - ps) * gg + ps * (S[(j, s)] - delta[1])
    return gg


def ecarts(lignes, snap_dates, snaps, fin_archive):
    out = []
    for x in lignes:
        cible = x['date'] + dt.timedelta(days=HORIZON)
        if cible > fin_archive:
            continue
        i = bisect.bisect_left(snap_dates, cible)
        if i >= len(snaps):
            continue
        ha = note_snap(snaps[i], x['a'], x['s'], x['delta'][x['a']])
        hb = note_snap(snaps[i], x['b'], x['s'], x['delta'][x['b']])
        if ha is None or hb is None:
            continue
        v = 1 / (x['na'] + 5) + 1 / (x['nb'] + 5)
        out.append({'date': x['date'], 'circuit': x['circuit'], 'v': v, 'd': (ha - hb) / FO.ELO_LOGIT - x['z'],
                    'na': x['na'], 'nb': x['nb']})
    return out


def ajuster(E_):
    E_ = sorted(E_, key=lambda e: e['v'])
    k = max(1, len(E_) // CLASSES)
    pts = []
    for i in range(0, len(E_), k):
        c = E_[i:i + k]
        if len(c) < 50:
            continue
        mv = sum(e['v'] for e in c) / len(c)
        md = sum(e['d'] for e in c) / len(c)
        var = sum((e['d'] - md) ** 2 for e in c) / (len(c) - 1)
        pts.append((mv, var, len(c)))
    sw = sum(n for _, _, n in pts)
    mx = sum(v * n for v, _, n in pts) / sw
    my = sum(y * n for _, y, n in pts) / sw
    sxx = sum(n * (v - mx) ** 2 for v, _, n in pts)
    sxy = sum(n * (v - mx) * (y - my) for v, y, n in pts)
    beta = max(0.0, sxy / sxx) if sxx else 0.0
    alpha = max(0.0, my - beta * mx)
    return alpha, beta, [{'v': round(v, 5), 'var': round(y, 5), 'n': n} for v, y, n in pts]


def var_actuelle(na, nb):
    return (FO.rd(na) ** 2 + FO.rd(nb) ** 2) / FO.ELO_LOGIT ** 2


def juger(E_, alpha, beta):
    res = {}
    for c in CIRCUITS:
        X = [e for e in E_ if e['circuit'] == c and JUGEMENT[0] <= e['date'] <= JUGEMENT[1]]
        if not X:
            res[c] = {'n': 0}
            continue
        nouv = [Z80 * math.sqrt(alpha + beta * e['v']) for e in X]
        act = [Z80 * math.sqrt(var_actuelle(e['na'], e['nb'])) for e in X]
        cn = 100 * sum(abs(e['d']) <= h for e, h in zip(X, nouv)) / len(X)
        ca = 100 * sum(abs(e['d']) <= h for e, h in zip(X, act)) / len(X)
        ln, la = sum(nouv) / len(X), sum(act) / len(X)
        # largeur moyenne en points de % autour de p = 60 %, part Elo seule, poids Elo de l'algo
        def pts(h):
            z0 = math.log(0.6 / 0.4)
            w = FO.POIDS['elo']
            return 100 * (1 / (1 + math.exp(-(z0 + w * h))) - 1 / (1 + math.exp(-(z0 - w * h))))
        adopte = len(X) >= MATCHS_MIN and cn >= COUVERTURE_MIN and ln < la
        res[c] = {'n': len(X), 'couverture_nouvelle_pct': round(cn, 1), 'couverture_actuelle_pct': round(ca, 1),
                  'demi_largeur_logit_nouvelle': round(ln, 4), 'demi_largeur_logit_actuelle': round(la, 4),
                  'largeur_pts_a_60pct_nouvelle': round(sum(pts(h) for h in nouv) / len(X), 1),
                  'largeur_pts_a_60pct_actuelle': round(sum(pts(h) for h in act) / len(X), 1),
                  'adopte': adopte}
    return res


def main(archive='/tmp/sackmann', racine='.'):
    M = D.charger(archive, 2018)
    fin = max(m['date'] for m in M)
    lignes, sd, sn, _ = rejouer(M)
    E_ = ecarts(lignes, sd, sn, fin)
    app = [e for e in E_ if e['date'] <= APPRENTISSAGE_FIN]
    alpha, beta, classes = ajuster(app)
    res = juger(E_, alpha, beta)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': __doc__.split('RÈGLE (fixée avant de regarder les résultats) :')[1].split('Sortie :')[0].strip(),
           'horizon_jours': HORIZON, 'apprentissage': '2018–2022', 'jugement': '2023 → juin 2026',
           'alpha': round(alpha, 5), 'beta': round(beta, 4), 'matchs_apprentissage': len(app),
           'classes_apprentissage': classes, 'circuits': res}
    with open(os.path.join(racine, 'simulateur', 'rapport_fourchette.json'), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return doc


if __name__ == '__main__':
    print(json.dumps(main(*sys.argv[1:]), ensure_ascii=False, indent=1))
