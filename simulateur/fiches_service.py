#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fiches_service.py — fiche « service et retour » de chaque joueur pour le Lab (22/10/2026).

Pour chaque joueur actif (un match depuis le 01/01/2025 et au moins 300 balles de
service pondérées), à partir des mêmes profils que le match simulé
(profils_service.py : archive Sackmann + feuilles collectées depuis) :
  — au service : % de 1re balle, aces par 1re balle dans le court, doubles fautes
    par 2e balle, points gagnés derrière la 1re, derrière la 2e jouée, points de
    service gagnés ;
  — au retour : aces concédés, points gagnés en retour sur 1re et sur 2e balle ;
  — tous terrains et par surface (si 150 balles au moins), comparés à la moyenne
    du circuit (ATP, WTA, Challenger…) et rangés en centile parmi les joueurs
    actifs du même circuit (100 = le meilleur ; pour les doubles fautes et les
    aces concédés, moins = mieux, le centile est inversé) ;
  — évolution mois par mois depuis la fin de l'archive, sur les feuilles collectées.
Ce sont des descriptions du jeu, pas des signaux de pari.

Sortie : Tennis_Edge_Lab/live/joueurs_service.json.gz
"""
import collections
import datetime as dt
import gzip
import json
import os

import profils_service as PS

SORTIE = os.path.join('Tennis_Edge_Lab', 'live', 'joueurs_service.json.gz')
ACTIF_DEPUIS = dt.date(2025, 1, 1)
N_MIN, N_MIN_SURFACE = 300.0, 150.0
SURFACES = ('all', 'Hard', 'Clay', 'Grass')
INVERSES = ('d', 'ra')            # moins = mieux


def taux_lisibles(t, mu):
    """Taux du profil -> grandeurs lisibles en % (service et retour)."""
    serv = t['f'] * t['w1'] + (1 - t['f']) * (1 - t['d']) * t['w2j']
    # retour : face à un serveur moyen du circuit, points gagnés = 1 − points gagnés par ce serveur
    ret1, ret2 = 1 - t['r1'], 1 - t['r2j'] * (1 - mu['d'])
    ret = mu['f'] * ret1 + (1 - mu['f']) * ret2
    return {'f': t['f'], 'a': t['a'], 'd': t['d'], 'w1': t['w1'], 'w2j': t['w2j'], 'serv': serv,
            'ra': t['ra'], 'ret1': ret1, 'ret2': 1 - t['r2j'], 'ret': ret}


def circuit_principal(matchs, cle):
    c = collections.Counter()
    for m in matchs:
        if m['date'] >= ACTIF_DEPUIS:
            for k in (cle(m['nom_g']), cle(m['nom_p'])):
                c[(k, m['circuit'])] += 1
    out = {}
    for (k, circ), n in c.items():
        if n > out.get(k, (None, 0))[1]:
            out[k] = (circ, n)
    return {k: v[0] for k, v in out.items()}


def evolution(F, cle):
    """{joueur: [[mois, matchs, aces/match, 1re %, gagnés 1re %, gagnés 2e %, service %, retour %]]} (feuilles)."""
    acc = collections.defaultdict(lambda: collections.defaultdict(lambda: [0] * 9))
    for m in F:
        d = m.get('detail')
        if not d:
            continue
        mois = m['date'].isoformat()[:7]
        for k, a, b in ((cle(m['nom_g']), d['w'], d['l']), (cle(m['nom_p']), d['l'], d['w'])):
            x = acc[k][mois]
            sv, in1, w1, w2, ace = a[:5]
            osv, ow1, ow2 = b[0], b[2], b[3]
            for i, v in enumerate((1, ace, sv, in1, w1, w2, sv - in1, osv, osv - ow1 - ow2)):
                x[i] += v
    out = {}
    for k, mois in acc.items():
        L = []
        for mo, x in sorted(mois.items()):
            n, ace, sv, in1, w1, w2, sec, osv, ret = x
            L.append([mo, n, round(ace / n, 1), round(100 * in1 / sv, 1), round(100 * w1 / in1, 1),
                      round(100 * w2 / sec, 1) if sec else None, round(100 * (w1 + w2) / sv, 1),
                      round(100 * ret / osv, 1) if osv else None])
        out[k] = L
    return out


def construire(P, jour, matchs, F, cle):
    """Document du Lab. P : Profils (au jour d'export) ; matchs : tous (archive + feuilles) ; F : feuilles seules."""
    princ = circuit_principal(matchs, cle)
    dernier = {}
    for m in matchs:
        for k in (cle(m['nom_g']), cle(m['nom_p'])):
            if m['date'] > dernier.get(k, dt.date.min):
                dernier[k] = m['date']
    evo = evolution(F, cle)
    facteur = 1.0 / P._poids(jour)
    J, moyennes = {}, {}
    for (k, s), v in P.j.items():
        if s != 'all' or k not in princ or dernier.get(k, dt.date.min) < ACTIF_DEPUIS:
            continue
        n = v[PS.I['svpt']] * facteur
        if n < N_MIN:
            continue
        circ = princ[k]
        fiche = {'nom': P.noms.get(k, k), 'circuit': circ, 'balles': round(n), 'dernier_match': dernier[k].isoformat(),
                 'surfaces': {}}
        for surf in SURFACES:
            ns = (P.j.get((k, surf)) or [0] * len(PS.CHAMPS))[PS.I['svpt']] * facteur
            if surf != 'all' and ns < N_MIN_SURFACE:
                continue
            t = profil_tous_terrains(P, k, circ, jour) if surf == 'all' else P.profil(k, circ, surf, jour)[0]
            mu = P.moyenne(circ, surf)
            fiche['surfaces'][surf] = {'balles': round(ns), 'joueur': {a: round(b, 3) for a, b in taux_lisibles(t, mu).items()}}
            moyennes.setdefault(circ, {})[surf] = {a: round(b, 3) for a, b in taux_lisibles(mu, mu).items()}
        if k in evo:
            fiche['evolution'] = evo[k]
        J[k] = fiche
    # centiles tous terrains, par circuit
    par_c = collections.defaultdict(list)
    for k, f in J.items():
        par_c[f['circuit']].append(k)
    for circ, ks in par_c.items():
        for stat in ('f', 'a', 'd', 'w1', 'w2j', 'serv', 'ra', 'ret1', 'ret2', 'ret'):
            vals = sorted(J[k]['surfaces']['all']['joueur'][stat] for k in ks)
            for k in ks:
                v = J[k]['surfaces']['all']['joueur'][stat]
                rang = sum(x < v for x in vals) + 0.5 * sum(x == v for x in vals)
                c = 100 * rang / len(vals)
                J[k]['surfaces']['all'].setdefault('centiles', {})[stat] = round(100 - c if stat in INVERSES else c)
    return {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'profils_au': jour.isoformat(),
            'joueurs_par_circuit': {c: len(v) for c, v in par_c.items()}, 'moyennes': moyennes, 'joueurs': J}


def profil_tous_terrains(P, k, circ, jour):
    """Profil tous terrains (premier étage du rappel vers la moyenne), à l'échelle du circuit."""
    mu = P.moyenne(circ, 'all')
    sa = P.j.get((k, 'all'))
    facteur = 1.0 / P._poids(jour)
    out = {}
    for t, (num, den, force) in PS.TAUX.items():
        n = PS._val(sa, den) * facteur
        x = PS._val(sa, num) * facteur
        out[t] = (x + force * mu[t]) / (n + force)
    return out


def ecrire(doc, racine):
    p = os.path.join(racine, SORTIE)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    data = json.dumps(doc, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')
    try:
        with gzip.open(p, 'rb') as f:
            old = json.loads(f.read())
        if {k: v for k, v in old.items() if k != 'genere_le'} == {k: v for k, v in doc.items() if k != 'genere_le'}:
            return False
    except (OSError, ValueError):
        pass
    with open(p, 'wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as g:
            g.write(data)
    return True
