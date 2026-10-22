#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_forme_du_jour.py — la « forme du jour » existe-t-elle, mesurée à la source ? (22/10/2026)

Le moteur suppose qu'un joueur dans un bon (ou mauvais) jour le reste tout le match :
un écart δ ~ N(0 ; σ = 0,15), tiré une fois par match, ajouté (en logit) à son service
et retiré de celui de l'adversaire. σ a été réglé sur le NOMBRE DE SETS seulement.
Les feuilles collectées donnent les statistiques SET PAR SET : on peut le vérifier.

Pour chaque joueur et chaque match (ATP, WTA, Challenger ; au moins 2 sets avec feuille) :
  résidu du set s = % de points gagnés sur son service au set s − sa moyenne sur ses
  AUTRES matchs (au moins 3). Mesures (moyennes de produits de résidus) :
  A. même joueur, set 1 × set 2 du MÊME match            -> forme du jour + biais du joueur ;
     même joueur, set 1 d'un match × set 2 d'un AUTRE match -> biais du joueur seul (témoin) ;
     forme du jour = A(même match) − A(témoin).
  B. les deux joueurs, même set : service de A × service de B.
     Le modèle prévoit un signe NÉGATIF (A en forme = B sert moins bien). Un signe positif
     signale plutôt les conditions du jour (court rapide, vent) qui touchent les deux.
  C. même mesure que A pour le % de 1re balle (la variation de la 1re balle d'un match à
     l'autre, défaut constaté du match simulé).
Traduction en σ (logit) : σ ≈ √(variance) / p(1−p) moyen. Intervalles à 95 % par
rééchantillonnage des matchs (200 tirages). C'est une ÉTUDE : rien n'est modifié
automatiquement dans le moteur ; un changement de σ serait une nouvelle règle à geler.

Usage : python simulateur/etude_forme_du_jour.py [racine]
Sortie : simulateur/rapport_forme_du_jour.json
"""
import collections
import datetime as dt
import json
import math
import os
import random
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import feuilles as FE  # noqa: E402
import elo as E  # noqa: E402

SORTIE = os.path.join(ICI, 'rapport_forme_du_jour.json')
SIGMA_MODELE = 0.15
PERIODES = ('1ST', '2ND', '3RD', '4TH', '5TH')
N_MIN_SET = 12              # points de service au moins dans le set
MATCHS_MIN = 3              # autres matchs du joueur pour sa moyenne


def sets_joueur(r, cote):
    """[(points de service, gagnés, 1res dans)] par set, pour home (cote 0) ou away (cote 2)."""
    out = []
    st = r.get('stats') or {}
    for p in PERIODES:
        x = st.get(p)
        if not x:
            break
        n = (x.get('firstServeAccuracy') or [None] * 4)[cote + 1]
        k = (x.get('servicePointsScored') or [None] * 4)[cote]
        f = (x.get('firstServeAccuracy') or [None] * 4)[cote]
        try:
            n, k, f = int(n), int(k), int(f)
        except (TypeError, ValueError):
            break
        if n < N_MIN_SET or not 0 <= k <= n or not 0 <= f <= n:
            break
        out.append((n, k, f))
    return out


def preparer(fiches):
    """Liste de matchs : {'id', 'joueurs': [(clé, [(n, k, f) par set])] * 2}."""
    M = []
    for r in fiches:
        if FE.circuit_de(r.get('categorie')) not in ('ATP', 'WTA', 'CH'):
            continue
        if str((r.get('statut') or {}).get('texte') or '').lower() != 'ended':
            continue
        a, b = sets_joueur(r, 0), sets_joueur(r, 2)
        if len(a) >= 2 and len(b) >= 2:
            M.append({'id': r.get('id'), 'j': [(E.cle(r['home'].get('nom')), a), (E.cle(r['away'].get('nom')), b)]})
    return M


def residus(M):
    """Résidus par joueur-match : (match, joueur, [r_set service], [r_set 1re balle], p moyen, f moyen)."""
    tot = collections.defaultdict(lambda: [0, 0, 0])            # joueur -> n, gagnés, 1res dans (tous matchs)
    nb = collections.Counter()
    for m in M:
        for j, s in m['j']:
            nb[j] += 1
            for n, k, f in s:
                t = tot[j]
                t[0] += n
                t[1] += k
                t[2] += f
    out = []
    for mi, m in enumerate(M):
        for ji, (j, s) in enumerate(m['j']):
            if nb[j] - 1 < MATCHS_MIN:
                continue
            n0 = tot[j][0] - sum(x[0] for x in s)
            p = (tot[j][1] - sum(x[1] for x in s)) / n0
            f = (tot[j][2] - sum(x[2] for x in s)) / n0
            out.append({'m': mi, 'cote': ji, 'j': j, 'r': [k / n - p for n, k, _ in s],
                        'rf': [fi / n - f for n, _, fi in s], 'p': p, 'f': f})
    return out


def mesures(R, M, rnd):
    """Covariances A (même joueur), B (adversaires, même set), C (1re balle), témoins compris."""
    par_joueur = collections.defaultdict(list)
    par_match = collections.defaultdict(dict)
    for x in R:
        par_joueur[x['j']].append(x)
        par_match[x['m']][x['cote']] = x
    A_in = [x['r'][0] * x['r'][1] for x in R]
    C_in = [x['rf'][0] * x['rf'][1] for x in R]
    A_out, C_out = [], []
    for x in R:
        autres = [y for y in par_joueur[x['j']] if y['m'] != x['m']]
        if autres:
            y = rnd.choice(autres)
            A_out.append(x['r'][0] * y['r'][1])
            C_out.append(x['rf'][0] * y['rf'][1])
    B_in, B_out = [], []
    tous = list(par_match.values())
    for d in tous:
        if 0 in d and 1 in d:
            for s in range(min(len(d[0]['r']), len(d[1]['r']))):
                B_in.append(d[0]['r'][s] * d[1]['r'][s])
            e = rnd.choice(tous)
            if 1 in e and e is not d:
                B_out.append(d[0]['r'][0] * e[1]['r'][0])
    moy = lambda v: sum(v) / len(v) if v else None
    return {'A_meme_match': moy(A_in), 'A_temoin': moy(A_out), 'B_meme_set': moy(B_in), 'B_temoin': moy(B_out),
            'C_meme_match': moy(C_in), 'C_temoin': moy(C_out), 'n_joueur_match': len(R), 'n_paires_B': len(B_in)}


def en_sigma(v, pq):
    if v is None or pq <= 0:
        return None
    return math.copysign(math.sqrt(abs(v)) / pq, v)


def main(argv):
    racine = argv[1] if len(argv) > 1 else os.path.join(ICI, '..')
    fiches = FE.lire(racine)
    M = preparer(fiches)
    R = residus(M)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'sigma_modele': SIGMA_MODELE,
           'matchs_avec_sets': len(M), 'joueur_matchs': len(R)}
    if len(M) < 200 or len(R) < 300:
        doc['verdict'] = f"en attente : {len(M)} matchs avec feuilles set par set (200 au moins)"
        with open(SORTIE, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        print(doc['verdict'])
        return 0
    rnd = random.Random(7)
    base = mesures(R, M, rnd)
    pq = sum(x['p'] * (1 - x['p']) for x in R) / len(R)
    fq = sum(x['f'] * (1 - x['f']) for x in R) / len(R)
    # Rééchantillonnage des matchs
    par_m = collections.defaultdict(list)
    for x in R:
        par_m[x['m']].append(x)
    ids = list(par_m)
    tirages = collections.defaultdict(list)
    for t in range(200):
        tir = [rnd.choice(ids) for _ in ids]
        RR = []
        for k, mid in enumerate(tir):
            for x in par_m[mid]:
                RR.append(dict(x, m=(k, mid)))
        z = mesures(RR, M, rnd)
        tirages['forme'].append(z['A_meme_match'] - z['A_temoin'])
        tirages['adversaires'].append(z['B_meme_set'] - z['B_temoin'])
        tirages['premiere'].append(z['C_meme_match'] - z['C_temoin'])
    ic = lambda v: [round(sorted(v)[int(0.025 * len(v))], 6), round(sorted(v)[int(0.975 * len(v)) - 1], 6)]
    forme = base['A_meme_match'] - base['A_temoin']
    adv = base['B_meme_set'] - base['B_temoin']
    prem = base['C_meme_match'] - base['C_temoin']
    doc.update({
        'mesures_brutes': {k: (round(v, 6) if isinstance(v, float) else v) for k, v in base.items()},
        'forme_du_jour_service': {'variance': round(forme, 6), 'ic95': ic(tirages['forme']),
                                  'sigma_logit': round(en_sigma(forme, pq), 3) if en_sigma(forme, pq) is not None else None,
                                  'attendu_par_le_modele_variance': round((SIGMA_MODELE * pq) ** 2, 6)},
        'adversaires_meme_set': {'covariance': round(adv, 6), 'ic95': ic(tirages['adversaires']),
                                 'lecture': ("négatif : un joueur en forme fait moins bien servir l'autre (ce que suppose le modèle)"
                                             if adv < 0 else 'positif : les deux servent mieux ou moins bien ensemble (conditions du jour)')},
        'premiere_balle': {'variance': round(prem, 6), 'ic95': ic(tirages['premiere']),
                           'sigma_logit': round(en_sigma(prem, fq), 3) if en_sigma(prem, fq) is not None else None},
    })
    f = doc['forme_du_jour_service']
    lo, hi = f['ic95']
    att = f['attendu_par_le_modele_variance']
    doc['verdict'] = (f"forme du jour au service : σ ≈ {f['sigma_logit']} en logit (modèle : {SIGMA_MODELE}) ; "
                      + ('compatible avec le modèle' if lo <= att <= hi else
                         ('plus forte que le modèle' if lo > att else 'plus faible que le modèle'))
                      + f" ; adversaires au même set : {doc['adversaires_meme_set']['lecture']}"
                      + f" ; 1re balle d'un match à l'autre : σ ≈ {doc['premiere_balle']['sigma_logit']} en logit")
    with open(SORTIE, 'w', encoding='utf-8') as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
