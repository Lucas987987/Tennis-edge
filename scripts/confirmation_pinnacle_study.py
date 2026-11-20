#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""confirmation_pinnacle_study.py — Pinnacle confirme-t-elle le signal
d'ouverture précoce (hypothèse gelée #6, 13/08) ?

PISTE GELÉE LE 2026-08-26, PROTOCOLE FIGÉ AVANT VERDICT.

Contexte : un exploratoire rapide ce soir sur les 62 signaux existants
(early_open_log.jsonl) donnait CLV comparable et 100% de refermeture dans
les deux groupes — mais sur seulement 29 signaux appariés, avec un taux de
refermeture (100%) trop net pour être crédible : signe d'un sous-échantillon
biaisé (seuls les cas les plus faciles à apparier), pas un verdict. D'où ce
protocole écrit AVANT toute nouvelle mesure, à juger sur les données qui
arriveront APRÈS ce gel.

HYPOTHÈSE : parmi les signaux d'ouverture précoce (book ouvert avant
Pinnacle, écart >=5%), ceux où Pinnacle elle-même continue de bouger dans le
MÊME SENS dans l'heure suivant son apparition (t_pin) ont un CLV/taux de
refermeture supérieur à ceux où Pinnacle est stable ou repart en sens
inverse. Logique : Pinnacle qui persiste dans la direction du book précoce
est une confirmation indépendante ; Pinnacle qui s'arrête ou s'inverse
suggère que le book précoce était simplement mal calé, sans rapport avec une
info réelle.

TEST : fenêtre de confirmation FIXE à 60 min après t_pin (pas la fermeture
entière — évite de mélanger "confirme tôt" et "finit par converger", qui
sont deux histoires différentes). confirme = prix Pinnacle à t_pin+60min a
bougé d'au moins 0,5 pt de probabilité implicite dans le sens du signal.
Comparaison des deux groupes en CLV (Wilson sur refermeture), n>=30 par
groupe avant tout verdict — sinon affichage de l'avancement seulement.
Le signal in-sample (81% refermeture, CLV +8,6%, n=144) reste la référence
descriptive, jamais le verdict.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datetime
import statistics as st
import pistes_common as pc

FENETRE_MIN = 60
SEUIL_CONFIRME_PTS = 0.5   # en points de probabilité implicite (1/cote)


def charge_pinnacle_et_book(uids_books):
    """uids_books = {uid: book} -> ({uid: enreg_pinnacle}, {uid: enreg_book})."""
    uids = set(uids_books)
    pin, bk = {}, {}
    for r in pc.iter_hist('book'):
        u = r.get('uid')
        if u not in uids:
            continue
        if r.get('book') == 'pinnacle':
            pin[u] = r
        elif r.get('book') == uids_books.get(u):
            bk[u] = r
    return pin, bk


def main():
    pc.entete('CONFIRMATION PINNACLE — hypothèse ouverture précoce', gel='2026-08-26')
    if not os.path.exists('early_open_log.jsonl'):
        print('  early_open_log.jsonl absent — rien à mesurer.')
        return
    signaux = [__import__('json').loads(l) for l in open('early_open_log.jsonl',
               encoding='utf-8') if l.strip()]
    signaux = [m for m in signaux if m.get('t') and
              m['t'][:10] > '2026-08-26']     # STRICTEMENT postérieur au gel
    print(f'  {len(signaux)} signaux POSTÉRIEURS au gel (les 62 signaux du '
          f'13-26/08 ayant servi à formuler le protocole sont exclus).')
    if not signaux:
        print('  rien encore — relance après le prochain cycle early_open_signal.')
        return
    uids_books = {m['uid']: m['book'] for m in signaux}
    pin_par_uid, bk_par_uid = charge_pinnacle_et_book(uids_books)
    lignes = []
    for m in signaux:
        r_pin, r_bk = pin_par_uid.get(m['uid']), bk_par_uid.get(m['uid'])
        if not r_pin or not r_bk:
            continue
        cle = f"{m['side']}_curve"
        ct = r_pin.get('commence_time')
        try:
            t0 = datetime.datetime.fromisoformat(pc.ts_norm(m['t_pin']))
        except ValueError:
            continue
        t60 = (t0 + datetime.timedelta(minutes=FENETRE_MIN)).isoformat()
        p0 = pc.val_at(r_pin.get(cle), m['t_pin'], ct)
        p60 = pc.val_at(r_pin.get(cle), t60, ct)
        p_close = pc.val_at(r_bk.get(cle), '9999', r_bk.get('commence_time'))
        if not (p0 and p60 and p_close):
            continue
        # sens du signal : le book précoce cotait DESSOUS le fair Pinnacle
        # (price < fair) -> Pinnacle "devrait" baisser pour confirmer
        sens_attendu = -1 if m['price'] < m['fair'] else 1
        delta_proba = (1 / p60 - 1 / p0) * 100      # en points de proba implicite
        confirme = (delta_proba * sens_attendu) >= SEUIL_CONFIRME_PTS
        clv = (m['price'] / p_close - 1) * 100
        lignes.append({'clv': clv, 'confirme': confirme})
    print(f'  {len(lignes)} signaux appariés (Pinnacle + book, fenêtre {FENETRE_MIN}min)')
    for lab, sel in (('Pinnacle CONFIRME (>= %.1fpt en %dmin)' % (SEUIL_CONFIRME_PTS, FENETRE_MIN),
                      [x for x in lignes if x['confirme']]),
                     ('Pinnacle ne confirme pas', [x for x in lignes if not x['confirme']])):
        if len(sel) < 30:
            print(f'    {lab:42} n={len(sel):3} — sous 30, suivi sans verdict')
            continue
        pos = sum(1 for x in sel if x['clv'] > 0)
        p, lo, hi = pc.wilson(pos, len(sel))
        print(f'    {lab:42} n={len(sel):3} | CLV médian '
              f'{st.median(x["clv"] for x in sel):+6.1f}% | refermeture '
              f'{100*p:.0f}% (IC95 {100*lo:.0f}-{100*hi:.0f}%)')
    print('  Verdict : IC95 disjoints ET n>=30 des deux côtés -> promouvoir en')
    print('  hypothèse gelée de la famille Holm avec sa propre FREEZE_DATE.')


if __name__ == '__main__':
    main()
