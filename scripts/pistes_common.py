#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pistes_common.py — socle partagé des études de pistes (gel 2026-08-25).

Conventions non négociables, héritées des leçons du projet :
- AUCUN point in-play : toute valeur est coupée à commence_time (le look-ahead
  a déjà coûté 6 corrections) ;
- Wilson pour tout intervalle, refus de conclure sous n=30 ;
- le témoin est le taux de base de la POPULATION concernée, jamais 50 % ;
- une lecture vide s'annonce à voix haute, jamais en silence.
"""
import glob
import gzip
import json
import math
import os


def wilson(k, n, z=1.96):
    if n <= 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p, (c - m) / d, (c + m) / d


def _ouvrir(path):
    if path.endswith('.gz'):
        return gzip.open(path, 'rt', encoding='utf-8', errors='replace')
    return open(path, encoding='utf-8', errors='replace')


def iter_hist(market='book'):
    """Itère les lignes (match×book) des partitions hist, gz inclus."""
    fichiers = sorted(glob.glob(f'parts/hist_{market}_*.jsonl')
                      + glob.glob(f'parts/hist_{market}_*.jsonl.gz'))
    if not fichiers:
        print(f"⚠️ iter_hist('{market}') : aucune partition — étude vide.")
    for f in fichiers:
        with _ouvrir(f) as fh:
            for ligne in fh:
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    yield json.loads(ligne)
                except json.JSONDecodeError:
                    continue


def courbes_par_uid(book, market='book'):
    """{uid: enregistrement} pour UN book ; en cas de doublon, garde la
    dernière version lue (la plus proche du closing réel)."""
    out = {}
    for r in iter_hist(market):
        if r.get('book') == book and r.get('uid'):
            out[r['uid']] = r
    return out


def ts_norm(t):
    return str(t or '').replace('Z', '')[:19]


def val_at(curve, ts, commence=None, champ=1):
    """Dernière valeur du champ (1=cote, 2=limite) AVANT ts, et jamais après
    commence_time. Renvoie None si rien d'antérieur — le silence interdit,
    c'est l'appelant qui décide quoi en dire."""
    coupure = ts_norm(ts)
    fin = ts_norm(commence) if commence else '9999'
    coupure = min(coupure, fin)
    out = None
    for pt in curve or []:
        t = ts_norm(pt[0])
        if t > coupure:
            break
        try:
            v = float(pt[champ])
            if champ != 1 or v > 1:
                out = v
        except (TypeError, ValueError, IndexError):
            continue
    return out


def closing_prematch(curve, commence):
    return val_at(curve, '9999', commence, champ=1)


def charge_moves():
    """moves_detail_hist.csv -> liste de dicts typés (CLV, lead, mag...)."""
    import csv
    out = []
    if not os.path.exists('moves_detail_hist.csv'):
        print('⚠️ moves_detail_hist.csv absent — études sur moves vides.')
        return out
    for r in csv.DictReader(open('moves_detail_hist.csv', encoding='utf-8')):
        try:
            out.append({
                'uid': r['uid'], 'tour': r.get('tour', ''),
                'date': r.get('date', ''),
                'mag': float(r['mag_cote_pct']),
                'lead_min': float(r['lead_min']),
                'clv': float(r['clv_book_pct']),
                'entry_book': r.get('entry_book', ''),
            })
        except (TypeError, ValueError, KeyError):
            continue
    return out


def segment_circuit(tour):
    t = tour or ''
    if 'Challenger' in t or t.startswith('CH'):
        return 'Challenger'
    if 'WTA' in t:
        return 'WTA'
    if 'ATP' in t:
        return 'ATP'
    return 'autre'


def temoin(moves):
    """(p0, n) : taux de base CLV>0 de la population passée en argument —
    l'étalon se calcule sur LA population étudiée (leçon du seuil adaptatif)."""
    n = len(moves)
    if not n:
        return 0.5, 0
    return sum(1 for m in moves if m['clv'] > 0) / n, n


def entete(titre, gel='2026-08-25'):
    print('=' * 62)
    print(f'{titre}')
    print(f'(exploratoire, protocole gelé le {gel} — voir frozen_pistes.json ;')
    print(' n<30 = suivi sans conclusion ; témoin = population concernée)')
    print('=' * 62)
