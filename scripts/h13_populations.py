#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
h13_populations.py — mesure SÉPARÉMENT les deux populations H13, et
quantifie leur divergence.

    A. les alertes Telegram RÉELLEMENT ENVOYÉES   (h13_signal_log.jsonl)
    B. la RECONSTRUCTION historique               (moves_detail_hist.csv)

──────────────────────────────────────────────────────────────────────────
POURQUOI CE SCRIPT EXISTE

Pendant des semaines, le ROI « H13 out-of-sample » a été lu comme s'il
décrivait le flux Telegram. Ce n'est pas le cas. Mesuré le 25/09/2026 sur
77 matchs présents des deux côtés :

    côté steamé DIFFÉRENT        24/77  =  31 %
    book d'entrée différent      53/77  =  69 %
    détection >30 min plus tôt   70/77  =  91 %
    lead médian : alerte 391 min · reconstruction 759 min

Et le mécanisme est enchaîné : quand le côté diffère, la cote change, donc
le pari sort de la bande 2,00-3,00. Sur les 24 divergences, UNE SEULE reste
dans la bande — contre 48 sur 53 quand le côté concorde. C'est ce qui
explique que 40 alertes sur 105 soient absentes de la reconstruction.

Les deux populations donnent d'ailleurs des résultats différents :

    A. alertes envoyées   n=105  gains 41,9 %  ROI  +0,2 %
    B. reconstruction     n=137  gains 44,5 %  ROI  +7,5 %

CE NE SONT PAS DEUX MESURES DU MÊME SYSTÈME. Les confondre, c'est
attribuer au flux Telegram un rendement qu'il n'a pas produit.

──────────────────────────────────────────────────────────────────────────
CE QUE CE SCRIPT NE FAIT PAS

Il ne corrige pas la divergence — il la MESURE. La corriger demanderait
d'aligner l'instant d'observation de h13_signal.py sur celui de
move_audit.py, ce qui changerait le signal envoyé et donc romprait le gel
de l'hypothèse 13.

Tant que la divergence existe, la règle est simple : le ROI du flux
Telegram se lit dans la section A, jamais dans la B.

Env : LOG, SRC, SET_RESULTS, GEL, COTE_MIN, COTE_MAX, OUT.
"""
import os
import sys
import csv
import json
import math
import re
import unicodedata
import statistics as st

LOG = os.environ.get('LOG', 'h13_signal_log.jsonl')
SRC = os.environ.get('SRC', 'moves_detail_hist.csv')
SET_RESULTS = os.environ.get('SET_RESULTS', 'set_results.json')
GEL = os.environ.get('GEL', '2026-09-06')
COTE_MIN = float(os.environ.get('COTE_MIN', '2.0'))
COTE_MAX = float(os.environ.get('COTE_MAX', '3.0'))
OUT = os.environ.get('OUT', 'h13_populations.json')
Z = 1.96


def _norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z]', '', s.lower())


def _side_depuis_uid(uid, joueur):
    """'home'/'away' déduit du uid 'AAAA-MM-JJ_home_away'.

    Utilisé UNIQUEMENT pour les lignes anciennes sans champ `side` (avant
    le 09/09). Ne tranche que si le nom colle d'un seul côté : un nom qui
    matche les deux extrémités renvoie None plutôt que d'inverser le pari.
    """
    if not uid or not joueur:
        return None
    base = uid[11:] if re.match(r'^\d{4}-\d\d-\d\d_', uid) else uid
    u, j = _norm(base), _norm(joueur)
    if not j:
        return None
    d, f = u.startswith(j), u.endswith(j)
    if d and not f:
        return 'home'
    if f and not d:
        return 'away'
    return None


def wilson(k, n):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return (c - h, c + h)


def _ecart_type(v):
    if len(v) < 2:
        return 0.0
    m = sum(v) / len(v)
    return (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5


def charger_resultats():
    try:
        return json.load(open(SET_RESULTS, encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def population_A(res):
    """Les alertes RÉELLEMENT parties sur Telegram."""
    out = []
    try:
        lignes = list(open(LOG, encoding='utf-8'))
    except OSError:
        return out
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            x = json.loads(ligne)
        except ValueError:
            continue
        uid = x.get('uid')
        side = x.get('side') or _side_depuis_uid(uid, x.get('joueur'))
        g = (res.get(uid) or {}).get('match')
        if not side or g not in ('home', 'away'):
            continue
        try:
            cote = float(x['cote'])
        except (KeyError, TypeError, ValueError):
            continue
        w = 1 if g == side else 0
        out.append({'uid': uid, 'cote': cote, 'win': w,
                    'pnl': (cote - 1.0) if w else -1.0, 'side': side,
                    'lead': x.get('lead_min'), 'book': x.get('book'),
                    'date': str(x.get('signale_le'))[:10]})
    return out


def population_B():
    """La reconstruction move_audit, bande gelée, out-of-sample."""
    out, tous = [], {}
    try:
        lignes = list(csv.DictReader(open(SRC, encoding='utf-8')))
    except OSError:
        return out, tous
    for r in lignes:
        d = str(r.get('date') or '')[:10]
        if not d or d < GEL:
            continue
        try:
            cote = float(r['entry'])
            lead = float(r['lead_min'])
        except (KeyError, TypeError, ValueError):
            continue
        side = _side_depuis_uid(r.get('uid'), r.get('steame'))
        # Index de TOUTES les lignes post-gel, bande comprise ou non :
        # la comparaison avec A doit porter sur l'ensemble, sinon on ne
        # verrait pas les divergences qui font SORTIR de la bande.
        tous[r['uid']] = {'cote': cote, 'side': side, 'lead': lead,
                          'book': r.get('entry_book')}
        if not (COTE_MIN <= cote <= COTE_MAX):
            continue
        g = r.get('steame_gagne')
        if g not in ('oui', 'non'):
            continue
        try:
            pnl = float(r['pnl'])
        except (KeyError, TypeError, ValueError):
            pnl = (cote - 1.0) if g == 'oui' else -1.0
        out.append({'uid': r['uid'], 'cote': cote,
                    'win': 1 if g == 'oui' else 0, 'pnl': pnl,
                    'side': side, 'lead': lead, 'book': r.get('entry_book'),
                    'date': d})
    return out, tous


def bilan(D, lib):
    if not D:
        print(f"  {lib} : aucun pari dénoué.\n")
        return None
    p = [x['pnl'] for x in D]
    k = sum(x['win'] for x in D)
    n = len(D)
    p0 = st.mean([1 / x['cote'] for x in D])
    lo, hi = wilson(k, n)
    roi = 100 * st.mean(p)
    ic = 100 * Z * _ecart_type(p) / math.sqrt(n)
    lm = [x['lead'] for x in D if isinstance(x.get('lead'), (int, float))]
    print(f"  {lib}")
    print(f"    n={n} · gains {k} = {100*k/n:.1f} % · seuil de rentabilité "
          f"{100*p0:.1f} %")
    print(f"    IC95 du taux [{100*lo:.1f} ; {100*hi:.1f}]"
          + ("   ✅ au-dessus du seuil" if 100*lo > 100*p0 else
             ("   ❌ sous le seuil" if 100*hi < 100*p0 else
              "   — ne tranche pas")))
    print(f"    ROI {roi:+.1f} % [{roi-ic:+.1f} ; {roi+ic:+.1f}] · "
          f"P&L {sum(p):+.1f} u")
    print(f"    cote médiane {st.median([x['cote'] for x in D]):.2f}"
          + (f" · lead médian {st.median(lm):.0f} min" if lm else "") + "\n")
    return {'n': n, 'gains': k, 'taux': round(100*k/n, 1),
            'seuil': round(100*p0, 1), 'ic_bas': round(100*lo, 1),
            'ic_haut': round(100*hi, 1), 'roi': round(roi, 1),
            'roi_ic_bas': round(roi-ic, 1), 'roi_ic_haut': round(roi+ic, 1),
            'pnl': round(sum(p), 2)}


def divergence(A, B_tous):
    """Quantifie l'écart entre le flux envoyé et la reconstruction."""
    a = {x['uid']: x for x in A}
    com = sorted(set(a) & set(B_tous))
    print("  C — DIVERGENCE ENTRE LES DEUX POPULATIONS")
    if not com:
        print("    aucun match commun — comparaison impossible.\n")
        return {}
    diff = [u for u in com if a[u]['side'] and B_tous[u]['side']
            and a[u]['side'] != B_tous[u]['side']]
    same = [u for u in com if u not in diff]
    bk = sum(1 for u in com
             if a[u]['book'] and B_tous[u]['book']
             and a[u]['book'] != B_tous[u]['book'])
    la = [a[u]['lead'] for u in com
          if isinstance(a[u].get('lead'), (int, float))]
    lb = [B_tous[u]['lead'] for u in com]
    ec = sorted(B_tous[u]['lead'] - a[u]['lead'] for u in com
                if isinstance(a[u].get('lead'), (int, float)))
    tot = len(a)
    print(f"    {tot} alerte(s) envoyée(s) · {len(com)} retrouvée(s) dans la "
          f"reconstruction · {tot-len(com)} absente(s)")
    print(f"    CÔTÉ STEAMÉ DIFFÉRENT : {len(diff)}/{len(com)} = "
          f"{100*len(diff)/len(com):.0f} %")
    # L'enchaînement qui explique les absences : côté différent -> cote
    # différente -> hors bande -> absent de la population jugée.
    for lib, S in (('côté identique', same), ('côté DIFFÉRENT', diff)):
        if not S:
            continue
        dans = sum(1 for u in S if COTE_MIN <= B_tous[u]['cote'] <= COTE_MAX)
        print(f"      {lib:16} {len(S):3} match(s) · {dans:3} dans la bande "
              f"({100*dans/len(S):.0f} %)")
    print(f"    book d'entrée différent : {bk}/{len(com)} = "
          f"{100*bk/len(com):.0f} %")
    if la and lb:
        print(f"    lead médian : alerte {st.median(la):.0f} min · "
              f"reconstruction {st.median(lb):.0f} min")
    if ec:
        plus = 100 * sum(1 for x in ec if x > 30) / len(ec)
        print(f"    reconstruction détecte >30 min plus tôt : {plus:.0f} %")
    print()
    return {'communs': len(com), 'absents': tot - len(com),
            'cote_differente': len(diff), 'book_different': bk,
            'lead_median_alerte': round(st.median(la), 0) if la else None,
            'lead_median_reconstruction': round(st.median(lb), 0) if lb else None}


def main():
    res = charger_resultats()
    A = population_A(res)
    B, B_tous = population_B()
    print("H13 — DEUX POPULATIONS, MESURÉES SÉPARÉMENT\n")
    ra = bilan(A, "A — ALERTES TELEGRAM RÉELLEMENT ENVOYÉES")
    rb = bilan(B, f"B — RECONSTRUCTION move_audit "
                  f"(bande {COTE_MIN:.2f}-{COTE_MAX:.2f}, post-gel)")
    rd = divergence(A, B_tous)
    print("  LECTURE")
    print("    Le ROI du flux Telegram est celui de A. Celui de B décrit une")
    print("    population reconstruite qui détecte plus tôt, sur un autre")
    print("    book, et parfois sur l'autre joueur. Les deux ne se")
    print("    substituent pas l'un à l'autre.")
    try:
        json.dump({'alertes_envoyees': ra, 'reconstruction': rb,
                   'divergence': rd},
                  open(OUT, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print(f"\n  -> {OUT}")
    except OSError as e:
        print(f"\n  ⚠️ écriture de {OUT} impossible : {e}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
