#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
profils_service.py — profil de service et de retour de chaque joueur (22/10/2026).

Tiré des feuilles de match de l'archive Sackmann (jusqu'en juin 2026) :
  au service : f   = % de 1re balle dans le court        (1stIn / svpt)
               a   = aces par 1re balle dans le court      (ace / 1stIn)
               w1  = points gagnés derrière la 1re balle   (1stWon / 1stIn)
               d   = doubles fautes par 2e balle           (df / 2es balles)
               w2j = points gagnés quand la 2e balle est jouée (2ndWon / (2es balles − df))
  au retour  : ra  = aces concédés par 1re balle adverse dans le court
               r1  = points perdus derrière la 1re balle adverse (= w1 de l'adversaire)
               r2j = points perdus quand la 2e balle adverse est jouée

Chaque taux est une moyenne pondérée dans le temps (demi-vie 1 an), ramenée
vers la moyenne (deux étages, fixés d'avance, jamais réglés sur les résultats) :
  1. tous terrains : vers la moyenne du circuit (ATP, WTA, Challenger) ;
  2. par surface   : vers « moyenne du circuit sur cette surface + écart du
     joueur tous terrains » (en logit). Un joueur qui a peu joué sur gazon garde
     son style, à l'échelle du gazon.
Force du rappel (en nombre de balles) : PRIOR ci-dessous.

POINT-IN-TIME : Profils.ajouter() reçoit les matchs dans l'ordre, et le
backtest n'ajoute un tournoi qu'une fois terminé (champ `fin`).

Usage : python simulateur/profils_service.py <archive Sackmann> [racine]
        -> simulateur/profils_service.json (sommes pondérées par joueur).
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees  # noqa: E402
import elo as E  # noqa: E402

SORTIE = os.path.join(ICI, 'profils_service.json')
DEMI_VIE = 365.0
REF = dt.date(2016, 1, 1)
SURFACES = ('Hard', 'Clay', 'Grass')
# Sommes stockées (ordre fixe) : service puis retour (statistiques de l'adversaire).
CHAMPS = ('svpt', 'in1', 'w1', 'ace', 'sec', 'df', 'w2',
          'o_in1', 'o_w1', 'o_ace', 'o_sec', 'o_df', 'o_w2')
I = {c: i for i, c in enumerate(CHAMPS)}
# taux : (numérateur, dénominateur, force du rappel en balles)
TAUX = {'f': ('in1', 'svpt', 150), 'a': ('ace', 'in1', 150), 'w1': ('w1', 'in1', 200),
        'd': ('df', 'sec', 150), 'w2j': ('w2', 'sec-df', 200),
        'ra': ('o_ace', 'o_in1', 400), 'r1': ('o_w1', 'o_in1', 400), 'r2j': ('o_w2', 'o_sec-o_df', 400)}
REPLI = {'f': 0.62, 'a': 0.10, 'w1': 0.72, 'd': 0.07, 'w2j': 0.56, 'ra': 0.10, 'r1': 0.72, 'r2j': 0.56}


def _lg(x):
    x = min(max(x, 1e-4), 1 - 1e-4)
    return math.log(x / (1 - x))


def _sg(z):
    return 1 / (1 + math.exp(-z))


def _val(s, nom):
    if nom == 'sec-df':
        return s[I['sec']] - s[I['df']]
    if nom == 'o_sec-o_df':
        return s[I['o_sec']] - s[I['o_df']]
    return s[I[nom]]


def sommes_du_match(d_moi, d_adv):
    """13 sommes d'un joueur pour un match (detail Sackmann : svpt, in1, w1, w2, ace, df, …)."""
    sv, in1, w1, w2, ace, df = d_moi[:6]
    osv, oin1, ow1, ow2, oace, odf = d_adv[:6]
    return (sv, in1, w1, ace, sv - in1, df, w2, oin1, ow1, oace, osv - oin1, odf, ow2)


class Profils:
    def __init__(self, demi_vie=DEMI_VIE):
        self.hl = demi_vie
        self.j = {}          # (joueur, surface | 'all') -> sommes pondérées
        self.m = {}          # (circuit, surface | 'all') -> sommes pondérées
        self.noms = {}

    def _poids(self, jour):
        return 2.0 ** ((jour - REF).days / self.hl)

    def _ajouter(self, table, cle, val, w):
        s = table.get(cle)
        if s is None:
            s = table[cle] = [0.0] * len(CHAMPS)
        for i, v in enumerate(val):
            s[i] += w * v

    def ajouter(self, m, cle_g=None, cle_p=None):
        """Ajoute les deux feuilles d'un match Sackmann (m['detail'] requis)."""
        if not m.get('detail'):
            return
        w = self._poids(m['fin'])
        g, p = cle_g or m['gagnant'], cle_p or m['perdant']
        dw, dl = m['detail']['w'], m['detail']['l']
        for j, a, b, nom in ((g, dw, dl, m.get('nom_g')), (p, dl, dw, m.get('nom_p'))):
            v = sommes_du_match(a, b)
            for surf in ('all', m['surface']):
                self._ajouter(self.j, (j, surf), v, w)
                self._ajouter(self.m, (m['circuit'], surf), v, w)
            if nom:
                self.noms[j] = nom

    # ---------------------------------------------------------------- lecture
    def moyenne(self, circuit, surface):
        """Profil moyen du circuit sur la surface (repli : tous terrains, puis ATP/WTA, puis valeurs fixes)."""
        rep = {'CH': 'ATP', 'ITF': 'WTA'}.get(circuit)
        for c, s in ((circuit, surface), (circuit, 'all'), (rep, surface), (rep, 'all')):
            x = self.m.get((c, s))
            if x and x[I['svpt']] > 0:
                return {k: (_val(x, num) / _val(x, den) if _val(x, den) > 0 else REPLI[k])
                        for k, (num, den, _) in TAUX.items()}
        return dict(REPLI)

    def profil(self, joueur, circuit, surface, jour):
        """Profil rétréci (deux étages), à l'échelle du circuit et de la surface du match.
        Renvoie (profil, balles de service effectives du joueur)."""
        mu_all, mu_s = self.moyenne(circuit, 'all'), self.moyenne(circuit, surface)
        facteur = 1.0 / self._poids(jour)          # sommes ramenées à leur poids au jour du match
        sa, ss = self.j.get((joueur, 'all')), self.j.get((joueur, surface))
        out = {}
        for k, (num, den, force) in TAUX.items():
            dev = 0.0
            if sa:
                n = _val(sa, den) * facteur
                x = _val(sa, num) * facteur
                r_all = (x + force * mu_all[k]) / (n + force)
                dev = _lg(r_all) - _lg(mu_all[k])
            prior = _sg(_lg(mu_s[k]) + dev)
            if ss:
                n = _val(ss, den) * facteur
                x = _val(ss, num) * facteur
                out[k] = (x + force * prior) / (n + force)
            else:
                out[k] = prior
        n_eff = (sa[I['svpt']] * facteur) if sa else 0.0
        return out, n_eff

    # ---------------------------------------------------------------- export
    def exporter(self, jour, depuis=None, n_min=50.0):
        facteur = 1.0 / self._poids(jour)
        J = {}
        for (j, s), v in self.j.items():
            tot = self.j.get((j, 'all'))
            if not tot or tot[I['svpt']] * facteur < n_min:
                continue
            J.setdefault(j, {'nom': self.noms.get(j, j), 'sommes': {}})['sommes'][s] = [round(x * facteur, 1) for x in v]
        Mo = {f"{c} {s}": [round(x * facteur, 1) for x in v] for (c, s), v in self.m.items()}
        return {'jour': jour.isoformat(), 'demi_vie_j': self.hl, 'champs': list(CHAMPS),
                'taux': {k: list(v) for k, v in TAUX.items()}, 'moyennes': Mo, 'joueurs': J}

    @classmethod
    def importer(cls, doc):
        """Profils lus depuis profils_service.json (sommes au jour d'export ; jour du match = jour d'export)."""
        P = cls(doc.get('demi_vie_j', DEMI_VIE))
        jour = dt.date.fromisoformat(doc['jour'])
        w = P._poids(jour)
        for k, v in (doc.get('moyennes') or {}).items():
            c, _, s = k.partition(' ')
            P.m[(c, s)] = [x * w for x in v]
        for j, d in (doc.get('joueurs') or {}).items():
            P.noms[j] = d.get('nom', j)
            for s, v in d['sommes'].items():
                P.j[(j, s)] = [x * w for x in v]
        P.jour_export = jour
        return P


def construire(M, jusqu_au=None, cle=None):
    """Profils de tous les matchs terminés avant `jusqu_au` (tous si None). cle : nom -> clé joueur."""
    P = Profils()
    for m in M:
        if jusqu_au and m['fin'] >= jusqu_au:
            continue
        if cle:
            P.ajouter(m, cle(m['nom_g']), cle(m['nom_p']))
        else:
            P.ajouter(m)
    return P


def main(argv):
    dossier = argv[1] if len(argv) > 1 else 'sackmann'
    M = donnees.charger(dossier, 2016)
    if not M:
        print(f"::error::aucun match Sackmann sous {dossier}")
        return 1
    fin = max(m['date'] for m in M)
    P = construire(M, cle=E.cle)
    doc = P.exporter(fin)
    doc['genere_le'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    doc['source'] = 'archive Jeff Sackmann (CC BY-NC-SA 4.0), feuilles de match jusqu\'au ' + fin.isoformat()
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    avec = sum(1 for m in M if m.get('detail'))
    print(f"Profils de service : {len(doc['joueurs'])} joueurs ({avec} feuilles de match sur {len(M)}), "
          f"jusqu'au {fin} -> {SORTIE} ({os.path.getsize(SORTIE) // 1024} Ko)")
    for c in ('ATP', 'WTA', 'CH'):
        mo = P.moyenne(c, 'all')
        print(f"  {c} : 1re {100 * mo['f']:.1f} % · aces/1re {100 * mo['a']:.1f} % · gagnés 1re {100 * mo['w1']:.1f} % · "
              f"DF/2e {100 * mo['d']:.1f} % · gagnés 2e jouée {100 * mo['w2j']:.1f} %")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
