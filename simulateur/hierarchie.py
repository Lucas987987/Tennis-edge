#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Partage partiel service–retour et incertitude dynamique, avant le match.

Les forces globales sont communes à tous les circuits. Les écarts de surface et
de circuit sont des effets locaux fortement contractés : ce n'est donc pas une
séparation en algorithmes indépendants. Les observations d'une édition de
 tournoi ne sont versées qu'à sa fin, comme dans profils_service.py.
"""
import math

K_GLOBAL, K_SURFACE, K_CIRCUIT = 300.0, 1200.0, 2400.0
PAS_GLOBAL, PAS_LOCAL = 0.12, 0.04
SIGMA_BASE, SIGMA_MIN, SIGMA_MAX = 0.15, 0.05, 0.35
SURFACES = ('Hard', 'Clay', 'Grass')


def _lg(p):
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def _etat():
    return {'srv': 0.0, 'ret': 0.0, 'ns': 0.0, 'nr': 0.0, 'ms': 0, 'mr': 0,
            'vol': 0.0, 'dernier': None}


class HierarchieServiceRetour:
    """Estimateur logistique en ligne avec effets globaux et locaux contractés."""

    def __init__(self, k_global=K_GLOBAL, k_surface=K_SURFACE, k_circuit=K_CIRCUIT,
                 pas_global=PAS_GLOBAL, pas_local=PAS_LOCAL):
        self.k_global, self.k_surface, self.k_circuit = k_global, k_surface, k_circuit
        self.pas_global, self.pas_local = pas_global, pas_local
        self.joueurs, self.surfaces, self.circuits = {}, {}, {}
        self.total = {}

    def _j(self, j):
        return self.joueurs.setdefault(j, _etat())

    @staticmethod
    def _groupe(circuit):
        return 'principal' if circuit in ('ATP', 'WTA') else 'developpement'

    def _base(self, circuit, surface):
        # Prior neutre de 300 points ; les moyennes sont partagées, jamais des modèles séparés.
        n, w = self.total.get((circuit, surface), (0.0, 0.0))
        return _lg((w + 300.0 * .62) / (n + 300.0))

    def _effet(self, j, role, circuit, surface):
        e = self._j(j)
        n = e['ns'] if role == 'srv' else e['nr']
        z = e[role] * n / (n + self.k_global)
        s = self.surfaces.get((j, surface))
        if s:
            ns = s['ns'] if role == 'srv' else s['nr']
            z += s[role] * ns / (ns + self.k_surface)
        c = self.circuits.get((j, self._groupe(circuit)))
        if c:
            nc = c['ns'] if role == 'srv' else c['nr']
            z += c[role] * nc / (nc + self.k_circuit)
        return z

    def point(self, serveur, relanceur, circuit, surface):
        z = self._base(circuit, surface)
        z += self._effet(serveur, 'srv', circuit, surface)
        z -= self._effet(relanceur, 'ret', circuit, surface)
        return min(max(_sg(z), .25), .85)

    def _maj_cote(self, serveur, relanceur, circuit, surface, gagnes, total, date):
        if not total:
            return
        p = self.point(serveur, relanceur, circuit, surface)
        residu = (gagnes - total * p) / total
        a, b = self._j(serveur), self._j(relanceur)
        pa = self.pas_global / math.sqrt(1 + (a['ms'] + a['mr']) / 40)
        pb = self.pas_global / math.sqrt(1 + (b['ms'] + b['mr']) / 40)
        a['srv'] = max(min(a['srv'] + pa * residu, 3), -3)
        b['ret'] = max(min(b['ret'] - pb * residu, 3), -3)
        for j, role, signe, pas in ((serveur, 'srv', 1, pa), (relanceur, 'ret', -1, pb)):
            e = self._j(j)
            e['vol'] = .95 * e['vol'] + .05 * abs(residu)
            e['dernier'] = date
            for table, cle, prior in ((self.surfaces, (j, surface), self.k_surface),
                                      (self.circuits, (j, self._groupe(circuit)), self.k_circuit)):
                q = table.setdefault(cle, _etat())
                local = self.pas_local * pas / max(self.pas_global, 1e-9)
                q[role] = max(min(q[role] + signe * local * residu, 2), -2)
                q['ns' if role == 'srv' else 'nr'] += total
            e['ns' if role == 'srv' else 'nr'] += total
            e['ms' if role == 'srv' else 'mr'] += 1

    def ajouter(self, m):
        """Verse une feuille terminée ; les points manquants sont simplement ignorés."""
        date = m.get('fin') or m['date']
        c, s = m['circuit'], m['surface']
        w, l = m['gagnant'], m['perdant']
        stats = m.get('stats') or {}
        for prefix, serveur, relanceur in (('w', w, l), ('l', l, w)):
            total, won = stats.get(prefix, (0, 0))
            if total > 0:
                self._maj_cote(serveur, relanceur, c, s, won, total, date)
                n, g = self.total.get((c, s), (0.0, 0.0))
                self.total[(c, s)] = (n + total, g + won)

    def documentation(self, j):
        e = self._j(j)
        return e['ns'] + e['nr']

    def sigma(self, h, a, date, sigma_base=SIGMA_BASE):
        """Forme du jour élargie par documentation, absence et volatilité observée."""
        doc = min(self.documentation(h), self.documentation(a))
        absences, vols = [], []
        for j in (h, a):
            e = self._j(j)
            absences.append(max(0, (date - e['dernier']).days) if e['dernier'] else 365)
            vols.append(e['vol'])
        absence = max(absences)
        vol = sum(vols) / 2
        inc_doc = .10 / math.sqrt(1 + doc / 300)
        inc_abs = .04 * min(absence / 180, 1.0)
        inc_vol = .5 * max(0.0, vol - .08)
        sigma = min(max(sigma_base + inc_doc + inc_abs + inc_vol, SIGMA_MIN), SIGMA_MAX)
        return sigma, {'documentation_points': doc, 'absence_jours': absence,
                       'volatilite_residuelle': vol, 'incertitude_documentation': inc_doc,
                       'incertitude_absence': inc_abs, 'incertitude_volatilite': inc_vol}
