#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resultats_points.py — la simulation apprend des RÉSULTATS, match après match (22/10/2026).

La simulation apprend des points (aces, 1re balle, retour…) puis en déduit le vainqueur ; l'Elo,
lui, apprend directement de qui a gagné. Cette couche donne à la simulation ce que l'Elo a :
après chaque match, le niveau au service ET au retour de chaque joueur est corrigé dans le sens
de l'erreur de la simulation elle-même :
    p = P(vainqueur) selon la simulation (taux du point + couche), R_vainqueur += K·(1 − p),
    R_perdant −= K·(1 − p)
R (logit) décale les points gagnés derrière la 1re et la 2e balle : au service pour soi, au retour
contre soi. Une victoire attendue ne bouge presque rien, une surprise bouge beaucoup — comme l'Elo,
mais à l'échelle du point, si bien que la simulation garde sa façon de jouer (aces, 1re balle…).
K est choisi sur 2024 et jugé sur 2025 → (backtest_match_simule.choisir_reglage) ; tous les
circuits nourrissent la couche (ITF compris), à partir du 1er janvier 2023.
"""
import match_simule as S


def _decale(t, d):
    if not d:
        return t
    return dict(t, w1=S._sg(S._lg(t['w1']) + d), w2j=S._sg(S._lg(t['w2j']) + d))


class CoucheResultats:
    def __init__(self, K, R=None):
        self.K = float(K)
        self.R = dict(R or {})
        self._cache = {}

    def ecart(self, serveur, relanceur):
        return self.R.get(serveur, 0.0) - self.R.get(relanceur, 0.0)

    def decaler(self, t_srv, serveur, relanceur):
        """Taux du point du serveur contre le relanceur, corrigés par les résultats."""
        return S.borner(_decale(t_srv, self.ecart(serveur, relanceur)))

    def proba(self, tA, tB, sg):
        """P(A gagne) de la simulation pure (σ = 0), mise en cache au pas de 0,002."""
        pa = min(max(S.p_service(tA), 0.3), 0.95)
        pb = min(max(S.p_service(tB), 0.3), 0.95)
        k = (round(pa / 0.002), round(pb / 0.002), sg)
        if k not in self._cache:
            self._cache[k] = S.victoire(k[0] * 0.002, k[1] * 0.002, sg)
        return self._cache[k]

    def apprendre(self, gagnant, perdant, t_g, t_p, sg):
        """t_g : taux du gagnant au service contre le perdant (modèle des points, sans la couche) ; t_p : l'inverse."""
        p = self.proba(self.decaler(t_g, gagnant, perdant), self.decaler(t_p, perdant, gagnant), sg)
        e = self.K * (1 - p)
        self.R[gagnant] = self.R.get(gagnant, 0.0) + e
        self.R[perdant] = self.R.get(perdant, 0.0) - e
        return p

    def exporter(self, joueurs=None):
        return {j: round(v, 4) for j, v in self.R.items() if abs(v) >= 1e-4 and (joueurs is None or j in joueurs)}


def rejouer(matchs, adj, K, cle, debut, fin=None):
    """Couche apprise sur tous les matchs terminés [debut ; fin[ (score complet), modèle des points adj."""
    import datetime as dt
    C = CoucheResultats(K)
    for m in matchs:
        if m['date'] < debut or (fin and m['date'] >= fin) or not m.get('complet') or not m.get('sets'):
            continue
        g, p = cle(m['nom_g']), cle(m['nom_p'])
        tg = S.borner(adj.taux(g, p, m['circuit'], m['surface']))
        tp = S.borner(adj.taux(p, g, m['circuit'], m['surface']))
        C.apprendre(g, p, tg, tp, 3 if m.get('bo') == 5 else 2)
    return C
