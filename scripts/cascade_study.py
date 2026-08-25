#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cascade_study.py — Dans quel ordre les books suivent-ils un move ?

PISTE GELÉE LE 2026-08-25. Pour chaque alerte : délai, par book soft, avant
que SON prix du côté steamé ait parcouru >=50 % de l'amplitude de l'alerte
(par rapport à son propre prix à T0). Classement des books par délai médian.
Hypothèse pré-spécifiée (à geler en H si stable) : les retardataires
systématiques offrent un CLV supérieur — la sélection dynamique du book
d'entrée devient alors un paramètre du dispositif. n>=10 alertes par book
pour figurer au classement.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datetime
import statistics as st
import pistes_common as pc
from decay_study import charge_alertes, cle_match, SOFTS_EXCLUS


def main():
    pc.entete('PISTE 4 — LA CASCADE DES BOOKS')
    alertes = charge_alertes()
    cles = {a['cle'] for a in alertes}
    courbes = {}
    for r in pc.iter_hist('book'):
        c = cle_match(r.get('home'), r.get('away'), r.get('commence_time'))
        if c in cles and r.get('book') not in SOFTS_EXCLUS:
            courbes.setdefault(c, {})[r['book']] = r
    delais = {}
    for a in alertes:
        bks = courbes.get(a['cle']) or {}
        try:
            t0 = datetime.datetime.fromisoformat(pc.ts_norm(a['ts']))
        except ValueError:
            continue
        for book, r in bks.items():
            cle = f"{a['side']}_curve"
            curve = r.get(cle) or []
            ct = pc.ts_norm(r.get('commence_time'))
            v0 = pc.val_at(curve, t0.isoformat(), r.get('commence_time'))
            close = pc.closing_prematch(curve, r.get('commence_time'))
            if not v0 or not close or v0 <= close:
                continue                    # move baissier attendu côté steamé
            cible = v0 - 0.5 * (v0 - close)
            atteint = None
            for pt in curve:
                t = pc.ts_norm(pt[0])
                if t <= t0.isoformat()[:19] or t > ct:
                    continue
                try:
                    if float(pt[1]) <= cible:
                        atteint = t
                        break
                except (TypeError, ValueError):
                    continue
            if atteint:
                dt = (datetime.datetime.fromisoformat(atteint)
                      - t0).total_seconds() / 60
                delais.setdefault(book, []).append(max(dt, 0.0))
    lignes = [(book, st.median(v), len(v)) for book, v in delais.items()
              if len(v) >= 10]
    if not lignes:
        print('  trop tôt : aucun book avec >=10 alertes mesurables.')
        return
    lignes.sort(key=lambda x: x[1])
    print(f'  délai médian pour parcourir 50 % du move (n>=10 alertes) :')
    for book, med, n in lignes:
        print(f'    {book:14} {med:6.0f} min (n={n})')
    print('  Lecture : le bas du classement = les books où le CLV vit le plus')
    print('  longtemps. Stabilité à vérifier avant tout gel en hypothèse.')


if __name__ == '__main__':
    main()
