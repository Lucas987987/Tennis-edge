#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""shadow_sizing_study.py — La note de fiabilité mérite-t-elle de sizer une
mise un jour ? (créée le 26/08/2026, PROTOCOLE GELÉ AVANT VERDICT)

CE QUE CE SCRIPT NE FAIT PAS : il ne change AUCUNE mise réelle. Le ROI
officiel du projet reste, pour toujours, calculé à mise plate (1 unité) —
c'est l'instrument de mesure de l'edge, pas une simplification. Ici on
mesure seulement, en PARALLÈLE et à titre EXPLORATOIRE, ce qu'aurait donné
une mise variable pilotée par fiabilite_score.py, SI on l'avait appliquée.

POURQUOI CE N'EST PAS ENCORE UNE DÉCISION : la note combine des pistes
elles-mêmes non confirmées (ampleur, timing — piste 5, gelée hier, encore
in-sample sur son propre protocole). Une mise variable calée sur des
signaux non prouvés peut sembler améliorer le ROI simplement parce qu'elle
sur-mise sur les paris qui, par chance, ont bien tourné dans l'historique —
la version composée du surapprentissage. D'où : verdict UNIQUEMENT sur les
paris ouverts APRÈS ce gel (score déjà journalisé par paper_journal.py),
jamais sur l'historique qui a servi à concevoir la note.

RÈGLE DE MISE TESTÉE (pré-spécifiée, simple, pas ajustée) :
  score <= -2  -> mise 0,5u   (fiabilité faible)
  score en -1..+1 -> mise 1u  (neutre = mise plate actuelle)
  score >= +2  -> mise 1,5u   (fiabilité haute)
Verdict : ROI à mise variable significativement différent du ROI à mise
plate (comparaison des IC95, n>=30 côté SETTLED avec score renseigné)
-> alors seulement, envisager un changement de politique de mise réelle,
avec sa propre décision et sa propre date.
"""
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pistes_common as pc

GEL = '2026-08-26'
REGLE = ((-3, -2, 0.5), (-1, 1, 1.0), (2, 3, 1.5))


def mise_pour(score):
    for lo, hi, m in REGLE:
        if lo <= score <= hi:
            return m
    return 1.0


def main():
    pc.entete('SIZING OMBRE — la note de fiabilité mérite-t-elle une mise ?',
             gel=GEL)
    trades = []
    for market in ('match', 'set1', 'set2'):
        f = f'paper_trades_{market}.jsonl'
        if not os.path.exists(f):
            continue
        for l in open(f, encoding='utf-8'):
            try:
                t = json.loads(l)
            except json.JSONDecodeError:
                continue
            trades.append(t)
    # POSTÉRIEUR au gel uniquement : le score n'existe que depuis ce gel,
    # donc ce filtre est automatique -- mais on le rend explicite.
    settled = [t for t in trades if t.get('status') == 'SETTLED'
              and t.get('fiabilite_score') is not None and 'pnl' in t]
    print(f'  {len(settled)} paris dénoués avec note de fiabilité (score '
          f'journalisé depuis le {GEL}).')
    if len(settled) < 30:
        print('  TROP TÔT (<30) — aucun verdict. La note continue de se '
              'journaliser à chaque pari sans rien piloter.')
        return
    plat = [t['pnl'] for t in settled]
    var = [t['pnl'] * mise_pour(t['fiabilite_score']) for t in settled]
    def stats(vals, n):
        roi = sum(vals) / n
        sd = st.pstdev(vals)
        ic = 1.96 * sd / (n ** 0.5) if n > 1 else 0
        return roi, ic
    r1, ic1 = stats(plat, len(settled))
    r2, ic2 = stats(var, len(settled))
    print(f'  Mise plate (référence) : ROI {100*r1:+.1f}% '
          f'[IC95 {100*(r1-ic1):+.1f}, {100*(r1+ic1):+.1f}]')
    print(f'  Mise variable (note)   : ROI {100*r2:+.1f}% '
          f'[IC95 {100*(r2-ic2):+.1f}, {100*(r2+ic2):+.1f}]')
    par_score = {}
    for t in settled:
        par_score.setdefault(t['fiabilite_score'], []).append(t['pnl'])
    print('  Détail par note :')
    for s in sorted(par_score):
        v = par_score[s]
        print(f'    score {s:+d} : n={len(v):3} | ROI {100*sum(v)/len(v):+6.1f}%')
    if (r2 - ic2) > (r1 + ic1) or (r1 - ic1) > (r2 + ic2):
        print('  IC95 disjoints -> écart réel entre les deux politiques : '
              'matière à décision de mise, séparément et datée.')
    else:
        print('  IC95 recouvrants -> pas encore de différence démontrée. '
              'La mise plate reste la référence.')


if __name__ == '__main__':
    main()
