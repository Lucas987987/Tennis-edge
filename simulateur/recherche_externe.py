"""Recherche EXTERNE : algorithme indépendant × marché × H13–H19.

Les probabilités indépendantes sont des offsets figés. Les cotes sont censurées au
moment du pronostic puis au début ; les signaux sont censurés à ces deux instants.
Aucun résultat de ce module n'est réinjecté dans le modèle indépendant.
"""
import argparse
import datetime as dt
import glob
import json
import math
import os
from collections import defaultdict

import ablation as AB
import elo as E

CODES = ('H13', 'H14', 'H15', 'H16', 'H16B', 'H17', 'H18', 'H19')
FICHIERS = {'H16B': 'h16b_signal_log.jsonl', **{c: f'{c.lower()}_signal_log.jsonl' for c in CODES if c != 'H16B'}}


def _date(x):
    if not x:
        return None
    try:
        d = dt.datetime.fromisoformat(str(x).replace('Z', '+00:00'))
        return d.replace(tzinfo=dt.timezone.utc) if d.tzinfo is None else d.astimezone(dt.timezone.utc)
    except ValueError:
        return None


def _lire_jsonl(path):
    out = []
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def _paire(a, b):
    return tuple(sorted((E.cle(a), E.cle(b))))


def charger_courbes(racine):
    brut = []
    for p in glob.glob(os.path.join(racine, 'clv_history', '*.jsonl')) + glob.glob(os.path.join(racine, 'clv_history.jsonl')):
        brut.extend(_lire_jsonl(p))
    # Les exports mensuels et le fichier consolidé peuvent contenir le même match.
    uniques = {}
    for r in brut:
        if r.get('home_curve') and r.get('away_curve') and _date(r.get('commence_time')):
            uniques[(r.get('uid'), r.get('fixture_id'), r.get('commence_time'))] = r
    index = defaultdict(list)
    for r in uniques.values():
        index[_paire(r.get('home'), r.get('away'))].append(r)
    return index


def courbe_avant(points, cutoff):
    vals = [(_date(t), float(c)) for t, c in points if _date(t) and _date(t) < cutoff and isinstance(c, (int, float)) and c > 1]
    return vals[-1] if vals else None


def probabilite_sans_marge(oh, oa):
    if not oh or not oa or min(oh, oa) <= 1:
        return None
    ih, ia = 1/oh, 1/oa
    return ih/(ih+ia)


def _lg(p):
    p = min(1-1e-9, max(1e-9, p))
    return math.log(p/(1-p))


def mouvement(row, pronostique, debut):
    """Dernière probabilité disponible avant chaque instant ; jamais la clôture en aveugle."""
    at_h, at_a = courbe_avant(row['home_curve'], pronostique), courbe_avant(row['away_curve'], pronostique)
    pre_h, pre_a = courbe_avant(row['home_curve'], debut), courbe_avant(row['away_curve'], debut)
    p0, p1 = probabilite_sans_marge(at_h[1] if at_h else None, at_a[1] if at_a else None), probabilite_sans_marge(pre_h[1] if pre_h else None, pre_a[1] if pre_a else None)
    if p0 is None or p1 is None:
        return None
    return {'feature': _lg(p1)-_lg(p0), 'p_au_pronostic': p0, 'p_avant_debut': p1,
            'horodatage_pronostic': max(at_h[0], at_a[0]).isoformat(),
            'horodatage_avant_debut': max(pre_h[0], pre_a[0]).isoformat()}


def associer_courbe(m, index):
    debut, pronostique = _date(m.get('debut')), _date(m.get('pronostique_le'))
    if not debut or not pronostique:
        return None
    candidats = index.get(_paire(m.get('home'), m.get('away')), [])
    meilleurs = []
    for r in candidats:
        d = _date(r.get('commence_time'))
        ecart = abs((d-debut).total_seconds()) if d else float('inf')
        if ecart <= 12*3600:
            meilleurs.append((ecart, r))
    if not meilleurs:
        return None
    row = min(meilleurs, key=lambda z: z[0])[1]
    inverse = E.cle(row.get('home')) != E.cle(m.get('home'))
    if inverse:
        row = dict(row, home_curve=row['away_curve'], away_curve=row['home_curve'])
    return mouvement(row, pronostique, debut)


def charger_signaux(racine):
    out = {}
    for code, nom in FICHIERS.items():
        rows = _lire_jsonl(os.path.join(racine, nom))
        index = defaultdict(list)
        for r in rows:
            if _date(r.get('detecte_le')) and _date(r.get('commence')):
                index[_paire(r.get('joueur'), r.get('adversaire'))].append(r)
        out[code] = index
    return out


def signal_avant(m, index):
    debut, pronostique = _date(m.get('debut')), _date(m.get('pronostique_le'))
    if not debut or not pronostique:
        return None
    cutoff = min(debut, pronostique)
    possibles = []
    for r in index.get(_paire(m.get('home'), m.get('away')), []):
        disponible = _date(r.get('signale_le') or r['detecte_le'])
        if disponible and disponible < cutoff and abs((_date(r['commence'])-debut).total_seconds()) <= 12*3600:
            possibles.append(r)
    if not possibles:
        return None
    r = max(possibles, key=lambda z: _date(z['detecte_le']))
    return 1 if E.cle(r.get('joueur')) == E.cle(m.get('home')) else -1


def ajuster(rows, ridge=10.0):
    """Une variable, offset = logit du pronostic indépendant ; retourne beta, erreur-type, p-value."""
    beta = 0.0
    for _ in range(30):
        grad, hess = -ridge*beta, ridge
        for off, x, y in rows:
            p = 1/(1+math.exp(-max(-30, min(30, off+beta*x))))
            grad += x*(y-p)
            hess += x*x*p*(1-p)
        pas = grad/hess
        beta += pas
        if abs(pas) < 1e-8:
            break
    p = 1/(1+math.exp(-max(-30, min(30, beta))))
    se = math.sqrt(1/max(1e-12, hess))
    z = beta/se
    return beta, se, math.erfc(abs(z)/math.sqrt(2))


def metriques(rows, beta):
    if not rows:
        return {'n': 0}
    def ll(b):
        vals = []
        for off, x, y in rows:
            p = 1/(1+math.exp(-max(-30, min(30, off+b*x))))
            vals.append(-math.log(min(1-1e-12, max(1e-12, p if y else 1-p))))
        return sum(vals)/len(vals)
    return {'n': len(rows), 'n_actifs': sum(x != 0 for _, x, _ in rows),
            'log_loss_base': round(ll(0), 6), 'log_loss_avec': round(ll(beta), 6), 'gain': round(ll(0)-ll(beta), 6)}


def holm(candidats):
    actifs = [(nom, r['decouverte']['p_value']) for nom, r in candidats.items() if r['decouverte'].get('p_value') is not None]
    actifs.sort(key=lambda z: z[1])
    running = 0.0
    for i, (nom, p) in enumerate(actifs):
        running = max(running, min(1.0, (len(actifs)-i)*p))
        candidats[nom]['decouverte']['p_holm'] = running


def evaluer(matchs, courbes, signaux, version='combinaison'):
    utilisables, _ = AB.utilisables(matchs, version)
    rows = []
    for m in utilisables:
        p = m['prevus'][version]['p_home']
        debut = _date(m.get('debut'))
        if not debut:
            continue
        base = {'off': _lg(p), 'y': int(m['gagnant'] == 'home'), 'debut': debut,
                'marche': 0.0, **{c: 0 for c in CODES}}
        mv = associer_courbe(m, courbes)
        if mv:
            base['marche'] = mv['feature']
        for code in CODES:
            base[code] = signal_avant(m, signaux[code]) or 0
        rows.append(base)
    ids = sorted(range(len(rows)), key=lambda i: rows[i]['debut'])
    cut = len(ids)//2
    candidats = {}
    for nom in ('marche',)+CODES:
        R = [(r['off'], r[nom], r['y']) for r in rows]
        train = [R[i] for i in ids[:cut]]
        test = [R[i] for i in ids[cut:]]
        beta, se, pv = ajuster(train) if train else (0.0, 0.0, None)
        beta_conf = ajuster(test)[0] if test else 0.0
        d = metriques(train, beta)
        d.update({'beta': round(beta, 6), 'erreur_type': round(se, 6), 'p_value': pv})
        c = metriques(test, beta)
        c['beta_reappris_diagnostic'] = round(beta_conf, 6)
        candidats[nom] = {'decouverte': d, 'confirmation': c}
    holm(candidats)
    for nom, r in candidats.items():
        d, c = r['decouverte'], r['confirmation']
        suffisant = d['n'] >= 100 and c['n'] >= 100 and d['n_actifs'] >= 30 and c['n_actifs'] >= 30
        confirme = bool(suffisant and (d.get('p_holm') or 1) < .05 and c['gain'] > 0
                          and d['beta']*c['beta_reappris_diagnostic'] > 0)
        r['statut'] = 'confirme_exploratoire' if confirme else 'non_confirme'
        if not suffisant:
            r['raison'] = 'échantillon insuffisant : 100 matchs et 30 signaux actifs par période requis'
    return {'n_matchs': len(rows), 'candidats': candidats,
            'protocole': 'Découverte puis confirmation chronologiques ; Holm sur les neuf tests ; beta figé pour la confirmation.',
            'limites': ['Aucun volume de transactions disponible.', 'Aucun consensus multi-bookmakers imposé par les données actuelles.',
                        'Un mouvement de cotes ne démontre ni information privilégiée ni pari certain.',
                        'Aucune réinjection dans les probabilités indépendantes.']}


def main(racine='.'):
    path = os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json')
    try:
        doc = json.load(open(path, encoding='utf-8'))
        matchs = doc
    except (OSError, ValueError):
        matchs = []
    out = evaluer(matchs, charger_courbes(racine), charger_signaux(racine))
    out['genere_le'] = dt.datetime.now(dt.timezone.utc).isoformat()
    path = os.path.join(racine, 'simulateur', 'rapport_recherche_externe.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('Recherche externe :', out['n_matchs'], 'matchs indépendants ; aucune réinjection', flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--racine', default='.')
    args = ap.parse_args()
    main(args.racine)
