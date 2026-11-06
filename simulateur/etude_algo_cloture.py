#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_algo_cloture.py — l'algo apporte-t-il une information que la clôture Pinnacle n'a pas ? (06/11/2026, demande de
Lucas, « bilan algo contre clôture »). ÉTUDE PRIVÉE : rien ne change dans l'algo, aucune cote n'entre dans le calcul.

Données : pronostics hors échantillon (p_algo) reliés à la ligne Pinnacle du même match (suivi_desaccords_pinnacle.relier :
ouverture po, clôture pc, marge retirée).

RÈGLE FIXÉE LE 06/11/2026, AVANT DE REGARDER LE RÉSULTAT, circuit par circuit :
  modèle « clôture + algo » : logit p = logit pc + β · (logit p_algo − logit pc) ;
  β appris sur les matchs d'avant le 1er octobre 2026, jugé sur ceux d'après ;
  l'algo AJOUTE de l'information si la log loss jugée baisse d'au moins 0,001 contre la clôture seule, sur au moins
  300 matchs jugés, ET β > 0 sur les deux périodes.
Aussi, pour information : log loss de l'algo seul et de la clôture seule ; part des matchs où Pinnacle s'est déplacé
vers l'algo entre ouverture et clôture (approche de la CLV : la clôture plus proche de l'algo que l'ouverture), selon l'écart à la clôture.
Usage : python simulateur/etude_algo_cloture.py [racine] [--telegram] — rapport HORS du dépôt (ALGO_CLOTURE_SORTIE),
résumé sur le Telegram privé : la comparaison au marché reste une loupe privée.
"""
import datetime as dt
import gzip
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
COUPURE = '2026-10-01'
MIN_JUGES, MARGE = 300, 0.001
CIRCUITS = ('ATP', 'WTA', 'CH')
SORTIE = os.path.join(__import__('tempfile').gettempdir(), 'rapport_algo_cloture.json')   # hors du dépôt : canal privé


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-z))


def ll(R, b=None):
    t = 0.0
    for r in R:
        p = r['pa'] if b == 'algo' else _sg(_lg(r['pc']) + (b or 0.0) * (_lg(r['pa']) - _lg(r['pc'])))
        p = min(max(p, 1e-6), 1 - 1e-6)
        t -= math.log(p if r['y'] else 1 - p)
    return t / max(1, len(R))


def apprendre(R):
    b = 0.0
    for _ in range(50):
        g = h = 0.0
        for r in R:
            x = _lg(r['pa']) - _lg(r['pc'])
            p = _sg(_lg(r['pc']) + b * x)
            g += (r['y'] - p) * x
            h += p * (1 - p) * x * x
        if h <= 0:
            break
        s = g / h
        b += s
        if abs(s) < 1e-9:
            break
    return b


def juger(rows):
    out = {}
    for c in CIRCUITS:
        R = [r for r in rows if r['c'] == c and r.get('pc') and r.get('pa') is not None]
        av, ju = [r for r in R if r['jour'] < COUPURE], [r for r in R if r['jour'] >= COUPURE]
        if len(av) < 100 or not ju:
            out[c] = {'matchs': len(R), 'note': 'trop peu de matchs'}
            continue
        b1, b2 = apprendre(av), apprendre(ju)
        l0, l1 = ll(ju), ll(ju, b1)
        vers = {}
        for nom, lo, hi in (('0-3', 0, .03), ('3-6', .03, .06), ('6-10', .06, .10), ('10+', .10, 1.01)):
            T = [r for r in R if lo <= abs(r['pa'] - r['pc']) < hi and r.get('po')]
            # vers l'algo = la clôture est plus proche de l'algo que l'ouverture ne l'était
            mv = [abs(r['pa'] - r['po']) - abs(r['pa'] - r['pc']) for r in T if abs(r['pc'] - r['po']) > 1e-9]
            vers[nom] = {'matchs': len(T), 'vers_algo_pct': round(100 * sum(m > 0 for m in mv) / len(mv), 1) if mv else None}
        out[c] = {'matchs': {'avant_octobre': len(av), 'juges': len(ju)},
                  'log_loss_juges': {'cloture_seule': round(l0, 5), 'algo_seul': round(ll(ju, 'algo'), 5),
                                     'cloture_plus_algo': round(l1, 5)},
                  'beta_avant': round(b1, 3), 'beta_juges': round(b2, 3), 'gain': round(l0 - l1, 5),
                  'algo_ajoute_information': bool(len(ju) >= MIN_JUGES and l0 - l1 >= MARGE and b1 > 0 and b2 > 0),
                  'pinnacle_bouge_vers_algo': vers}
    return out


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    racine = args[0] if args else os.path.join(ICI, '..')
    import elo as E
    import feuilles as FE
    import closing_store as CS
    import suivi_desaccords_pinnacle as SD
    with gzip.open(os.path.join(racine, 'simulateur', 'pronostics_hors_echantillon.jsonl.gz'), 'rt', encoding='utf-8') as f:
        pronos = [json.loads(l) for l in f if l.strip()]
    closing = CS.load_all(os.path.join(racine, 'closing_lines.json'), max_age_days=None)
    rows = SD.relier(pronos, FE.lire(racine), closing, E.cle)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("par circuit : logit p = logit clôture + β·(logit algo − logit clôture), β appris avant le 01/10/2026 ; "
                     "l'algo ajoute de l'information si −0,001 de log loss sur ≥ 300 matchs jugés et β > 0 sur les deux périodes"),
           'matchs_relies': len(rows), 'circuits': juger(rows)}
    with open(os.environ.get('ALGO_CLOTURE_SORTIE') or SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    txt = message(doc)
    print(txt)
    if '--telegram' in argv:
        import urllib.parse
        import urllib.request
        tok, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
        if tok and chat:
            try:
                data = urllib.parse.urlencode({'chat_id': chat, 'text': txt}).encode()
                urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/sendMessage', data=data, timeout=20).read()
            except Exception as e:  # noqa: BLE001
                print(f'::warning::Telegram impossible ({type(e).__name__})')
    return 0


def message(doc):
    L = [f"Algo contre clôture Pinnacle (règle fixée le 06/11, privé) · {doc['matchs_relies']} matchs"]
    for c, b in doc['circuits'].items():
        if 'log_loss_juges' not in b:
            L.append(f"{c} : {b.get('note')}")
            continue
        v = b['pinnacle_bouge_vers_algo']
        L.append(f"{c} : {'AJOUTE de l’information' if b['algo_ajoute_information'] else 'n’ajoute rien'} "
                 f"(gain {b['gain']:+.4f}, β {b['beta_avant']} puis {b['beta_juges']}, {b['matchs']['juges']} jugés) · "
                 f"clôture vers l'algo : 0-3 {v['0-3']['vers_algo_pct']} %, 10+ {v['10+']['vers_algo_pct']} %")
    return '\n'.join(L)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
