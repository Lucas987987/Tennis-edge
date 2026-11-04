#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_confiance_circuits.py — les pronostics forts (au-delà de 70 %) sont-ils trop sûrs, ou pas assez, circuit par
circuit ? (04/11/2026, point 2 ; décision de Lucas : tout est jugé par circuit)

Population : les pronostics hors échantillon FIGÉS (simulateur/pronostics_hors_echantillon.jsonl.gz, probabilité
affichée p_algo, résultat réel), jamais les cotes. Le direct (pronostics_resultats.json) est donné à part, pour info.

Correction testée (un seul paramètre par circuit, symétrique favori / outsider), en logit :
    |z'| = |z|                         si |z| ≤ logit 70 %
    |z'| = n70 + k · (|z| − n70)       au-delà        (k < 1 : on calme les gros favoris ; k > 1 : on les renforce)
k choisi sur une grille 0,50 → 1,50 (pas 0,02) en minimisant la log loss.

RÈGLE FIXÉE LE 04/11/2026, AVANT DE REGARDER LE RÉSULTAT :
  k appris sur les matchs d'AVANT le 1er octobre 2026, jugé sur ceux d'après (jamais vus) ;
  positif sur un circuit si la log loss jugée baisse d'au moins 0,001 sur au moins 300 matchs jugés.
  Positif → modèle fantôme « confiance » sur les nouveaux matchs de ce circuit (k ré-appris sur tout l'historique),
  adopté seulement par fantomes_circuits.py (deux semaines gagnantes de suite). Sinon : rien ne change sur ce circuit.
"""
import datetime as dt
import gzip
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

COUPURE = '2026-10-01'
N70 = math.log(0.7 / 0.3)
GRILLE = [round(0.5 + 0.02 * i, 2) for i in range(51)]
MIN_JUGES, MARGE = 300, 0.001
SORTIE = os.path.join('simulateur', 'confiance_circuits.json')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def corriger(p, k):
    """Probabilité corrigée au-delà de 70 % (k = 1 ou None : inchangée)."""
    if k is None or k == 1.0 or p is None:
        return p
    z = _lg(p)
    a = abs(z)
    if a <= N70:
        return p
    a2 = N70 + k * (a - N70)
    return _sg(a2 if z >= 0 else -a2)


def ll(rows, k=1.0):
    if not rows:
        return None
    return sum(-math.log(min(max(corriger(p, k) if y else 1 - corriger(p, k), 1e-6), 1 - 1e-6)) for p, y in rows) / len(rows)


def apprendre(rows):
    return min(GRILLE, key=lambda k: ll(rows, k)) if rows else 1.0


def lignes(racine):
    out = []
    try:
        with gzip.open(os.path.join(racine, 'simulateur', 'pronostics_hors_echantillon.jsonl.gz'), 'rt',
                       encoding='utf-8') as fh:
            for l_ in fh:
                r = json.loads(l_)
                if r.get('p_algo') is None or r.get('gagnant') not in ('home', 'away') or not r.get('t'):
                    continue
                jour = dt.datetime.fromtimestamp(r['t'], dt.timezone.utc).date().isoformat()
                out.append((r.get('circuit') or '?', jour, float(r['p_algo']), int(r['gagnant'] == 'home')))
    except (OSError, ValueError):
        pass
    return out


def calib(rows, k=1.0):
    t = []
    for lo in (70, 80, 90):
        b = [(max(corriger(p, k), 1 - corriger(p, k)), y if p >= .5 else 1 - y) for p, y in rows]
        b = [x for x in b if lo <= 100 * x[0] < lo + 10]
        if b:
            t.append(f"{lo}–{lo + 10} % : n {len(b)}, {100 * sum(q for q, _ in b) / len(b):.1f} → "
                     f"{100 * sum(v for _, v in b) / len(b):.1f}")
    return ' · '.join(t)


def etude(L):
    out = {}
    for c in ('ATP', 'WTA', 'CH'):
        av = [(p, y) for cc, j, p, y in L if cc == c and j < COUPURE]
        ju = [(p, y) for cc, j, p, y in L if cc == c and j >= COUPURE]
        k = apprendre(av)
        l0, l1 = ll(ju), ll(ju, k)
        gain = round(l0 - l1, 5) if ju else None
        positif = len(ju) >= MIN_JUGES and gain is not None and gain >= MARGE
        tout = [(p, y) for cc, j, p, y in L if cc == c]
        out[c] = {'appris': len(av), 'juges': len(ju), 'k_appris': k, 'log_loss_sans': round(l0, 5) if l0 else None,
                  'log_loss_avec': round(l1, 5) if l1 else None, 'gain': gain, 'positif': bool(positif),
                  'k_fantome': apprendre(tout) if positif else None,
                  'calibration_jugee_sans': calib(ju), 'calibration_jugee_avec': calib(ju, k)}
    return out


def lire(racine):
    """{circuit: k} des circuits où le fantôme « confiance » tourne."""
    try:
        with open(os.path.join(racine, SORTIE), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return {}
    return {c: v['k_fantome'] for c, v in (doc.get('circuits') or {}).items() if v.get('positif') and v.get('k_fantome')}


def main(racine):
    L = lignes(racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'matchs': len(L),
           'regle': ("k appris avant le 01/10/2026, jugé après ; positif si −0,001 de log loss sur ≥ 300 matchs jugés, "
                     "par circuit ; positif → fantôme « confiance » (deux semaines gagnantes pour l'adopter)"),
           'circuits': etude(L)}
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return doc


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ICI, '..'))
