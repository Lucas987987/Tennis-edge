#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cross_market_study.py — Le steam ML se propage-t-il aux marchés de sets ?

PISTE GELÉE LE 2026-08-25. Pour chaque alerte ML : mouvement du côté steamé
sur le marché SET1 dans les 60 min suivant l'alerte, comparé à une fenêtre
témoin du MÊME match (60 min se terminant 2 h avant l'alerte). Hypothèse
pré-spécifiée : le set1 bouge dans le même sens, avec retard — un deuxième
terrain de chasse moins liquide. Verdict binomial (fenêtre alerte plus
baissière que fenêtre témoin) vs 50 % — ici 50 % est le BON étalon : les
deux fenêtres viennent du même match, l'asymétrie de population s'annule.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datetime
import pistes_common as pc
from decay_study import charge_alertes, cle_match


def variation(curve, t0, minutes, commence):
    v0 = pc.val_at(curve, t0.isoformat(), commence)
    v1 = pc.val_at(curve, (t0 + datetime.timedelta(minutes=minutes)).isoformat(),
                   commence)
    if not v0 or not v1:
        return None
    return (v1 / v0 - 1) * 100


def main():
    pc.entete('PISTE 6 — PROPAGATION ML -> MARCHÉ SET1')
    alertes = charge_alertes()
    cles = {a['cle'] for a in alertes}
    set1 = {}
    for r in pc.iter_hist('set1'):
        c = cle_match(r.get('home'), r.get('away'), r.get('commence_time'))
        if c in cles:
            set1.setdefault(c, []).append(r)
    paires = []
    for a in alertes:
        try:
            t0 = datetime.datetime.fromisoformat(pc.ts_norm(a['ts']))
        except ValueError:
            continue
        for r in set1.get(a['cle']) or []:
            cle = f"{a['side']}_curve"
            ct = r.get('commence_time')
            v_alerte = variation(r.get(cle), t0, 60, ct)
            v_temoin = variation(r.get(cle),
                                 t0 - datetime.timedelta(hours=3), 60, ct)
            if v_alerte is not None and v_temoin is not None:
                paires.append((v_alerte, v_temoin))
    n = len(paires)
    print(f'  {n} paires (fenêtre alerte / fenêtre témoin même match, set1)')
    if n < 30:
        print('  TROP TÔT (<30 paires) — protocole gelé, relance hebdomadaire.')
        return
    k = sum(1 for va, vt in paires if va < vt)
    p, lo, hi = pc.wilson(k, n)
    print(f'  fenêtre alerte plus baissière que sa fenêtre témoin : '
          f'{k}/{n} = {100 * p:.0f}% (IC95 {100 * lo:.0f}-{100 * hi:.0f}%)')
    print('  IC95 entièrement > 50 % ET n>=30 -> propagation confirmée, à')
    print('  geler alors en hypothèse de la famille principale.')
    if hi < 0.5:
        print('  ⚠️ RÉSULTAT INVERSE — lire avec le CONFONDEUR en tête : la')
        print('  fenêtre témoin est plus loin du coup d\'envoi que la fenêtre')
        print("  alerte, or dérive et volatilité varient avec l'approche du")
        print('  match. Avant toute conclusion, protocole v2 : témoin apparié')
        print('  à la MÊME distance du match, sur des matchs SANS alerte.')


if __name__ == '__main__':
    main()
