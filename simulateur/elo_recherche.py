#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Challengers Elo pour la recherche ; aucun n'est importé par le modèle actif.

Grille courte fixée avant les résultats : chaque variante ne change qu'un mécanisme
par rapport au contrôle (surface 0,3 ; WELO norme ; incertitude 5). Les résultats
sont versés au changement de date, comme dans le socle commun des autres pistes.
"""
import datetime as dt
import math

import elo as E
from pistes_observations import ELO_CONTROLE, cle_match

DEPART_BAS = 1200.0
VARIANTES = {
    'controle': {},
    'decroissance_730j': {'demi_vie_j': 730.0},
    'adaptation_surface_125': {'k_transition_surface': 1.25},
    'apprentissage_challenger_itf_110': {'k_circuits_secondaires': 1.10},
    'prior_nouveaux_1350': {'depart_bas': 1350.0},
    'transition_circuit_115': {'k_transition_circuit': 1.15},
    'format_bo5_110': {'k_bo5': 1.10},
}


class EloVariante(E.Elo):
    def __init__(self, demi_vie_j=None, k_transition_surface=1.0,
                 k_circuits_secondaires=1.0, depart_bas=DEPART_BAS,
                 k_transition_circuit=1.0, k_bo5=1.0, **options):
        super().__init__(**options)
        self.demi_vie_j = demi_vie_j
        self.k_transition_surface = float(k_transition_surface)
        self.k_circuits_secondaires = float(k_circuits_secondaires)
        self.depart_bas = float(depart_bas)
        self.k_transition_circuit = float(k_transition_circuit)
        self.k_bo5 = float(k_bo5)
        self.jour = None
        self.date_g, self.date_s = {}, {}
        self.derniere_surface, self.dernier_circuit = {}, {}

    def a_la_date(self, jour):
        self.jour = jour

    def _decayer(self, j, surface=None):
        if not self.demi_vie_j or self.jour is None:
            return
        centre = self.dep.get(j, self.depart)
        if j in self.g:
            ancien = self.date_g.get(j)
            if ancien is not None and self.jour > ancien:
                f = 2.0 ** (-(self.jour - ancien).days / self.demi_vie_j)
                self.g[j] = centre + f * (self.g[j] - centre)
            self.date_g[j] = self.jour
        cle = (j, surface)
        if surface in E.SURFACES and cle in self.s:
            ancien = self.date_s.get(cle)
            if ancien is not None and self.jour > ancien:
                f = 2.0 ** (-(self.jour - ancien).days / self.demi_vie_j)
                self.s[cle] = centre + f * (self.s[cle] - centre)
            self.date_s[cle] = self.jour

    def note(self, j, surface=None):
        self._decayer(j, surface)
        return super().note(j, surface)

    def options(self):
        out = super().options()
        out.update({'demi_vie_j': self.demi_vie_j, 'k_transition_surface': self.k_transition_surface,
                    'k_circuits_secondaires': self.k_circuits_secondaires, 'depart_bas': self.depart_bas,
                    'k_transition_circuit': self.k_transition_circuit, 'k_bo5': self.k_bo5})
        return out

    def maj(self, gagnant, perdant, surface=None, grand_chelem=False, part=None,
            circuit=None, bo=3):
        w, l = gagnant, perdant
        self._decayer(w, surface)
        self._decayer(l, surface)
        f = 1.1 if grand_chelem else 1.0
        if circuit in ('CH', 'ITF'):
            f *= self.k_circuits_secondaires
        if bo == 5:
            f *= self.k_bo5
        if any(j in self.derniere_surface and self.derniere_surface[j] != surface for j in (w, l)):
            f *= self.k_transition_surface
        if any(j in self.dernier_circuit and self.dernier_circuit[j] != circuit for j in (w, l)):
            f *= self.k_transition_circuit
        if self.welo == 'brut':
            f *= part if part is not None else E.PART_JEUX_MOY
        elif self.welo == 'norme' and part is not None:
            f *= part / E.PART_JEUX_MOY
        gw, gl = self._g(w), self._g(l)
        e = 1 / (1 + 10 ** ((gl - gw) / 400))
        kw, kl = f * self._k(self.n.get(w, 0)), f * self._k(self.n.get(l, 0))
        self.g[w] = gw + kw * (1 - e)
        self.g[l] = gl - kl * (1 - e)
        self.n[w] = self.n.get(w, 0) + 1
        self.n[l] = self.n.get(l, 0) + 1
        if surface in E.SURFACES:
            sw, sl = (w, surface), (l, surface)
            vw, vl = self._s(w, surface), self._s(l, surface)
            e = 1 / (1 + 10 ** ((vl - vw) / 400))
            kw, kl = f * self._k(self.ns.get(sw, 0)), f * self._k(self.ns.get(sl, 0))
            self.s[sw] = vw + kw * (1 - e)
            self.s[sl] = vl - kl * (1 - e)
            self.ns[sw] = self.ns.get(sw, 0) + 1
            self.ns[sl] = self.ns.get(sl, 0) + 1
        if self.jour is not None:
            for j in (w, l):
                self.date_g[j] = self.jour
                if surface in E.SURFACES:
                    self.date_s[(j, surface)] = self.jour
                self.derniere_surface[j] = surface
                self.dernier_circuit[j] = circuit


def predictions(M, choisis):
    """{uid: {variante: probabilité home}}, avec la même orientation que le socle."""
    etats = {nom: EloVariante(**ELO_CONTROLE, **options) for nom, options in VARIANTES.items()}
    out, veille, jour = {}, [], None
    for m in sorted(M, key=lambda x: (x['date'], x.get('tour', 0), x.get('num', 0))):
        if jour != m['date']:
            for ancien in veille:
                for e in etats.values():
                    e.a_la_date(jour)
                    e.maj(ancien['gagnant'], ancien['perdant'], ancien['surface'],
                          ancien.get('niveau') == 'G',
                          E.part_jeux(ancien['sets']) if ancien.get('complet') else None,
                          ancien['circuit'], ancien['bo'])
            veille, jour = [], m['date']
        for nom, e in etats.items():
            e.a_la_date(jour)
            if m['circuit'] in ('CH', 'ITF'):
                e.presenter(m['gagnant'], e.depart_bas)
                e.presenter(m['perdant'], e.depart_bas)
            if id(m) in choisis:
                h, a = sorted((m['gagnant'], m['perdant']))
                out.setdefault(cle_match(m), {})[nom] = e.proba(h, a, m['surface'])
        veille.append(m)
    return out
