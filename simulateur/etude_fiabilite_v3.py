#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_fiabilite_v3.py — une note de fiabilité qui tient sa promesse (04/11/2026, définition de Lucas : « plus la note est
haute et proche de 100, plus les résultats sont censés être la réalité »).

Mesure : la PENTE d'étalonnage a d'un groupe de matchs — réel ~ σ(a · logit p annoncé).
  a = 1 : nos % se réalisent tels quels ; a < 1 : trop sûrs (la réalité est plus proche de 50 %) ; a > 1 : pas assez.
Note v3 d'un match = 100 · min(a, 1/a) de sa CASE, apprise sur 2016–2022 de l'archive, avec la correction combinée
en place (etude_signaux_combines.py) : 100 = « nos % sont la réalité » ; 80 = « nos écarts à 50 % sont trop
forts (ou trop faibles) de 20 % ». Cases (connues avant le match) : circuit × expérience du moins connu des deux
(10–29, 30–99, 100–299, 300 matchs et plus) × ampleur de la correction combinée (nulle, < 0,15, ≥ 0,15 en logit).
Rétrécie vers la pente de son circuit (poids n / (n + 300)).

RÈGLE FIXÉE LE 04/11/2026, AVANT DE REGARDER LE RÉSULTAT : la note v3 REMPLACE la note affichée si, sur 2023 → 2026
(jamais vu), le tiers des matchs aux notes les plus hautes a (1) une pente plus proche de 1 et (2) une erreur
d'étalonnage (moyenne pondérée |réel − annoncé| par tranches de 10 points) plus petite que le tiers aux notes les plus
basses, toutes circuits confondus ET sur au moins deux circuits sur trois. Sinon la note actuelle reste.
Usage : python simulateur/etude_fiabilite_v3.py /tmp/sackmann .
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_signaux_combines as ESC  # noqa: E402

COUPURE = dt.date(2023, 1, 1)
EXPERIENCE = (10, 30, 100, 300, 10 ** 9)
AMPLEUR = (0.0, 0.15)
RETRECI = 300.0
SORTIE = os.path.join(ICI, 'rapport_fiabilite_v3.json')


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def classe_experience(n_min):
    for i, (lo, hi) in enumerate(zip(EXPERIENCE[:-1], EXPERIENCE[1:])):
        if lo <= n_min < hi:
            return i
    return 0


def classe_ampleur(d):
    d = abs(d or 0.0)
    return 0 if d < 1e-9 else 1 if d < AMPLEUR[1] else 2


def case(circuit, n_min, ampleur):
    return f'{circuit}|{classe_experience(n_min)}|{classe_ampleur(ampleur)}'


def pente(R):
    """a tel que y ~ σ(a·z) (vainqueur = A, donc y = 1 sur z) : Newton à un paramètre."""
    a = 1.0
    for _ in range(50):
        g = h = 0.0
        for z in R:
            q = _sg(a * z)
            g += (q - 1) * z
            h += q * (1 - q) * z * z
        if h <= 0:
            break
        d = g / h
        a -= d
        if abs(d) < 1e-9:
            break
    return a


def note(a):
    return round(100 * min(a, 1 / a)) if a > 0 else 0


def apprendre_cases(R):
    """{case: pente rétrécie vers celle du circuit} — R : [(case, circuit, z)]."""
    par_c, par_case = {}, {}
    for k, c, z in R:
        par_c.setdefault(c, []).append(z)
        par_case.setdefault(k, []).append(z)
    a_c = {c: pente(v) for c, v in par_c.items()}
    out = {}
    for k, v in par_case.items():
        c = k.split('|')[0]
        w = len(v) / (len(v) + RETRECI)
        out[k] = {'pente': round(w * pente(v) + (1 - w) * a_c[c], 4), 'matchs': len(v)}
    out['_circuits'] = {c: round(a, 4) for c, a in a_c.items()}
    return out


def note_du_match(modele, circuit, n_min, ampleur):
    m = (modele or {}).get(case(circuit, n_min, ampleur))
    a = m['pente'] if m else ((modele or {}).get('_circuits') or {}).get(circuit)
    return note(a) if a else None


def erreur_etalonnage(P):
    """P : [(p annoncé au vainqueur réel… non : (p_A, y_A))] → moyenne pondérée |réel − annoncé| par tranches de 10 points."""
    tot, n = 0.0, 0
    for lo in range(0, 100, 10):
        b = [(p, y) for p, y in P if lo <= 100 * p < lo + 10]
        if b:
            tot += abs(sum(y for _, y in b) - sum(p for p, _ in b))
            n += len(b)
    return tot / max(1, n)


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    rows = ESC.lignes(archive, racine)
    betas = {}
    for c in ('ATP', 'WTA', 'CH'):
        betas[c] = ESC.apprendre([(r['z'], r['x']) for r in rows if r['c'] == c and r['d'] < COUPURE])
    X = []
    for r in rows:
        d = sum(bi * xi for bi, xi in zip(betas[r['c']], r['x']))
        X.append({'d': r['d'], 'c': r['c'], 'z': r['z'] + d, 'k': case(r['c'], min(r['n']), d)})
    modele = apprendre_cases([(x['k'], x['c'], x['z']) for x in X if x['d'] < COUPURE])
    ju = [x for x in X if x['d'] >= COUPURE]
    for x in ju:
        m = modele.get(x['k'])
        x['note'] = note(m['pente'] if m else modele['_circuits'][x['c']])
    # le match vu « côté A » (vainqueur) biaiserait l'étalonnage : on le symétrise (A ou B au hasard fixe)
    import random
    rnd = random.Random(20261104)
    for x in ju:
        x['sym'] = (_sg(x['z']), 1) if rnd.random() < 0.5 else (1 - _sg(x['z']), 0)

    def bilan(G):
        S = sorted(G, key=lambda x: x['note'])
        k = len(S) // 3
        T = {'bas': S[:k], 'haut': S[2 * k:]}
        out = {}
        for nom, g in T.items():
            a = pente([x['z'] for x in g])
            out[nom] = {'matchs': len(g), 'notes': [g[0]['note'], g[-1]['note']] if g else None, 'pente_jugee': round(a, 4),
                        'distance_a_1': round(abs(1 - a), 4), 'erreur_etalonnage_pts': round(100 * erreur_etalonnage([x['sym'] for x in g]), 2)}
        out['tient'] = bool(out['haut']['distance_a_1'] < out['bas']['distance_a_1']
                            and out['haut']['erreur_etalonnage_pts'] < out['bas']['erreur_etalonnage_pts'])
        return out
    jug = {'tous': bilan(ju)}
    for c in ('ATP', 'WTA', 'CH'):
        jug[c] = bilan([x for x in ju if x['c'] == c])
    adopte = jug['tous']['tient'] and sum(jug[c]['tient'] for c in ('ATP', 'WTA', 'CH')) >= 2
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'definition': "note = 100 · min(a, 1/a), a = pente d'étalonnage de la case du match (1 = nos % sont la réalité)",
           'regle': ("remplace la note affichée si, sur 2023 →, le tiers haut a une pente plus proche de 1 ET une erreur "
                     "d'étalonnage plus petite que le tiers bas, au global ET sur au moins 2 circuits sur 3"),
           'modele': modele, 'betas_combines_2016_2022': {c: [round(v, 4) for v in b] for c, b in betas.items()},
           'jugement_2023': jug, 'adopte': bool(adopte)}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: doc[k] for k in ('jugement_2023', 'adopte')}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
