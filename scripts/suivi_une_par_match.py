#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
suivi_une_par_match.py — LECTURE GELÉE « UNE POSITION PAR MATCH » DES JOURNAUX DE SUIVI (20/11/2026, paquet 307,
décision de Lucas).

Pourquoi : le 20/11, une fois les positions en double retirées (paquet 306), le journal match lu à une position par
match donnait ROI +44,1 % (IC 95 % +7,7 ; +83,7) et CLV médiane +6,7 % sur 75 matchs. Mais cette lecture a été choisie
APRÈS avoir regardé (trois façons de compter, la meilleure retenue) et porte surtout sur des matchs déjà vus en octobre.
Elle ne peut donc être jugée que sur des matchs NEUFS.

RÈGLE ÉCRITE LE 20/11/2026 À 15 h 30 UTC, AVANT TOUT MATCH JUGÉ (ne pas la modifier après coup) :
  - matchs jugés : ceux dont l'horaire annoncé est postérieur au gel (GEL ci-dessous), positions réglées (SETTLED),
    journal par journal (match, set 1), sans les DOUBLON ;
  - une position par match : la PREMIÈRE ouverte (ordre du journal), quel que soit le book ;
  - la CLV contre la clôture de référence est la SEULE validation : « CLV positive » si la borne basse de l'IC 95 % de
    la CLV médiane (rééchantillonnage par match, 4 000 tirages, graine fixe) est au-dessus de 0 ;
  - le ROI (1 unité par position) est publié avec son IC 95 %, à titre descriptif : il ne décide rien ;
  - rien n'est conclu avant 30 matchs jugés dans un journal ; aucun conseil de mise.
Sorties : un message sur le Telegram PRIVÉ (bilan hebdomadaire, workflow « Suivi — une position par match ») et la
sortie du job ; rien n'est publié dans le dépôt (la comparaison aux clôtures reste privée).
Usage : python scripts/suivi_une_par_match.py [racine] [--telegram]
"""
import datetime as dt
import json
import os
import random
import statistics as st
import sys
import urllib.parse
import urllib.request

GEL = dt.datetime(2026, 11, 20, 15, 30, tzinfo=dt.timezone.utc)
MIN_MATCHS, TIRAGES, GRAINE = 30, 4000, 20261120
JOURNAUX = (('match', 'paper_trades_match.jsonl'), ('set 1', 'paper_trades_set1.jsonl'))


def instant(v):
    if isinstance(v, (int, float)):
        return float(v)
    try:
        d = dt.datetime.fromisoformat(str(v).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return (d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)).timestamp()


def premieres(chemin, gel=GEL):
    """La première position ouverte de chaque match postérieur au gel, si elle est réglée."""
    vus, out = set(), []
    try:
        lignes = open(chemin, encoding='utf-8').read().splitlines()
    except OSError:
        return out
    for ligne in lignes:
        if not ligne.strip():
            continue
        try:
            t = json.loads(ligne)
        except ValueError:
            continue
        if t.get('status') == 'DOUBLON' or not t.get('uid'):
            continue
        ti = instant(t.get('commence'))
        if ti is None or ti <= gel.timestamp():
            continue
        if t['uid'] in vus:
            continue
        vus.add(t['uid'])                       # la première ouverte, même si elle n'est pas encore réglée
        if t.get('status') == 'SETTLED' and t.get('pnl') is not None:
            out.append(t)
    return out


def ic(valeurs, f, tirages=TIRAGES, graine=GRAINE):
    r = random.Random(graine)
    n = len(valeurs)
    s = sorted(f([valeurs[r.randrange(n)] for _ in range(n)]) for _ in range(tirages))
    return s[int(0.025 * tirages)], s[int(0.975 * tirages) - 1]


def bilan(T):
    n = len(T)
    if not n:
        return {'matchs': 0, 'verdict': f'aucun match jugé depuis le gel ({GEL:%d/%m %H:%M} UTC)'}
    pnl = [float(t['pnl']) for t in T]
    clv = [float(t['clv_pin']) for t in T if t.get('clv_pin') is not None]
    out = {'matchs': n, 'roi_pct': round(100 * sum(pnl) / n, 1),
           'roi_ic95': [round(100 * x, 1) for x in ic(pnl, lambda s: sum(s) / len(s))],
           'gagnes_pct': round(100 * sum(1 for t in T if t.get('won')) / n, 1)}
    if clv:
        out['clv_med'] = round(st.median(clv), 2)
        out['clv_ic95'] = [round(x, 2) for x in ic(clv, st.median)]
    if n < MIN_MATCHS:
        out['verdict'] = f'trop tôt ({n}/{MIN_MATCHS} matchs) : rien n\'est conclu'
    elif clv and out['clv_ic95'][0] > 0:
        out['verdict'] = 'CLV positive (borne basse de l\'IC 95 % au-dessus de 0) ; le ROI reste descriptif'
    else:
        out['verdict'] = 'CLV non démontrée (IC 95 % touchant 0) ; le ROI reste descriptif'
    return out


def texte(resultats):
    L = [f"🧊 Suivi gelé « une position par match » (jugé sur les matchs après le {GEL:%d/%m/%Y %H:%M} UTC)"]
    for nom, b in resultats.items():
        L.append(f"\n• Journal {nom} : {b['matchs']} match(s)")
        if b['matchs']:
            L.append(f"  CLV méd {b.get('clv_med', 0):+.2f} % (IC95 {b.get('clv_ic95', [0, 0])[0]:+.2f} ; "
                     f"{b.get('clv_ic95', [0, 0])[1]:+.2f}) · ROI {b['roi_pct']:+.1f} % (IC95 {b['roi_ic95'][0]:+.1f} ; "
                     f"{b['roi_ic95'][1]:+.1f}) · gagnés {b['gagnes_pct']:.0f} %")
        L.append(f"  → {b['verdict']}")
    L.append("\nLa CLV est la seule validation ; rien avant 30 matchs ; aucun conseil de mise.")
    return '\n'.join(L)


def envoyer(msg):
    tok, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not tok or not chat:
        print('Telegram non configuré : message seulement affiché.')
        return False
    data = urllib.parse.urlencode({'chat_id': chat, 'text': msg}).encode()
    try:
        with urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/sendMessage', data=data, timeout=20) as r:
            return r.status == 200
    except OSError as e:
        print('Telegram :', e)
        return False


def main(argv):
    racine = next((a for a in argv[1:] if not a.startswith('--')), '.')
    res = {nom: bilan(premieres(os.path.join(racine, f))) for nom, f in JOURNAUX}
    msg = texte(res)
    print(msg)
    if '--telegram' in argv:
        envoyer(msg)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
