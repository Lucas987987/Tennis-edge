#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_changement_surface.py — un joueur qui vient de changer de surface est-il moins fort que son Elo ?
(04/11/2026, demande de Lucas ; jugé SÉPARÉMENT sur l'ATP, la WTA et le Challenger)

Idée : l'Elo par surface ne voit pas le temps d'adaptation (passer de la terre au dur, du dur au gazon…).
Définition, calculée AVANT le match avec les seuls matchs déjà joués :
  « nouveau » = ce match est le 1er ou le 2e du joueur sur cette surface depuis qu'il en a changé, et son match
  précédent (autre surface) date de 45 jours au plus (au-delà, c'est un retour de pause, autre chose).
Variable : x = nouveau_A − nouveau_B (−1, 0 ou +1). Correction : z = logit p_elo + β·x.
Base : l'Elo du pronostic (elo.py, notes d'avant le jour du match), le modèle principal (~78 % du mélange). Aucune cote.

RÈGLE FIXÉE LE 04/11/2026, AVANT DE REGARDER LE RÉSULTAT, pour chaque circuit :
  β appris sur 2016–2022, jugé sur 2023 → 2026 (jamais vu) ;
  positif si, sur les matchs CONCERNÉS (x ≠ 0) jugés, au moins 300, la log loss du vainqueur baisse d'au moins 0,001
  ET le gain reste positif sur tous les matchs jugés du circuit.
  Positif → modèle fantôme « changement de surface » sur les nouveaux matchs de ce circuit, adopté seulement après deux
  semaines gagnantes (fantomes_circuits.py). Sinon : rien ne change.
Usage : python simulateur/etude_changement_surface.py /tmp/sackmann .
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

COUPURE = dt.date(2023, 1, 1)
DEBUT = dt.date(2016, 1, 1)
FENETRE_J, MATCHS_NOUVEAU = 45, 2
MIN_CONCERNES, MARGE = 300, 0.001
SORTIE = os.path.join(ICI, 'rapport_changement_surface.json')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def ll(z):                                  # vainqueur = joueur A
    return -math.log(min(max(_sg(z), 1e-9), 1 - 1e-9))


def apprendre_beta(R, ridge=1.0):
    b = 0.0
    for _ in range(40):
        g = h = 0.0
        for z, x in R:
            q = _sg(z + b * x)
            g += (q - 1) * x
            h += q * (1 - q) * x * x
        if h <= 0:
            break
        d = (g + ridge * b) / (h + ridge)
        b -= d
        if abs(d) < 1e-9:
            break
    return b


class Suivi:
    """Pour chaque joueur : surface et jour du dernier match, et rang du match dans la série sur cette surface."""
    def __init__(self):
        self.dern = {}                              # joueur → (jour, surface, rang dans la série, série = changement ?)

    def nouveau(self, j, jour, surface):
        d = self.dern.get(j)
        if not d:
            return 0
        jour0, s0, rang, apres_changement = d
        if s0 != surface:
            return int((jour - jour0).days <= FENETRE_J)               # 1er match sur la nouvelle surface
        return int(apres_changement and rang < MATCHS_NOUVEAU)          # 2e match de la série

    def jouer(self, j, jour, surface):
        d = self.dern.get(j)
        if d and d[1] == surface:
            self.dern[j] = (jour, surface, d[2] + 1, d[3])
        else:
            self.dern[j] = (jour, surface, 1, bool(d) and (jour - d[0]).days <= FENETRE_J)


def lignes(archive, racine):
    import donnees as DN
    import elo as E
    import feuilles as FE
    M = DN.charger(archive, 2012)
    fin = max(m['date'] for m in M)
    M = M + [m for m in FE.charger(racine) if m['date'] > fin]
    try:
        with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
            alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    M.sort(key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    el, su, jour, attente, rows = E.Elo(), Suivi(), None, [], []
    for m in M:
        d = m['date']
        if d != jour:
            for g, p, s, gc in attente:
                el.maj(g, p, s, gc, None)
            attente, jour = [], d
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m['surface']
        if c in ('CH', 'ITF'):
            el.presenter(g, 1200.0)
            el.presenter(p, 1200.0)
        x = su.nouveau(g, d, s) - su.nouveau(p, d, s)
        if (c in ('ATP', 'WTA', 'CH') and d >= DEBUT and not m.get('abandon')
                and el.matchs(g) >= 10 and el.matchs(p) >= 10):
            rows.append({'d': d, 'c': c, 'z': _lg(el.proba(g, p, s)), 'x': x})
        su.jouer(g, d, s)
        su.jouer(p, d, s)
        attente.append((g, p, s, m.get('niveau') == 'G'))
    return rows


def juger(rows):
    out = {}
    for c in ('ATP', 'WTA', 'CH'):
        R = [r for r in rows if r['c'] == c]
        av = [(r['z'], r['x']) for r in R if r['d'] < COUPURE]
        ju = [r for r in R if r['d'] >= COUPURE]
        b = apprendre_beta([t for t in av if t[1]])
        cc = [r for r in ju if r['x']]
        l0c = sum(ll(r['z']) for r in cc) / max(1, len(cc))
        l1c = sum(ll(r['z'] + b * r['x']) for r in cc) / max(1, len(cc))
        g_tout = sum(ll(r['z']) - ll(r['z'] + b * r['x']) for r in ju) / max(1, len(ju))
        # le « nouveau » gagne-t-il moins qu'annoncé ? (descriptif, matchs jugés concernés ; A = vainqueur)
        nouv = [(_sg(r['z']) if r['x'] > 0 else 1 - _sg(r['z']), 1 if r['x'] > 0 else 0) for r in cc]
        positif = len(cc) >= MIN_CONCERNES and (l0c - l1c) >= MARGE and g_tout > 0
        out[c] = {'appris_concernes': sum(1 for t in av if t[1]), 'juges': len(ju), 'juges_concernes': len(cc),
                  'part_concernes_pct': round(100 * len(cc) / max(1, len(ju)), 1), 'beta': round(b, 4),
                  'log_loss_concernes_sans': round(l0c, 5), 'log_loss_concernes_avec': round(l1c, 5),
                  'gain_concernes': round(l0c - l1c, 5), 'gain_tous': round(g_tout, 6), 'positif': bool(positif),
                  'nouveau_annonce_pct': round(100 * sum(a for a, _ in nouv) / max(1, len(nouv)), 1),
                  'nouveau_reel_pct': round(100 * sum(v for _, v in nouv) / max(1, len(nouv)), 1)}
    return out


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    rows = lignes(archive, racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'definition': (f"nouveau = 1er ou 2e match sur la surface depuis un changement, match précédent à "
                          f"{FENETRE_J} jours au plus"),
           'regle': ("β appris 2016–2022, jugé 2023 → ; positif si −0,001 de log loss sur ≥ 300 matchs concernés et gain "
                     "positif sur tous les matchs, par circuit"),
           'circuits': juger(rows)}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
