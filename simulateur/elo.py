#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
elo.py — force de chaque joueur, tirée des RÉSULTATS (21/10/2026).

Classement Elo général + Elo par surface, mélangés à parts égales pour prédire
(méthode FiveThirtyEight pour le tennis, décrite par Kovalchik, JQAS 2016 ;
mélange surface/général à 50/50 de Tennis Abstract ; paramètres repris TELS
QUELS, jamais réglés sur nos données) :
    p(A bat B) = 1 / (1 + 10^((elo_B − elo_A) / 400))
    K du joueur = 250 / (matchs joués + 5)^0,4   (un nouveau bouge vite, un ancien lentement)
    K × 1,1 en Grand Chelem
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
        self.g, self.s, self.n, self.ns, self.dep = {}, {}, {}, {}, {}

    def presenter(self, j, valeur):
        """Note de départ d'un joueur jamais vu (ex. 1200 s'il débute en Challenger/ITF)."""
        if j not in self.g and j not in self.dep:
            self.dep[j] = valeur

    def _g(self, j):
        return self.g.get(j, self.dep.get(j, self.depart))

    def _s(self, j, surface):
        return self.s.get((j, surface), self.dep.get(j, self.depart))

    def note(self, j, surface=None):
        g = self._g(j)
        if surface not in SURFACES:
            return g
        return 0.5 * g + 0.5 * self._s(j, surface)

    def proba(self, a, b, surface=None):
        """Probabilité que A batte B."""
        return 1 / (1 + 10 ** ((self.note(b, surface) - self.note(a, surface)) / 400))

    def matchs(self, j):
        return self.n.get(j, 0)

    @staticmethod
    def _k(n):
        return 250 / (n + 5) ** 0.4

    def maj(self, gagnant, perdant, surface=None, grand_chelem=False):
        """Met à jour après un match (à appeler APRÈS la prédiction de ce match)."""
        w, l = gagnant, perdant
        f = 1.1 if grand_chelem else 1.0
        gw, gl = self._g(w), self._g(l)
        e = 1 / (1 + 10 ** ((gl - gw) / 400))
        kw, kl = f * self._k(self.n.get(w, 0)), f * self._k(self.n.get(l, 0))
        self.g[w] = gw + kw * (1 - e)
        self.g[l] = gl - kl * (1 - e)
        self.n[w] = self.n.get(w, 0) + 1
        self.n[l] = self.n.get(l, 0) + 1
        if surface in SURFACES:
            sw, sl = (w, surface), (l, surface)
            vw, vl = self._s(w, surface), self._s(l, surface)
            e = 1 / (1 + 10 ** ((vl - vw) / 400))
            kw, kl = f * self._k(self.ns.get(sw, 0)), f * self._k(self.ns.get(sl, 0))
            self.s[sw] = vw + kw * (1 - e)
            self.s[sl] = vl - kl * (1 - e)
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


# ------------------------------------------------------------------ identité des joueurs
def mots(nom):
    s = unicodedata.normalize('NFKD', str(nom or '')).encode('ascii', 'ignore').decode().lower()
    return [m for m in re.split(r'[^a-z]+', s) if m and m not in SUFFIXES]


def unifier(connus, nouveaux):
    """Relie un nom écrit autrement au joueur déjà connu (22/10/2026).

    « Leylah Fernandez » (OddsPapi) et « Leylah Annie Fernandez » (Sackmann) ont
    des clés différentes : sans ce lien, le même joueur aurait DEUX classements,
    chacun nourri d'une partie de ses résultats. Règle : les mots d'un nom sont
    inclus dans ceux de l'autre (un prénom en plus ou en moins), au moins deux
    mots en commun, et un SEUL joueur connu possible — sinon on ne relie pas.
    connus : {clé: nom} ; nouveaux : noms -> {clé du nouveau: clé du connu}."""
    par_mot, toks = {}, {}
    for k, n in connus.items():
        t = set(mots(n))
        toks[k] = t
        for w in t:
            par_mot.setdefault(w, set()).add(k)
    alias = {}
    for n in nouveaux:
        k = cle(n)
        if k in connus or k in alias:
            continue
        t = set(mots(n))
        if len(t) < 2:
            continue
        cands = set()
        for w in t:
            cands |= par_mot.get(w, set())
        bons = {c for c in cands if (t <= toks[c] or toks[c] <= t) and len(t & toks[c]) >= 2}
        if len(bons) == 1:
            alias[k] = next(iter(bons))
    return alias
