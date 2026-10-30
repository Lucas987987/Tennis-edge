#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
activite.py — l'activité récente de chaque joueur (29/10/2026).

Sources : les feuilles de match (feuilles/, ATP, WTA, Challenger, et l'ITF collecté avant le 22/10) et les résultats
ITF (resultats_itf/, resultats_itf_femmes/), un match compté une fois (identifiant TennisApi). Jamais de cote.

Pour un joueur avant un jour J (le jour J exclu) :
  m30       matchs joués dans les 30 jours avant J ;   m90 : dans les 60 jours d'avant (de J−90 à J−30) ;
  balles30  balles de service jouées sur 30 jours (feuilles avec statistiques seulement) ;
  tendance  ln((m30 + 1) / 30) − ln((m90 + 1) / 60) : > 0 joue plus qu'avant, < 0 moins ;
  volume    ln(1 + m30) ;
  repos     jours depuis son dernier match (None : jamais vu).

Étude du 29/10/2026 (4 820 pronostics hors échantillon, jugement depuis le 14/09) : ajoutée seule au mélange, la
tendance gagne +0,0026 (Challenger +0,0067) mais la WTA perd 0,0081 → rejetée. Descriptif : activité en hausse
+1,4 point de victoires par rapport au prévu, en baisse −0,7 ; 0 à 2 matchs sur 30 jours −5,4 ; retour d'absence
(joueur documenté, < 3 matchs en 90 jours) −6,6 sur 112 cas seulement. D'où : candidat dans les ARBRES (qui savent
séparer les circuits), jugé chaque semaine (entrainement_progressif.modele_arbres_activite) ; et affichage seul sur
la carte de chaque match (vitrine.ajouter_activite).
"""
import bisect
import datetime as dt
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
RETOUR_J = 45          # « revient après X jours sans match » à partir de 45 jours


class Activite:
    def __init__(self, matchs, cle=None, sexes=None):
        """matchs : [(jour date, [(nom, balles ou None), …])] ; sexes : {nom: 'H' ou 'F'} (facultatif)."""
        import elo as E
        cle = cle or E.cle
        par = {}
        for jour, joueurs in matchs:
            for nom, b in joueurs:
                if nom:
                    par.setdefault(cle(nom), []).append((jour, b))
        self.matchs = {k: sorted(v, key=lambda x: x[0]) for k, v in par.items()}
        self.jours = {k: [x[0] for x in v] for k, v in self.matchs.items()}
        self.sexe = {cle(n): s for n, s in (sexes or {}).items() if n}
        self._ref = {}

    def reference(self, jour, sexe):
        """29/10/2026 — tendance MÉDIANE des joueurs actifs (au moins un match sur 30 jours) du même sexe ce jour-là :
        la saison (octobre chargé) et notre collecte (ITF femmes depuis fin mai) gonflent toutes les tendances
        ensemble ; un joueur n'est « en hausse » que s'il joue plus que les autres en ce moment."""
        if isinstance(jour, dt.datetime):
            jour = jour.date()
        cle_r = (jour, sexe)
        if cle_r not in self._ref:
            L = sorted(v['tendance'] for v in (self._brut(k, jour) for k, s in self.sexe.items() if s == sexe)
                       if v['m30'] > 0)
            self._ref[cle_r] = L[len(L) // 2] if L else 0.0
        return self._ref[cle_r]

    @classmethod
    def depuis(cls, racine, fiches=None, cle=None):
        """Feuilles + résultats ITF (hommes et femmes), dédoublonnés par identifiant."""
        import feuilles as FE
        sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
        vus, M, sexes = set(), [], {}
        for r in (FE.lire(racine) if fiches is None else fiches):
            if r.get('vainqueur') not in (1, 2) or not r.get('jour') or r.get('id') in vus:
                continue
            vus.add(r.get('id'))
            cat = str(r.get('categorie') or '').lower()
            if 'itf' not in cat:                       # sexe des joueurs ATP / WTA / Challenger
                for c in ('home', 'away'):
                    sexes[(r.get(c) or {}).get('nom')] = 'F' if ('wta' in cat or 'women' in cat or 'billie' in cat or 'bjk' in cat) else 'H'
            st = (r.get('stats') or {}).get('ALL') or {}
            jj = []
            for i, c in ((0, 'home'), (2, 'away')):
                d = FE.detail(st, i) if st else None
                jj.append(((r.get(c) or {}).get('nom'), d[0] if d else None))
            M.append((dt.date.fromisoformat(r['jour']), jj))
        try:
            import resultats_itf as RI
            for dossier in (RI.DOSSIER_HOMMES, RI.DOSSIER_FEMMES):
                for r in RI.lire_tout(racine, dossier):
                    if r.get('vainqueur') not in (1, 2) or not r.get('jour') or r.get('id') in vus:
                        continue
                    vus.add(r.get('id'))
                    M.append((dt.date.fromisoformat(r['jour']), [((r.get(c) or {}).get('nom'), None) for c in ('home', 'away')]))
        except ImportError:
            pass
        return cls(M, cle, sexes)

    def _fen(self, k, jour, a, b):
        L = self.jours.get(k) or []
        i = bisect.bisect_left(L, jour - dt.timedelta(days=b))
        j = bisect.bisect_left(L, jour - dt.timedelta(days=a))
        seg = self.matchs[k][i:j] if L else []
        return len(seg), sum(x[1] for x in seg if x[1])

    def variables(self, k, jour, relatif=False):
        """Activité du joueur (clé) avant le jour (date) ; le jour lui-même exclu. relatif=True (affichage) : ajoute
        « tendance_relative » = tendance − tendance médiane de son circuit (hommes / femmes) ce jour-là."""
        v = self._brut(k, jour)
        s = self.sexe.get(k)
        if relatif and s:
            v['tendance_relative'] = round(v['tendance'] - self.reference(jour, s), 4)
        return v

    def _brut(self, k, jour):
        if isinstance(jour, dt.datetime):
            jour = jour.date()
        m30, b30 = self._fen(k, jour, 0, 30)
        m90, _ = self._fen(k, jour, 30, 90)
        L = self.jours.get(k) or []
        i = bisect.bisect_left(L, jour)
        repos = (jour - L[i - 1]).days if i else None
        return {'m30': m30, 'm90': m90, 'balles30': round(b30), 'repos': repos,
                'tendance': round(math.log((m30 + 1) / 30) - math.log((m90 + 1) / 60), 4),
                'volume': round(math.log(1 + m30), 4)}


def ecarts(va, vb):
    """(Δ tendance, Δ volume) vu du joueur 1 — les deux variables des arbres."""
    return va['tendance'] - vb['tendance'], va['volume'] - vb['volume']


def resume(v):
    """Catégorie lisible : 'retour' (≥ 45 jours sans match), 'peu', 'hausse', 'baisse', 'stable', ou None (jamais vu)."""
    if not v or v.get('repos') is None:
        return None
    if v['repos'] >= RETOUR_J:
        return 'retour'
    if v['m30'] + v['m90'] < 3:
        return 'peu'
    t = v.get('tendance_relative', v['tendance'])           # 29/10/2026 : par rapport à son circuit si connu
    return 'hausse' if t > 0.4 else 'baisse' if t < -0.4 else 'stable'
