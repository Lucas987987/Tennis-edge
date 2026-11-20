#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""limites_study.py — La limite Pinnacle au moment du move prédit-elle le CLV ?

PISTE GELÉE LE 2026-08-25. La donnée dormait dans les courbes depuis le début
(3e champ de chaque point). Hypothèses pré-spécifiées :
  H1a : un move survenant à limite BASSE (tercile inférieur du jour) referme
        plus souvent que le témoin (info précoce, le book n'ose pas encore).
  H1b : la limite MONTE entre le move et le closing (le prix mûrit) — mesure
        descriptive de la fenêtre.
Test : binomial exact vs témoin de LA population appariée, n>=30 par tercile.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datetime
import statistics as st
import pistes_common as pc


def main():
    pc.entete('PISTE 1 — LIMITES PINNACLE AU MOMENT DU MOVE')
    pin = pc.courbes_par_uid('pinnacle')
    moves = pc.charge_moves()
    lignes = []
    for m in moves:
        r = pin.get(m['uid'])
        if not r:
            continue
        ct = r.get('commence_time')
        # instant du move : commence_time - lead_min
        try:
            t0 = datetime.datetime.fromisoformat(pc.ts_norm(ct))
            t_move = (t0 - datetime.timedelta(minutes=m['lead_min'])).isoformat()
        except ValueError:
            continue
        lim_move = pc.val_at(r.get('home_curve'), t_move, ct, champ=2)
        lim_close = pc.val_at(r.get('home_curve'), '9999', ct, champ=2)
        if lim_move:
            lignes.append({'clv': m['clv'], 'lim': lim_move,
                           'lim_close': lim_close})
    if len(lignes) < 30:
        print(f'  n={len(lignes)} moves appariés à une limite — trop tôt (<30).')
        return
    p0, nt = pc.temoin([{'clv': x['clv']} for x in lignes])
    print(f'  {len(lignes)} moves appariés | témoin population appariée : '
          f'{100 * p0:.1f}% de CLV>0')
    limites = sorted(x['lim'] for x in lignes)
    t1 = limites[len(limites) // 3]
    t2 = limites[2 * len(limites) // 3]
    print(f'  terciles de limite : basse <= {t1:.0f} < moyenne <= {t2:.0f} < haute')
    for lab, sel in (('limite basse', [x for x in lignes if x['lim'] <= t1]),
                     ('limite moyenne', [x for x in lignes if t1 < x['lim'] <= t2]),
                     ('limite haute', [x for x in lignes if x['lim'] > t2])):
        k = sum(1 for x in sel if x['clv'] > 0)
        p, lo, hi = pc.wilson(k, len(sel))
        marque = ' [n<30]' if len(sel) < 30 else ''
        print(f'    {lab:15} n={len(sel):3} | CLV>0 : {100 * p:.0f}% '
              f'(IC95 {100 * lo:.0f}-{100 * hi:.0f}%) | CLV méd '
              f'{st.median(x["clv"] for x in sel):+.1f}%{marque}')
    montees = [x['lim_close'] / x['lim'] for x in lignes
               if x['lim_close'] and x['lim'] > 0]
    if montees:
        print(f'  H1b (descriptif) : limite closing / limite move — médiane '
              f'x{st.median(montees):.2f} sur n={len(montees)}')


if __name__ == '__main__':
    main()
