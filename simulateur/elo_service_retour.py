#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
elo_service_retour.py — un Elo AU SERVICE et un Elo AU RETOUR pour chaque joueur (04/11/2026, demande de Lucas).

Idée : ce qu'un joueur gagne au service compte plus s'il le fait contre un excellent relanceur (et inversement).
Chaque joueur a deux notes en logit, S (service) et R (retour), nulles au départ (= joueur moyen de son circuit).
Joueur A au service contre B :  P(A gagne le point) = sig( base[circuit, surface] + S_A − R_B ).
Après chaque match (feuille : points joués et gagnés au service), pour chaque serveur :
    écart = gagnés − joués · P ;   S_serveur += η_s · écart ;   R_relanceur −= η_r · écart
avec η_x = η · (1 + NOUVEAU · exp(−matchs_x / 10)) (les nouveaux bougent plus vite).
Probabilité de victoire : la chaîne de Markov exacte du match (match_simule.victoire) avec les deux P.
Sources : archive Sackmann (feuilles complètes) puis feuilles TennisApi collectées après l'archive. Aucune cote.
L'ITF femmes sert de DONNÉE (notes mises à jour), jamais de pronostic.
"""
import datetime as dt
import heapq
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

# taux de points gagnés au service, archive 2018–2022 (mesurés le 04/11/2026)
BASE = {('ATP', 'Clay'): .6161, ('ATP', 'Grass'): .6569, ('ATP', 'Hard'): .6409,
        ('CH', 'Clay'): .5960, ('CH', 'Grass'): .6454, ('CH', 'Hard'): .6261,
        ('ITF', 'Clay'): .5401, ('ITF', 'Grass'): .5759, ('ITF', 'Hard'): .5576,
        ('WTA', 'Clay'): .5520, ('WTA', 'Grass'): .5843, ('WTA', 'Hard'): .5680}
NOUVEAU = 3.0


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-z))


def base(c, s):
    return _lg(BASE.get((c, s)) or BASE.get((c, 'Hard')) or .62)


class EloSR:
    def __init__(self, eta=0.004):
        self.eta = eta
        self.S, self.R, self.n = {}, {}, {}

    def p_service(self, a, b, c, s):
        """P(a gagne un point sur son service contre b)."""
        return _sg(base(c, s) + self.S.get(a, 0.0) - self.R.get(b, 0.0))

    def _eta(self, k):
        return self.eta * (1 + NOUVEAU * math.exp(-self.n.get(k, 0) / 10.0))

    def maj(self, g, p, c, s, stats):
        """stats : {'w': (points au service du gagnant, gagnés), 'l': (… du perdant)}."""
        maj = []
        for srv, rel, cle in ((g, p, 'w'), (p, g, 'l')):
            n, w = stats[cle]
            if not n:
                continue
            e = w - n * self.p_service(srv, rel, c, s)
            maj.append((srv, rel, e))
        for srv, rel, e in maj:
            self.S[srv] = self.S.get(srv, 0.0) + self._eta(srv) * e
            self.R[rel] = self.R.get(rel, 0.0) - self._eta(rel) * e
        self.n[g] = self.n.get(g, 0) + 1
        self.n[p] = self.n.get(p, 0) + 1

    def proba(self, a, b, c, s, sets_gagnants=2):
        import match_simule as MS
        return MS.victoire(self.p_service(a, b, c, s), self.p_service(b, a, c, s), sets_gagnants)

    def connu(self, k):
        return self.n.get(k, 0)


def matchs(archive, racine, depuis=2015):
    """Archive Sackmann + feuilles postérieures, clés de joueurs unifiées comme l'Elo (alias)."""
    import json
    import donnees
    import elo as E
    import feuilles as FE
    M = donnees.charger(archive, depuis)
    fin = max(m['date'] for m in M) if M else dt.date(2000, 1, 1)
    F = [m for m in FE.charger(racine) if m['date'] > fin]
    try:
        with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
            alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    out = []
    for m in M + F:
        if not m.get('stats') or not m.get('complet') or m.get('abandon'):
            continue
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if g and p and g != p:
            out.append((m['date'], m.get('tour', 0), m.get('num', 0), g, p, m['circuit'], m['surface'], m['stats']))
    out.sort(key=lambda x: (x[0], x[1], x[2]))
    return out


def rejouer(M, requetes, eta=0.004):
    """requetes : [(jour, a, b, circuit, surface, sets_gagnants, cle_retour)] → {cle_retour: (p_a, n_a, n_b)}.
    Notes d'AVANT le jour de la requête (les matchs du même jour ne comptent pas)."""
    el, out, i = EloSR(eta), {}, 0
    for q in sorted(requetes, key=lambda q: q[0]):
        while i < len(M) and M[i][0] < q[0]:
            _, _, _, g, p, c, s, st = M[i]
            el.maj(g, p, c, s, st)
            i += 1
        jour, a, b, c, s, sg, cle = q
        out[cle] = (el.proba(a, b, c, s, sg), el.connu(a), el.connu(b))
    return out


def log_loss_archive(M, eta, debut, fin, circuits=('ATP', 'WTA', 'CH')):
    """Réglage de η : log loss du VAINQUEUR sur [debut, fin[, notes d'avant chaque jour."""
    el, tot, n, i, jour = EloSR(eta), 0.0, 0, 0, None
    attente = []
    for x in M:
        d, _, _, g, p, c, s, st = x
        if d != jour:
            for y in attente:
                el.maj(*y)
            attente, jour = [], d
        if debut <= d < fin and c in circuits and el.connu(g) >= 5 and el.connu(p) >= 5:
            q = min(max(el.proba(g, p, c, s, 2), 1e-6), 1 - 1e-6)
            tot, n = tot - math.log(q), n + 1
        attente.append((g, p, c, s, st))
    return tot / max(n, 1), n


if __name__ == '__main__':
    archive = sys.argv[1]
    racine = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ICI, '..')
    M = matchs(archive, racine)
    print(len(M), 'matchs')
    for eta in (0.002, 0.004, 0.008, 0.016):
        print(eta, log_loss_archive(M, eta, dt.date(2023, 1, 1), dt.date(2025, 1, 1)))
