"""Challengers de recalibrage évalués en origine glissante, sans marché.

Chaque fenêtre est entraînée exclusivement sur les semaines antérieures, puis jugée sur
les deux semaines suivantes. Une variante n'est proposée qu'après au moins deux fenêtres
et deux confirmations directionnelles ; ce module ne modifie jamais le champion actif.
"""
import argparse
import bisect
import datetime as dt
import gzip
import json
import math
import os
from collections import defaultdict

import ablation as AB

MIN_TRAIN = 200
MIN_TEST = 30
MIN_FENETRES = 2
MARGE = .001
MODELES = ('logistique', 'contraction_hierarchique', 'isotone')


def _p(x):
    return min(max(float(x), 1e-6), 1-1e-6)


def _lg(x):
    p = _p(x)
    return math.log(p/(1-p))


def _sg(z):
    return 1/(1+math.exp(-max(-40, min(40, z))))


def _ll(rows, key='p'):
    if not rows:
        return None
    return sum(-(r['y']*math.log(_p(r[key]))+(1-r['y'])*math.log(_p(1-r[key]))) for r in rows)/len(rows)


def _features(r):
    return [1., _lg(r['pipeline_complet']), _lg(r['elo'])-_lg(r['simulation']),
            float(r.get('circuit') == 'ATP'), float(r.get('circuit') == 'WTA'), float(r.get('circuit') == 'CH')]


def fit_logistique(rows):
    X, Y = [_features(r) for r in rows], [r['y'] for r in rows]
    beta = [0., 1., 0., 0., 0., 0.]
    n = max(1, len(rows))
    for _ in range(500):
        grad = [0.]*len(beta)
        for x, y in zip(X, Y):
            e = _sg(sum(b*v for b, v in zip(beta, x)))-y
            for j, v in enumerate(x):
                grad[j] += e*v/n
        for j in range(2, len(beta)):
            grad[j] += .03*beta[j]
        for j in range(len(beta)):
            beta[j] -= .08*grad[j]
    return beta


def pred_logistique(beta, r):
    return _sg(sum(b*v for b, v in zip(beta, _features(r))))


def fit_contraction(rows):
    global_lam = min((x/100 for x in range(70, 111, 2)),
                     key=lambda lam: _ll([{'p': .5+lam*(r['pipeline_complet']-.5), 'y': r['y']} for r in rows]))
    groupes = defaultdict(list)
    for r in rows:
        groupes[r.get('circuit') or '?'].append(r)
    lambdas = {}
    for circuit, rr in groupes.items():
        lambdas[circuit] = global_lam if len(rr) < 100 else min(
            (x/100 for x in range(70, 111, 2)),
            key=lambda lam: _ll([{'p': .5+lam*(r['pipeline_complet']-.5), 'y': r['y']} for r in rr]))
    return {'global': global_lam, 'circuits': lambdas}


def pred_contraction(modele, r):
    lam = modele['circuits'].get(r.get('circuit') or '?', modele['global'])
    return _p(.5+lam*(r['pipeline_complet']-.5))


def _pava(rows):
    blocs = []
    for r in sorted(rows, key=lambda x: x['pipeline_complet']):
        p, y = r['pipeline_complet'], float(r['y'])
        blocs.append([p, p, 1., y, y])
        while len(blocs) > 1 and blocs[-2][4]/blocs[-2][2] > blocs[-1][4]/blocs[-1][2]:
            b, a = blocs.pop(), blocs.pop()
            blocs.append([a[0], b[1], a[2]+b[2], a[3]+b[3], a[4]+b[4]])
    return [(b[0], b[1], _p(b[4]/b[2])) for b in blocs]


def fit_isotone(rows):
    global_modele = _pava(rows)
    groupes = defaultdict(list)
    for r in rows:
        groupes[r.get('circuit') or '?'].append(r)
    return {'global': global_modele,
            'circuits': {c: _pava(rr) for c, rr in groupes.items() if len(rr) >= 200}}


def _pred_pava(blocs, p):
    if not blocs:
        return p
    if p <= blocs[0][0]:
        return blocs[0][2]
    if p >= blocs[-1][1]:
        return blocs[-1][2]
    i = min(len(blocs)-1, max(0, bisect.bisect_right([b[0] for b in blocs], p)-1))
    return blocs[i][2]


def pred_isotone(modele, r):
    return _pred_pava(modele['circuits'].get(r.get('circuit') or '?', modele['global']), r['pipeline_complet'])


def predire(nom, modele, rows):
    fn = {'logistique': pred_logistique, 'contraction_hierarchique': pred_contraction,
          'isotone': pred_isotone}[nom]
    return [dict(r, p=fn(modele, r)) for r in rows]


def entrainer(nom, rows):
    return {'logistique': fit_logistique, 'contraction_hierarchique': fit_contraction,
            'isotone': fit_isotone}[nom](rows)


def evaluer_lignes(rows, min_train=MIN_TRAIN, min_test=MIN_TEST):
    rows = sorted(rows, key=lambda r: r['debut'])
    semaines = sorted({r['semaine'] for r in rows})
    par_semaine = {s: [r for r in rows if r['semaine'] == s] for s in semaines}
    fenetres = []
    # Avance de deux semaines : les périodes de test ne se chevauchent pas.
    for i in range(0, len(semaines)-2, 2):
        train = [r for s in semaines[:i+1] for r in par_semaine[s]]
        test_semaines = semaines[i+1:i+3]
        test = [r for s in test_semaines for r in par_semaine[s]]
        if len(train) < min_train or len(test) < min_test:
            continue
        base = _ll([dict(r, p=r['pipeline_complet']) for r in test])
        resultats = {}
        for nom in MODELES:
            pred = predire(nom, entrainer(nom, train), test)
            resultats[nom] = {'log_loss': _ll(pred), 'gain': base-_ll(pred)}
        fenetres.append({'train_n': len(train), 'test_n': len(test), 'semaines_test': test_semaines,
                         'champion_log_loss': base, 'challengers': resultats})
    decisions = {}
    for nom in MODELES:
        gains = [f['challengers'][nom]['gain'] for f in fenetres]
        n_test = sum(f['test_n'] for f in fenetres)
        gain_global = (sum(g*f['test_n'] for g, f in zip(gains, fenetres))/n_test) if n_test else None
        assez = len(fenetres) >= MIN_FENETRES
        adopte = assez and gain_global >= MARGE and sum(g > 0 for g in gains) >= MIN_FENETRES
        decisions[nom] = {'adopte': bool(adopte), 'gain_log_loss_pondere': gain_global,
                          'fenetres_positives': sum(g > 0 for g in gains), 'fenetres': len(fenetres),
                          'statut': 'confirmation' if assez else 'accumulation',
                          'regle': 'au moins deux fenêtres, deux gains positifs et gain pondéré >= 0,001'}
    return {'n': len(rows), 'semaines': len(semaines), 'population': 'premiers pronostics figés et résultats ultérieurs',
            'marche_utilise': False, 'fenetres_details': fenetres, 'decisions': decisions,
            'champion_actif_modifie': False}


def evaluer(doc, min_train=MIN_TRAIN, min_test=MIN_TEST):
    return evaluer_lignes(AB.observations(doc), min_train, min_test)


def observations_rejouees(racine='.'):
    """Pronostics hors échantillon figés ; population conservée séparée du direct."""
    path = os.path.join(racine, 'simulateur', 'pronostics_hors_echantillon.jsonl.gz')
    out = []
    try:
        with gzip.open(path, 'rt', encoding='utf-8') as fh:
            for ligne in fh:
                r = json.loads(ligne)
                if any(r.get(k) is None for k in ('p_algo', 'p_elo', 'p_sim', 'gagnant', 't')):
                    continue
                debut = dt.datetime.fromtimestamp(r['t'], dt.timezone.utc)
                out.append({'uid': str(r.get('id')), 'debut': debut.isoformat(),
                            'semaine': AB._semaine(debut.date().isoformat()),
                            'circuit': r.get('circuit') or '?', 'y': int(r['gagnant'] == 'home'),
                            'elo': _p(r['p_elo']), 'simulation': _p(r['p_sim']),
                            'pipeline_complet': _p(r['p_algo'])})
    except (OSError, ValueError):
        return []
    return out


def main(racine='.'):
    try:
        doc = json.load(open(os.path.join(racine, AB.RESULTATS), encoding='utf-8'))
    except (OSError, ValueError):
        doc = {}
    direct = evaluer(doc)
    rejoue = evaluer_lignes(observations_rejouees(racine))
    out = {'populations_separees': True, 'direct': direct, 'rejoue': rejoue,
           'n': direct['n'], 'decisions': direct['decisions'],
           'regle_populations': 'le direct et le rejoué ne sont jamais agrégés ; aucune promotion automatique',
           'genere_le': dt.datetime.now(dt.timezone.utc).isoformat()}
    path = os.path.join(racine, 'simulateur', 'rapport_recalibrage.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('Recalibrage :', {k: v['statut'] for k, v in out['decisions'].items()}, flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--racine', default='.')
    args = ap.parse_args()
    main(args.racine)
