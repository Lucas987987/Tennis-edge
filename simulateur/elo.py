#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
elo.py — force de chaque joueur, tirée des RÉSULTATS (21/10/2026).

Classement Elo général + Elo par surface, mélangés à parts égales pour prédire
(méthode publiée par FiveThirtyEight pour le tennis, paramètres repris TELS
QUELS, jamais réglés sur nos données) :
    p(A bat B) = 1 / (1 + 10^((elo_B − elo_A) / 400))
    K du joueur = 250 / (matchs joués + 5)^0,4   (un nouveau bouge vite, un ancien lentement)
Tout joueur commence à 1500, ATP comme ITF : ce sont les résultats qui placent
chacun à son niveau.

Alimentation : archive Sackmann (jusqu'en juin 2026, tous niveaux), puis NOS
résultats (set_results.json) chaque nuit : aucune source extérieure à jour
n'est nécessaire.

Les joueurs sont reconnus par leur NOM, sous une clé insensible à l'ordre des
mots, aux accents, tirets, apostrophes et « Jr » (cle()) : « Christopher
O'Connell », « O Connell Christopher » et « christopher_o_connell » donnent la
même clé.
"""
import math
import re
import unicodedata

SURFACES = ('Hard', 'Clay', 'Grass')
SUFFIXES = {'jr', 'sr', 'ii', 'iii', 'iv'}


def cle(nom):
    s = unicodedata.normalize('NFKD', str(nom or '')).encode('ascii', 'ignore').decode().lower()
    mots = [m for m in re.split(r'[^a-z]+', s) if m and m not in SUFFIXES]
    return ''.join(sorted(''.join(mots)))


class Elo:
    def __init__(self, depart=1500.0):
        self.depart = depart
        self.g, self.s, self.n, self.ns = {}, {}, {}, {}

    def note(self, j, surface=None):
        g = self.g.get(j, self.depart)
        if surface not in SURFACES:
            return g
        return 0.5 * g + 0.5 * self.s.get((j, surface), self.depart)

    def proba(self, a, b, surface=None):
        """Probabilité que A batte B."""
        return 1 / (1 + 10 ** ((self.note(b, surface) - self.note(a, surface)) / 400))

    def matchs(self, j):
        return self.n.get(j, 0)

    @staticmethod
    def _k(n):
        return 250 / (n + 5) ** 0.4

    def maj(self, gagnant, perdant, surface=None):
        """Met à jour après un match (à appeler APRÈS la prédiction de ce match)."""
        w, l = gagnant, perdant
        e = 1 / (1 + 10 ** ((self.g.get(l, self.depart) - self.g.get(w, self.depart)) / 400))
        kw, kl = self._k(self.n.get(w, 0)), self._k(self.n.get(l, 0))
        self.g[w] = self.g.get(w, self.depart) + kw * (1 - e)
        self.g[l] = self.g.get(l, self.depart) - kl * (1 - e)
        self.n[w] = self.n.get(w, 0) + 1
        self.n[l] = self.n.get(l, 0) + 1
        if surface in SURFACES:
            sw, sl = (w, surface), (l, surface)
            e = 1 / (1 + 10 ** ((self.s.get(sl, self.depart) - self.s.get(sw, self.depart)) / 400))
            kw, kl = self._k(self.ns.get(sw, 0)), self._k(self.ns.get(sl, 0))
            self.s[sw] = self.s.get(sw, self.depart) + kw * (1 - e)
            self.s[sl] = self.s.get(sl, self.depart) - kl * (1 - e)
            self.ns[sw] = self.ns.get(sw, 0) + 1
            self.ns[sl] = self.ns.get(sl, 0) + 1

    def exporter(self, noms):
        """{clé: {'nom', 'elo', 'surfaces': {...}, 'matchs'}} pour les pronostics du jour."""
        out = {}
        for j, g in self.g.items():
            out[j] = {'nom': noms.get(j, j), 'elo': round(g, 1), 'matchs': self.n.get(j, 0),
                      'surfaces': {s: round(self.s[(j, s)], 1) for s in SURFACES if (j, s) in self.s}}
        return out

    @classmethod
    def importer(cls, doc):
        e = cls()
        for j, v in doc.items():
            e.g[j] = v['elo']
            e.n[j] = v.get('matchs', 0)
            for s, x in (v.get('surfaces') or {}).items():
                e.s[(j, s)] = x
        return e


def log_loss(p, y):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p if y else 1 - p)
