#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""retournement_study.py — Peut-on prédire les moves qui s'inversent ?

PISTE GELÉE LE 2026-08-25. Les ~27 % de moves à CLV<=0 sont la perte
principale (ROI -1,7 % sur cette tranche). Prédicteurs candidats
pré-spécifiés, UNIVARIÉS (pas de modèle, pas de data mining) :
  ampleur du move (mag), avance sur le coup d'envoi (lead), circuit.
Un prédicteur n'est retenu que si le taux de retournement de son bucket
sort de l'IC95 du taux global, à n>=30.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pistes_common as pc


def buckets(moves, cle, bornes, labels):
    out = {lab: [] for lab in labels}
    for m in moves:
        v = m[cle]
        for (lo, hi), lab in zip(bornes, labels):
            if lo <= v < hi:
                out[lab].append(m)
                break
    return out


def main():
    pc.entete('PISTE 5 — PRÉDIRE LES RETOURNEMENTS (CLV<=0)')
    moves = pc.charge_moves()
    if len(moves) < 30:
        print('  trop tôt.')
        return
    inv = sum(1 for m in moves if m['clv'] <= 0)
    p, lo, hi = pc.wilson(inv, len(moves))
    print(f'  taux global de retournement : {100 * p:.1f}% '
          f'(IC95 {100 * lo:.1f}-{100 * hi:.1f}%, n={len(moves)})')
    grilles = [
        ('ampleur du move', 'mag',
         [(0, 3), (3, 6), (6, 12), (12, 999)],
         ['2-3%', '3-6%', '6-12%', '>12%']),
        ('avance sur le match', 'lead_min',
         [(0, 60), (60, 360), (360, 1440), (1440, 99999)],
         ['<1h', '1-6h', '6-24h', '>24h']),
    ]
    for titre, cle, bornes, labels in grilles:
        print(f'  — par {titre} —')
        for lab, sel in buckets(moves, cle, bornes, labels).items():
            if not sel:
                continue
            k = sum(1 for m in sel if m['clv'] <= 0)
            pb, lb, hb = pc.wilson(k, len(sel))
            # sort-il de l'IC global ?
            signal = '  <-- hors IC global' if (lb > hi or hb < lo) and len(sel) >= 30 else ''
            marque = ' [n<30]' if len(sel) < 30 else ''
            print(f'    {lab:8} n={len(sel):4} | retournés {100 * pb:.0f}% '
                  f'(IC {100 * lb:.0f}-{100 * hb:.0f}%){marque}{signal}')
    print('  — par circuit —')
    seg = {}
    for m in moves:
        seg.setdefault(pc.segment_circuit(m['tour']), []).append(m)
    for lab, sel in seg.items():
        k = sum(1 for m in sel if m['clv'] <= 0)
        pb, lb, hb = pc.wilson(k, len(sel))
        signal = '  <-- hors IC global' if (lb > hi or hb < lo) and len(sel) >= 30 else ''
        print(f'    {lab:11} n={len(sel):4} | retournés {100 * pb:.0f}% '
              f'(IC {100 * lb:.0f}-{100 * hb:.0f}%){signal}')


if __name__ == '__main__':
    main()
