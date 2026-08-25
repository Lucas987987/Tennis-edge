#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""segments_study.py — Le taux de refermeture diffère-t-il par circuit ?

PISTE GELÉE LE 2026-08-25. Hypothèse pré-spécifiée : les circuits
périphériques (Challengers) sont moins efficients -> refermeture ET CLV
supérieurs au témoin GLOBAL. Chaque segment est affiché avec SON Wilson ;
verdict par segment quand n>=30. Le témoin par segment servira d'étalon aux
futures hypothèses contextuelles (leçon du seuil adaptatif).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import statistics as st
import pistes_common as pc


def main():
    pc.entete('PISTE 7 — SEGMENTATION PAR CIRCUIT')
    moves = pc.charge_moves()
    p0, nt = pc.temoin(moves)
    print(f'  témoin global : {100 * p0:.1f}% de CLV>0 (n={nt})')
    seg = {}
    for m in moves:
        seg.setdefault(pc.segment_circuit(m['tour']), []).append(m)
    for lab in ('ATP', 'WTA', 'Challenger', 'autre'):
        sel = seg.get(lab, [])
        if not sel:
            continue
        k = sum(1 for m in sel if m['clv'] > 0)
        p, lo, hi = pc.wilson(k, len(sel))
        marque = ' [n<30 : suivi]' if len(sel) < 30 else ''
        print(f'    {lab:11} n={len(sel):4} | CLV>0 : {100 * p:.0f}% '
              f'(IC95 {100 * lo:.0f}-{100 * hi:.0f}%) | CLV méd '
              f'{st.median(m["clv"] for m in sel):+.1f}%{marque}')
    print('  Lecture : un segment ne devient hypothèse gelée que si son IC95')
    print('  se sépare du témoin global avec n>=30.')


if __name__ == '__main__':
    main()
