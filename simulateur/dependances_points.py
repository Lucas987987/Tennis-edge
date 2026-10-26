"""Tests de dépendances entre points sur séquences ordonnées, sans marché.

Les variables n'utilisent que le passé du point courant. Une amélioration de la
vraisemblance des points ne suffit pas à publier : le candidat devra ensuite passer
le backtest du vainqueur et la gouvernance champion–challenger.
"""
import argparse
import datetime as dt
import json
import math
import os
from collections import defaultdict

import random

import facteurs as FA
import match_simule as MS

FEATURES = ('precedent', 'tiebreak', 'points_100', 'points_100_bo5', 'set_avance')
CANDIDATS = {
    'momentum': ('precedent',),
    'tiebreak': ('tiebreak',),
    'fatigue_format': ('points_100', 'points_100_bo5'),
    'evolution_sets': ('set_avance',),
    'combines': FEATURES,
}


def extraire(lignes, coefs=None):
    """[(n, k, offset, features)] + index du match ; y = le serveur gagne le point."""
    rows, matchs = [], []
    for ix, x in enumerate(lignes):
        if not x.get('pbp'):
            continue
        bases = []
        for k in (0, 1):
            r, v = x['srv'][k], x['var'][k]
            ds, _, _ = FA.deltas(v, coefs or {})
            bases.append(MS.p_service(MS.appliquer_facteurs(r['tx'], ds, 0.0, 0.0)))
        precedent, n_points = 0.0, 0
        for jeu in x['pbp']:
            if len(jeu) != 4:
                continue
            try:
                set_no, game_no, serveur = int(jeu[0]), int(jeu[1]), int(jeu[2])
            except (TypeError, ValueError):
                continue
            if serveur not in (0, 1):
                continue
            off = FA._lg(bases[serveur])
            for issue in str(jeu[3]).upper():
                if issue not in ('H', 'A'):
                    continue
                f = [precedent, float(game_no >= 13), n_points / 100.0,
                     n_points / 100.0 if x.get('bo') == 5 else 0.0, max(0, set_no-1) / 2.0]
                gagnant = 0 if issue == 'H' else 1
                rows.append((1, int(gagnant == serveur), off, f))
                matchs.append(ix)
                precedent = 1.0 if gagnant == serveur else -1.0
                n_points += 1
    return rows, matchs


def _ll(rows, b):
    return FA.log_vrais(rows, b)


def _sous(rows, matchs, ids):
    ids = set(ids)
    return [r for r, ix in zip(rows, matchs) if ix in ids], [ix for ix in matchs if ix in ids]


def _features(rows, noms):
    idx = [FEATURES.index(f) for f in noms]
    return [(n, k, off, [x[i] for i in idx]) for n, k, off, x in rows]


def _bootstrap(rows0, rows1, matchs, n=1000):
    """IC du gain de log loss, rééchantillonnage par match et non par point."""
    par_match = defaultdict(lambda: [0.0, 0.0, 0])
    for a, b, ix in zip(rows0, rows1, matchs):
        n, k, off, x = a
        p0 = FA._sg(off)
        p1 = FA._sg(off + sum(u*v for u, v in zip(b[3], x)))
        d = (-k*math.log(max(1e-9, p1))-(n-k)*math.log(max(1e-9, 1-p1))
             + k*math.log(max(1e-9, p0))+(n-k)*math.log(max(1e-9, 1-p0)))
        z = par_match[ix]
        z[0] += d
        z[2] += n
    vals = [(z[0], z[2]) for z in par_match.values()]
    if len(vals) < 20:
        return {'n_boot': 0, 'raison': 'moins de vingt matchs'}
    rng = random.Random(20261026)
    gains = []
    for _ in range(n):
        ech = rng.choices(vals, k=len(vals))
        gains.append(sum(z[0] for z in ech) / sum(z[1] for z in ech))
    gains.sort()
    return {'ic95': [round(gains[int(q*(n-1))], 8) for q in (.025, .975)], 'n_boot': n}


def evaluer(lignes, coefs=None, n_boot=1000):
    rows, matchs = extraire(lignes, coefs)
    ids = sorted(set(matchs), key=lambda ix: lignes[ix]['t'])
    if len(ids) < 40:
        return {'statut': 'accumulation', 'matchs': len(ids), 'points': len(rows), 'candidats': {}}
    cut = ids[len(ids)//2]
    train, mt = _sous(rows, matchs, ids[:ids.index(cut)])
    test, mv = _sous(rows, matchs, ids[ids.index(cut):])
    base_train, base_test = [(n, k, off, []) for n, k, off, x in train], [(n, k, off, []) for n, k, off, x in test]
    out = {}
    for nom, feats in CANDIDATS.items():
        tr, te = _features(train, feats), _features(test, feats)
        b = FA.ajuster_logit(tr, len(feats))
        ll0, ll1 = _ll(base_test, []), _ll(te, b)
        # Version avec coefficients pour le bootstrap apparié.
        te_b = [(n, k, off, b) for n, k, off, x in te]
        out[nom] = {
            'variables': list(feats), 'coefficients_decouverte': [round(v, 6) for v in b],
            'decouverte': {'n_points': sum(r[0] for r in tr), 'log_loss_base': round(_ll(base_train, []), 6),
                           'log_loss_avec': round(_ll(tr, b), 6)},
            'confirmation': {'n_points': sum(r[0] for r in te), 'log_loss_base': round(ll0, 6),
                             'log_loss_avec': round(ll1, 6), 'gain': round(ll0-ll1, 8),
                             'bootstrap_matchs': _bootstrap(base_test, te_b, mv, n_boot)},
        }
    return {'statut': 'evalue', 'matchs': len(ids), 'points': len(rows), 'candidats': out,
            'decouverte_confirmation': 'première moitié chronologique / seconde moitié',
            'publication': 'interdite à ce stade : validation du vainqueur encore requise'}


def main(racine='.'):
    """Utilise les artefacts déjà produits par le pipeline hebdomadaire si présents."""
    path = os.path.join(racine, 'simulateur', 'lignes_facteurs.json')
    if not os.path.exists(path):
        out = {'statut': 'en_attente_pipeline', 'candidats': {},
               'raison': "Lancer via l'intégration facteurs : les lignes contiennent les séquences et les bases point-in-time."}
    else:
        lignes = json.load(open(path, encoding='utf-8'))
        try:
            coefs = json.load(open(os.path.join(racine, 'simulateur', 'facteurs.json'), encoding='utf-8')).get('coefs') or {}
        except (OSError, ValueError):
            coefs = {}
        out = evaluer(lignes, coefs)
    out['genere_le'] = dt.datetime.now(dt.timezone.utc).isoformat()
    path = os.path.join(racine, 'simulateur', 'rapport_dependances_points.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('Dépendances entre points :', out['statut'], flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--racine', default='.')
    args = ap.parse_args()
    main(args.racine)
