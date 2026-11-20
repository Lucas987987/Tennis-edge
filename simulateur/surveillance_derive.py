"""Surveillance de la dérive sur les premiers pronostics pré-match figés.

Fenêtres de 4, 8 et 12 semaines comparées à la période immédiatement précédente.
Aucune donnée postérieure au match ne modifie une probabilité ; les alertes ne
déclenchent ni réapprentissage ni promotion automatique.
"""
import argparse
import datetime as dt
import json
import math
import os

import ablation as AB

FENETRES = (4, 8, 12)
MIN_MATCHS = 30
SEUIL_LOG_LOSS = .05
SEUIL_BRIER = .01
SEUIL_CONFIDENCE = .10


def _jour(m):
    return dt.datetime.fromisoformat(str(m['debut']).replace('Z', '+00:00')).date()


def preparer(resultats, version='combinaison'):
    utilisables, rejetes = AB.utilisables(resultats, version)
    rows = []
    for m in utilisables:
        p = min(1-1e-12, max(1e-12, float(m['prevus'][version]['p_home'])))
        y = int(m['gagnant'] == 'home')
        contexte = m.get('profil_contexte') or {}
        effectifs = contexte.get('n_balles_effectives') or []
        documente = None
        if len(effectifs) == 2 and all(isinstance(x, (int, float)) for x in effectifs):
            documente = 'peu_documente' if min(effectifs) < 500 else 'documente'
        rows.append({'uid': m['uid'], 'date': _jour(m), 'p': p, 'y': y,
                     'circuit': m.get('circuit') or 'inconnu', 'surface': m.get('surface') or 'inconnue',
                     'format': f"BO{m.get('meilleur_des', 3)}", 'documentation': documente})
    return rows, rejetes


def metriques(rows):
    if not rows:
        return {'n': 0, 'semaines': 0}
    ll = [-(r['y'] * math.log(r['p']) + (1-r['y']) * math.log(1-r['p'])) for r in rows]
    br = [(r['p']-r['y'])**2 for r in rows]
    exact = [(r['p'] >= .5) == bool(r['y']) for r in rows]
    confiance = [max(r['p'], 1-r['p']) for r in rows]
    return {'n': len(rows), 'semaines': len({r['date'].isocalendar()[:2] for r in rows}),
            'du': min(r['date'] for r in rows).isoformat(), 'au': max(r['date'] for r in rows).isoformat(),
            'log_loss': round(sum(ll)/len(ll), 6), 'brier': round(sum(br)/len(br), 6),
            'exactitude': round(sum(exact)/len(exact), 6),
            'confiance_moyenne': round(sum(confiance)/len(confiance), 6),
            'ecart_confiance_exactitude': round(sum(confiance)/len(confiance)-sum(exact)/len(exact), 6)}


def comparer(courant, precedent):
    c, p = metriques(courant), metriques(precedent)
    out = {'courant': c, 'precedent': p, 'alertes': []}
    if not c['n'] or not p['n']:
        out['statut'] = 'accumulation'
        return out
    out['delta_log_loss'] = round(c['log_loss']-p['log_loss'], 6)
    out['delta_brier'] = round(c['brier']-p['brier'], 6)
    assez = c['n'] >= MIN_MATCHS and p['n'] >= MIN_MATCHS
    if assez and out['delta_log_loss'] >= SEUIL_LOG_LOSS and out['delta_brier'] >= SEUIL_BRIER:
        out['alertes'].append('degradation_log_loss_et_brier')
    if c['n'] >= MIN_MATCHS and abs(c['ecart_confiance_exactitude']) >= SEUIL_CONFIDENCE:
        out['alertes'].append('surconfiance' if c['ecart_confiance_exactitude'] > 0 else 'sous_confiance')
    out['statut'] = 'alerte' if out['alertes'] else ('surveillance' if assez else 'accumulation')
    return out


def _periode(rows, fin, semaines):
    debut = fin - dt.timedelta(days=7*semaines-1)
    return [r for r in rows if debut <= r['date'] <= fin]


def _groupes(rows):
    out = {'global': rows}
    for champ in ('surface', 'circuit', 'format', 'documentation'):
        for valeur in sorted({r[champ] for r in rows if r[champ] is not None}):
            out[f'{champ}:{valeur}'] = [r for r in rows if r[champ] == valeur]
    return out


def evaluer(resultats, version='combinaison'):
    rows, rejetes = preparer(resultats, version)
    if not rows:
        return {'version': version, 'statut': 'accumulation', 'n': 0, 'fenetres': {}, 'groupes_12_semaines': {},
                'regle': 'Au moins 30 matchs par période ; aucune action automatique.'}
    fin = max(r['date'] for r in rows)
    fenetres = {}
    for n in FENETRES:
        limite = fin - dt.timedelta(days=7*n)
        courant = _periode(rows, fin, n)
        precedent = [r for r in rows if limite-dt.timedelta(days=7*n-1) <= r['date'] <= limite]
        fenetres[f'{n}_semaines'] = comparer(courant, precedent)
    groupes = {}
    for nom, rr in _groupes(rows).items():
        limite = fin - dt.timedelta(days=84)
        courant = _periode(rr, fin, 12)
        precedent = [r for r in rr if limite-dt.timedelta(days=83) <= r['date'] <= limite]
        groupes[nom] = comparer(courant, precedent)
    alertes_globales = any(v['alertes'] for v in fenetres.values())
    alertes_groupes = any(v['alertes'] for k, v in groupes.items() if k != 'global')
    comparaison_global_disponible = any(v['statut'] in ('surveillance', 'alerte') for v in fenetres.values())
    statut = ('alerte' if alertes_globales else 'alerte_sous_groupe' if alertes_groupes
              else 'surveillance' if comparaison_global_disponible else 'accumulation')
    return {
        'version': version, 'statut': statut, 'n': len(rows), 'rejetes': len(rejetes),
        'date_de_reference': fin.isoformat(), 'fenetres': fenetres, 'groupes_12_semaines': groupes,
        'seuils': {'minimum_matchs_par_periode': MIN_MATCHS, 'delta_log_loss': SEUIL_LOG_LOSS,
                   'delta_brier': SEUIL_BRIER, 'ecart_confiance_absolu': SEUIL_CONFIDENCE},
        'regle': ('Dégradation signalée si log loss et Brier franchissent tous deux leurs seuils ; '
                  'sur/sous-confiance si |confiance - exactitude| >= 0,10. Sous-groupes sur 12 semaines.'),
        'action': 'Alerte diagnostique seulement : réévaluation contrôlée, jamais de modification automatique du champion.',
    }


def main(racine='.'):
    try:
        resultats = json.load(open(os.path.join(racine, AB.RESULTATS), encoding='utf-8'))
    except (OSError, ValueError):
        resultats = {}
    out = evaluer(resultats)
    out['genere_le'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    path = os.path.join(racine, 'simulateur', 'rapport_surveillance_derive.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('Surveillance dérive :', out['statut'], out['n'], 'matchs', flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--racine', default='.')
    args = ap.parse_args()
    main(args.racine)
