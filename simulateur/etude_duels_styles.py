#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_duels_styles.py — un profil de joueur gagne-t-il plus que prévu contre un autre profil ? (31/10/2026, Lucas)

Styles service–retour INTERNES (styles_descriptifs.classifier), figés AVANT chaque match avec les seules feuilles
déjà disponibles. Pour chaque duel orienté « style A contre style B » (A ≠ B, styles déterminés) :
  écart = victoires réelles de A − victoires attendues par l'Elo d'avant-match (surface mêlée), en points.
Le niveau des joueurs est donc retiré : on mesure ce que le style apporte EN PLUS de l'Elo.

RÈGLE FIXÉE AVANT DE REGARDER (31/10/2026) :
  découverte 2018–2022, confirmation 2023 → fin d'archive ;
  un duel n'est retenu que si, en découverte, |écart| ≥ 2 points avec z ≥ 2,81 (Bonferroni sur 10 duels) ET,
  en confirmation, le même signe avec z ≥ 1,96. Sinon : rien. Descriptif : aucun changement de l'algo.
Aucune cote.
Usage : python simulateur/etude_duels_styles.py /tmp/sackmann .
"""
import datetime as dt
import heapq
import itertools
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees  # noqa: E402
import elo as E  # noqa: E402
import profils_service as PS  # noqa: E402
import styles_descriptifs as SD  # noqa: E402

DETERMINES = [s for s in SD.STYLES if s != 'indetermine']
COUPURE = dt.date(2023, 1, 1)
Z_DECOUVERTE, Z_CONFIRMATION, ECART_MIN = 2.81, 1.96, 0.02


def lignes(M):
    """[(date, circuit, surface, style gagnant, style perdant, p Elo du gagnant)] — styles et Elo d'avant-match."""
    P, elo = PS.Profils(PS.DEMI_VIE, 1.0), E.Elo()
    attente, serial, out = [], 0, []
    for m in sorted(M, key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0))):
        debut = dt.datetime.combine(m['date'], dt.time())
        while attente and attente[0][0] < debut:
            _, _, a = heapq.heappop(attente)
            P.ajouter(a, a['_g'], a['_p'])
        g, p = m['_g'], m['_p']
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m['surface']
        if c in ('CH', 'ITF'):
            elo.presenter(g, 1200.0)
            elo.presenter(p, 1200.0)
        pe = elo.proba(g, p, s)
        mu = P.moyenne(c, s)
        sg = SD.classifier(*P.profil(g, c, s, m['date']), mu)
        sp = SD.classifier(*P.profil(p, c, s, m['date']), mu)
        if m.get('complet') and not m.get('abandon') and c != 'ITF':
            out.append((m['date'], c, s, sg, sp, pe))
        heapq.heappush(attente, (dt.datetime.combine(m['fin'], dt.time()), serial, m))
        serial += 1
        elo.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') else None)
    return out


def duel(rows, a, b):
    """Bilan de A contre B : n, victoires, attendu, écart, z."""
    n = v = att = var = 0.0
    for _, _, _, sg, sp, pe in rows:
        if (sg, sp) == (a, b):
            n, v, att, var = n + 1, v + 1, att + pe, var + pe * (1 - pe)
        elif (sg, sp) == (b, a):
            n, att, var = n + 1, att + (1 - pe), var + pe * (1 - pe)
    if not n:
        return None
    ec = (v - att) / n
    return {'matchs': int(n), 'victoires_pct': round(100 * v / n, 1), 'attendu_pct': round(100 * att / n, 1),
            'ecart_pts': round(100 * ec, 2), 'z': round((v - att) / math.sqrt(var), 2) if var else 0.0}


def tableau(rows):
    return {f'{a}>{b}': duel(rows, a, b) for a, b in itertools.combinations(DETERMINES, 2)}


def main(archive, racine):
    M = donnees.charger(archive, 2015)
    with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
        alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n))
    for m in M:
        m['_g'], m['_p'] = k(m.get('nom_g')), k(m.get('nom_p'))
    import pickle
    cache = os.environ.get('DUELS_CACHE')
    if cache and os.path.exists(cache):
        R = pickle.load(open(cache, 'rb'))
    else:
        R = [r for r in lignes(M) if r[0] >= dt.date(2018, 1, 1)]
        if cache:
            pickle.dump(R, open(cache, 'wb'))
    dec, conf = [r for r in R if r[0] < COUPURE], [r for r in R if r[0] >= COUPURE]
    out = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': 'découverte 2018–2022 : |écart| ≥ 2 pts et z ≥ 2,81 ; confirmation 2023+ : même signe, z ≥ 1,96',
           'archive_jusqu_au': max(r[0] for r in R).isoformat(), 'matchs': len(R),
           'repartition_styles': {s: sum((r[3] == s) + (r[4] == s) for r in R) for s in SD.STYLES},
           'decouverte': tableau(dec), 'confirmation': tableau(conf), 'par_circuit': {}, 'par_surface': {}}
    for c in ('ATP', 'WTA', 'CH'):
        Rc = [r for r in R if r[1] == c]
        d_c, f_c = tableau([r for r in Rc if r[0] < COUPURE]), tableau([r for r in Rc if r[0] >= COUPURE])
        out['par_circuit'][c] = {'decouverte': d_c, 'confirmation': f_c,
                                 'retenus': [k for k, d in d_c.items() if d and f_c.get(k)
                                             and abs(d['ecart_pts']) >= 100 * ECART_MIN and abs(d['z']) >= Z_DECOUVERTE
                                             and f_c[k]['z'] * d['z'] > 0 and abs(f_c[k]['z']) >= Z_CONFIRMATION]}
    # 01/11/2026 — hypothèse WTA fixée avant ce calcul : profil serveur (grand serveur, serveur attaquant) contre
    # profil non serveur (retourneur pressant, contreur, équilibré).
    SERV, NON = {'grand_serveur', 'serveur_attaquant'}, {'retourneur_pressant', 'contreur', 'equilibre'}
    def groupe(rows):
        n = v = att = var = 0.0
        for _, _, _, sg, sp, pe in rows:
            if sg in SERV and sp in NON:
                n, v, att, var = n + 1, v + 1, att + pe, var + pe * (1 - pe)
            elif sp in SERV and sg in NON:
                n, att, var = n + 1, att + (1 - pe), var + pe * (1 - pe)
        return {'matchs': int(n), 'ecart_pts': round(100 * (v - att) / n, 2), 'z': round((v - att) / math.sqrt(var), 2)} if n else None
    out['wta_serveuses'] = {p: groupe([r for r in R if r[1] == c and (r[0] < COUPURE) == (p == 'decouverte')])
                            for c in ('WTA',) for p in ('decouverte', 'confirmation')}
    out['serveurs_par_circuit'] = {c: {p: groupe([r for r in R if r[1] == c and (r[0] < COUPURE) == (p == 'decouverte')])
                                       for p in ('decouverte', 'confirmation')} for c in ('ATP', 'WTA', 'CH')}
    for s in ('Hard', 'Clay', 'Grass'):
        out['par_surface'][s] = tableau([r for r in R if r[2] == s])
    retenus = []
    for cle, d in out['decouverte'].items():
        c = out['confirmation'].get(cle)
        if d and c and abs(d['ecart_pts']) >= 100 * ECART_MIN and abs(d['z']) >= Z_DECOUVERTE \
                and c['z'] * d['z'] > 0 and abs(c['z']) >= Z_CONFIRMATION:
            retenus.append(cle)
    out['retenus'] = retenus
    with open(os.environ.get('DUELS_SORTIE') or os.path.join(ICI, 'rapport_duels_styles.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(ICI, '..'))
