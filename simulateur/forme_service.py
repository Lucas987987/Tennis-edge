#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
forme_service.py — le service et le retour « du moment » de chaque joueur (29/10/2026, demande de Lucas).

Source : les feuilles de match (feuilles/, statistiques TennisApi), un match compté une fois. Jamais de cote.

Pour un joueur, avant un jour J (exclu), sur la SURFACE du match (dur, terre, gazon) :
  récent : les 30 jours avant J ; référence : de J−395 à J−30 ;
  service = part des points gagnés au service ; retour = part des points gagnés au retour ;
  écart (logit) = (logit récent − logit référence) × n / (n + K), K = 300 points (peu de points : écart réduit),
  borné à ±0,4. Sans référence d'au moins 300 points sur la surface : pas d'écart.

DEUX USAGES :
  1. INFORMATION sur la carte du match (hausse / baisse / stable : ±3 points, au moins 150 points récents).
  2. MODÈLE FANTÔME (pronostics_du_jour.controle_forme_service) : la simulation rejouée avec ces écarts
     (service du joueur + retour adverse), puis le même mélange avec l'Elo et les mêmes ajustements → une
     probabilité « avec la forme du service », jamais affichée comme pronostic. Après chaque match, les deux sont
     comparées au vainqueur réel (apres_match : fantome_forme_service).

RÈGLE FIXÉE AVANT RÉSULTAT (29/10/2026) : jugée sur les matchs pronostiqués à partir du 30/10 ; rien avant 30 matchs ;
adoptée seulement si sa log loss est plus basse d'au moins 0,001 deux semaines de suite et qu'aucun circuit
(ATP, WTA, Challenger) n'est dégradé de plus de 0,001.
Limite connue : les taux sont bruts (pas corrigés du niveau des adversaires rencontrés) — c'est au fantôme de dire
si la forme ainsi mesurée apporte quelque chose.
"""
import bisect
import datetime as dt
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
RECENT_J, REFERENCE_J = 30, 395
K = 300.0                  # points : retrait vers 0 de l'écart quand le récent est mince
BORNE = 0.4                # écart maximal en logit
MIN_REFERENCE = 300        # points de référence au minimum sur la surface
SEUIL_PTS, MIN_RECENT = 0.03, 150      # affichage : hausse / baisse à ±3 points, 150 points récents au moins


def surface_feuille(s):
    s = str(s or '').lower()
    return 'Clay' if 'clay' in s else 'Grass' if 'grass' in s else 'Hard' if ('hard' in s or 'carpet' in s) else None


def _lg(x):
    x = min(max(x, 1e-6), 1 - 1e-6)
    return math.log(x / (1 - x))


class FormeService:
    def __init__(self, lignes, cle=None):
        """lignes : [(jour, nom, surface, pts_service, gagnés_service, pts_retour, gagnés_retour)]."""
        import elo as E
        cle = cle or E.cle
        par = {}
        for jour, nom, s, sp, sw, rp, rw in lignes:
            if nom and s:
                par.setdefault(cle(nom), []).append((jour, s, sp, sw, rp, rw))
        self.m = {k: sorted(v, key=lambda x: x[0]) for k, v in par.items()}
        self.j = {k: [x[0] for x in v] for k, v in self.m.items()}

    @classmethod
    def depuis(cls, racine, fiches=None, cle=None):
        import feuilles as FE
        vus, L = set(), []
        for r in (FE.lire(racine) if fiches is None else fiches):
            if r.get('id') in vus or not r.get('jour'):
                continue
            st = (r.get('stats') or {}).get('ALL') or {}
            if not st:
                continue
            dh, da = FE.detail(st, 0), FE.detail(st, 2)
            if not dh or not da:
                continue
            vus.add(r.get('id'))
            s = surface_feuille(r.get('surface'))
            j = dt.date.fromisoformat(r['jour'])
            gh, ga = dh[2] + dh[3], da[2] + da[3]           # points gagnés au service (1re + 2e)
            L.append((j, (r.get('home') or {}).get('nom'), s, dh[0], gh, da[0], da[0] - ga))
            L.append((j, (r.get('away') or {}).get('nom'), s, da[0], ga, dh[0], dh[0] - gh))
        return cls(L, cle)

    def _somme(self, k, jour, surface, a, b):
        L = self.j.get(k) or []
        i = bisect.bisect_left(L, jour - dt.timedelta(days=b))
        f = bisect.bisect_left(L, jour - dt.timedelta(days=a))
        sp = sw = rp = rw = n = 0
        for x in self.m[k][i:f] if L else []:
            if x[1] == surface:
                sp, sw, rp, rw, n = sp + x[2], sw + x[3], rp + x[4], rw + x[5], n + 1
        return {'matchs': n, 'pts_service': sp, 'pts_retour': rp,
                'service': sw / sp if sp else None, 'retour': rw / rp if rp else None}

    def variables(self, k, jour, surface):
        """{récent, référence, d_service, d_retour, sens_service, sens_retour} ; None si le joueur n'a rien de récent."""
        if isinstance(jour, dt.datetime):
            jour = jour.date()
        if surface not in ('Hard', 'Clay', 'Grass'):
            return None
        r = self._somme(k, jour, surface, 0, RECENT_J)
        if not r['matchs']:
            return None
        b = self._somme(k, jour, surface, RECENT_J, REFERENCE_J)
        out = {'surface': surface, 'recent': _arrondi(r), 'reference': _arrondi(b)}
        for q, n_r, n_b in (('service', r['pts_service'], b['pts_service']), ('retour', r['pts_retour'], b['pts_retour'])):
            if r[q] is None or b[q] is None or n_b < MIN_REFERENCE:
                out['d_' + q], out['sens_' + q] = 0.0, None
                continue
            d = (_lg(r[q]) - _lg(b[q])) * n_r / (n_r + K)
            out['d_' + q] = round(max(-BORNE, min(BORNE, d)), 4)
            ecart = r[q] - b[q]
            out['sens_' + q] = (None if n_r < MIN_RECENT else 'hausse' if ecart >= SEUIL_PTS
                                else 'baisse' if ecart <= -SEUIL_PTS else 'stable')
        return out


def _arrondi(d):
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}


def decalages(vh, va):
    """(décalage du service de home, décalage du service de away) en logit : son service du moment moins le retour
    du moment de l'adversaire."""
    g = lambda v, q: (v or {}).get('d_' + q) or 0.0
    return g(vh, 'service') - g(va, 'retour'), g(va, 'service') - g(vh, 'retour')


if __name__ == '__main__':          # python simulateur/forme_service.py . "Nom 1" "Nom 2" [AAAA-MM-JJ] [Hard]
    sys.path.insert(0, ICI)
    racine = sys.argv[1]
    jour = dt.date.fromisoformat(sys.argv[4]) if len(sys.argv) > 4 else dt.date.today()
    s = sys.argv[5] if len(sys.argv) > 5 else 'Hard'
    import elo as E
    F = FormeService.depuis(racine)
    for n in sys.argv[2:4]:
        print(n, F.variables(E.cle(n), jour, s))
