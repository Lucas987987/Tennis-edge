#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Challenger de pression avec récence, surface, circuit et force adverse.

Les résultats ne sont versés qu'au changement de date par le chef d'orchestre.
Les tie-breaks, sets décisifs et matchs serrés sont des résidus par rapport à
l'Elo pré-match. Les balles de break sont des résidus par rapport aux points
ordinaires du joueur. Ce module ne produit aucune probabilité et ne modifie pas
le champion.
"""
import math

SCHEMA = 'pression_v2'
GEL_UTC = '2026-10-28T00:00:00+00:00'
DEMI_VIE_J = 365.0
PRIORS = {
    'tiebreak': 10.0,
    'decisif': 10.0,
    'proche': 20.0,
    'bp_service': 30.0,
    'bp_retour': 30.0,
}
NOMS = tuple(PRIORS)
VARIABLES = ['pression_v2_' + nom for nom in NOMS]
VARIABLES_V1 = ['pression_' + nom for nom in NOMS]


class HistoriquePressionV2:
    """Résidus historiques disponibles la veille, sans donnée de marché."""

    def __init__(self, demi_vie=DEMI_VIE_J, priors=None):
        self.demi_vie = float(demi_vie)
        self.priors = dict(priors or PRIORS)
        self.events = {}

    def _add(self, joueur, nom, m, residu, poids=1.0):
        if poids <= 0 or not math.isfinite(residu):
            return
        self.events.setdefault((joueur, nom), []).append(
            (m['date'], m['surface'], m['circuit'], float(residu), float(poids)))

    def ajouter(self, m, p_elo_gagnant):
        """Ajoute un match terminé avec sa probabilité Elo connue avant match."""
        if not m.get('complet') or m.get('abandon'):
            return
        g, p = m['gagnant'], m['perdant']
        p_g = min(max(float(p_elo_gagnant), 1e-6), 1 - 1e-6)
        residu_g = 1.0 - p_g
        sets = m.get('sets') or []
        bo = m.get('bo') or 3
        for sg, sp in sets:
            if (sg, sp) in ((7, 6), (6, 7)):
                self._add(g, 'tiebreak', m, residu_g)
                self._add(p, 'tiebreak', m, -residu_g)
        if len(sets) == bo:
            self._add(g, 'decisif', m, residu_g)
            self._add(p, 'decisif', m, -residu_g)
        if .4 <= p_g <= .6:
            self._add(g, 'proche', m, residu_g)
            self._add(p, 'proche', m, -residu_g)

        d = m.get('detail')
        if not d:
            return
        for joueur, propre, adverse in ((g, d['w'], d['l']), (p, d['l'], d['w'])):
            sv, _, w1, w2 = propre[:4]
            bpf, bps = propre[6], propre[7]
            if sv > 0 and bpf > 0:
                attendu = (w1 + w2) / sv
                self._add(joueur, 'bp_service', m, (bps - bpf * attendu) / bpf, bpf)
            osv, _, ow1, ow2 = adverse[:4]
            obpf, obps = adverse[6], adverse[7]
            if osv > 0 and obpf > 0:
                attendu_retour = 1.0 - (ow1 + ow2) / osv
                converties = obpf - obps
                self._add(joueur, 'bp_retour', m,
                          (converties - obpf * attendu_retour) / obpf, obpf)

    def _somme(self, joueur, nom, jour, surface=None, circuit=None):
        n = somme = 0.0
        for date, surf, circ, residu, poids in self.events.get((joueur, nom), []):
            age = (jour - date).days
            if age < 0 or (surface is not None and surf != surface) or (circuit is not None and circ != circuit):
                continue
            w = .5 ** (age / self.demi_vie) * poids
            n += w
            somme += w * residu
        return somme, n

    def mesure(self, joueur, nom, surface, circuit, jour):
        """Résidu contracté : global, puis surface et circuit vers le global."""
        prior = float(self.priors[nom])
        somme, n = self._somme(joueur, nom, jour)
        global_ = somme / (n + prior)
        somme_s, n_s = self._somme(joueur, nom, jour, surface=surface)
        surface_ = (somme_s + prior * global_) / (n_s + prior)
        somme_c, n_c = self._somme(joueur, nom, jour, circuit=circuit)
        circuit_ = (somme_c + prior * global_) / (n_c + prior)
        return {
            'residu': surface_ + circuit_ - global_,
            'residu_global': global_,
            'residu_surface': surface_,
            'residu_circuit': circuit_,
            'n_effectif': n,
            'n_surface': n_s,
            'n_circuit': n_c,
        }

    def features(self, h, a, surface, circuit, jour):
        out = {}
        for nom in NOMS:
            mh = self.mesure(h, nom, surface, circuit, jour)
            ma = self.mesure(a, nom, surface, circuit, jour)
            out['pression_v2_' + nom] = mh['residu'] - ma['residu']
            out['pression_v2_documentation_' + nom] = min(mh['n_effectif'], ma['n_effectif'])
            out['pression_v2_documentation_surface_' + nom] = min(mh['n_surface'], ma['n_surface'])
            out['pression_v2_documentation_circuit_' + nom] = min(mh['n_circuit'], ma['n_circuit'])
        return out
