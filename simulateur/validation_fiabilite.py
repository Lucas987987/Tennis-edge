"""Validation hors échantillon de la note de fiabilité affichée avec chaque match.

La note n'est ni recalculée avec le résultat ni optimisée ici : on vérifie si les
notes figées avant le match ordonnent réellement les performances ultérieures.
"""
import argparse
import datetime as dt
import json
import math
import os
from collections import defaultdict

import random

import ablation as AB
import fiabilite as FI

MIN_MATCHS = 30
MIN_SEMAINES = 4


def _wilson(reussites, n, z=1.96):
    if not n:
        return None
    p = reussites / n
    den = 1 + z*z/n
    centre = (p + z*z/(2*n)) / den
    marge = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return [round(centre-marge, 6), round(centre+marge, 6)]


def _metriques(rows):
    if not rows:
        return {'n': 0, 'semaines': 0}
    ll = [-math.log(min(1 - 1e-12, max(1e-12, r['p'] if r['y'] else 1-r['p']))) for r in rows]
    br = [(r['p'] - r['y']) ** 2 for r in rows]
    calibration = []
    for i in range(5):
        lo = i / 5
        rr = [r for r in rows if lo <= r['p'] < lo + .2 or (lo == .8 and r['p'] == 1)]
        if rr:
            calibration.append({'bas': round(lo, 1), 'haut': round(lo+.2, 1), 'n': len(rr),
                                'prevu': round(sum(r['p'] for r in rr)/len(rr), 4),
                                'reel': round(sum(r['y'] for r in rr)/len(rr), 4)})
    exactes = sum((r['p'] >= .5) == bool(r['y']) for r in rows)
    attendue = sum(max(r['p'], 1-r['p']) for r in rows) / len(rows)
    return {
        'n': len(rows), 'semaines': len({r['semaine'] for r in rows}),
        'note_moyenne': round(sum(r['note'] for r in rows)/len(rows), 2),
        'log_loss': round(sum(ll)/len(ll), 6), 'brier': round(sum(br)/len(br), 6),
        'vainqueur_exact': round(exactes/len(rows), 6),
        'ic95_exactitude_wilson': _wilson(exactes, len(rows)),
        'exactitude_attendue': round(attendue, 6),
        'ecart_exactitude_moins_attendue': round(exactes/len(rows)-attendue, 6),
        'calibration': calibration,
    }


def _bootstrap(haut, bas, n=2000):
    """Différence de log loss haut-bas par semaine ; négatif = note élevée meilleure."""
    semaines = sorted({r['semaine'] for r in haut+bas})
    if len(semaines) < MIN_SEMAINES:
        return {'n_boot': 0, 'raison': 'moins de quatre semaines'}
    H = defaultdict(list)
    B = defaultdict(list)
    for r in haut:
        H[r['semaine']].append(r)
    for r in bas:
        B[r['semaine']].append(r)
    # Une semaine n'entre que si les deux groupes y sont observés, pour un contraste apparié.
    semaines = [s for s in semaines if H[s] and B[s]]
    if len(semaines) < MIN_SEMAINES:
        return {'n_boot': 0, 'raison': 'moins de quatre semaines appariées'}
    def ll(rows):
        vals = [-math.log(min(1-1e-12, max(1e-12, r['p'] if r['y'] else 1-r['p']))) for r in rows]
        return sum(vals)/len(vals)
    deltas = [ll(H[s])-ll(B[s]) for s in semaines]
    rng = random.Random(20261026)
    boot = [sum(rng.choices(deltas, k=len(deltas))) / len(deltas) for _ in range(n)]
    trie = sorted(boot)
    return {'semaines_appariees': len(semaines), 'difference_haut_moins_bas': round(sum(deltas)/len(deltas), 6),
            'ic95': [round(trie[int(q*(n-1))], 6) for q in (.025, .975)],
            'probabilite_haut_meilleur': round(sum(x < 0 for x in boot)/n, 4), 'n_boot': n}



def _rangs(vals):
    """Rangs moyens, égalités comprises (équivalent Spearman sans SciPy)."""
    ordre = sorted(range(len(vals)), key=lambda i: vals[i])
    out = [0.0] * len(vals)
    i = 0
    while i < len(ordre):
        j = i + 1
        while j < len(ordre) and vals[ordre[j]] == vals[ordre[i]]:
            j += 1
        rang = (i + j - 1) / 2 + 1
        for k in range(i, j):
            out[ordre[k]] = rang
        i = j
    return out


def _spearman(a, b):
    a, b = _rangs(a), _rangs(b)
    ma, mb = sum(a)/len(a), sum(b)/len(b)
    num = sum((x-ma)*(y-mb) for x, y in zip(a, b))
    da = sum((x-ma)**2 for x in a)
    db = sum((y-mb)**2 for y in b)
    return num/math.sqrt(da*db) if da > 0 and db > 0 else None

def preparer(resultats, version='combinaison'):
    utilisables, _ = AB.utilisables(resultats, version)
    rows = []
    for m in utilisables:
        f = m.get('fiabilite') or (m.get('prevus', {}).get(version) or {}).get('fiabilite')
        if not isinstance(f, dict) or not isinstance(f.get('note'), (int, float)):
            continue
        v = m['prevus'][version]
        d = dt.datetime.fromisoformat(m['debut'].replace('Z', '+00:00'))
        rows.append({'note': float(f['note']), 'p': float(v['p_home']),
                     'y': int(m['gagnant'] == 'home'), 'semaine': d.isocalendar()[:2],
                     'categorie': f.get('categorie') or 'D_non_controle',
                     'desaccord': bool(f.get('desaccord_vainqueur_elo_simulation'))})
    return rows


def evaluer(resultats, version='combinaison'):
    rows = preparer(resultats, version)
    par_niveau = {niveau: _metriques([r for r in rows if FI.niveau(r['note']) == niveau])
                  for niveau in FI.NIVEAUX}
    par_categorie = {cat: _metriques([r for r in rows if r['categorie'] == cat])
                     for cat in FI.CATEGORIES}
    desaccords = {str(v): _metriques([r for r in rows if r['desaccord'] is v]) for v in (False, True)}
    bas = [r for r in rows if r['note'] < FI.SEUILS['correct']]
    haut = [r for r in rows if r['note'] >= FI.SEUILS['correct']]
    notes = sorted({r['note'] for r in rows})
    monotone = None
    if len(notes) >= 2 and len(rows) >= MIN_MATCHS:
        # Corrélation de Spearman : une note élevée doit être associée à une perte faible.
        nr = [r['note'] for r in rows]
        perte = [-math.log(min(1-1e-12, max(1e-12, r['p'] if r['y'] else 1-r['p']))) for r in rows]
        rho = _spearman(nr, perte)
        monotone = round(rho, 6) if rho is not None else None
    contraste = _bootstrap(haut, bas)
    groupes_assez = sum(v['n'] >= 10 for v in par_niveau.values())
    pret = (len(bas) >= MIN_MATCHS and len(haut) >= MIN_MATCHS
            and contraste.get('n_boot', 0) > 0 and groupes_assez >= 2)
    probabilite = contraste.get('probabilite_haut_meilleur')
    if not pret:
        verdict = 'accumulation'
    elif probabilite >= .95 and (monotone is None or monotone < 0):
        verdict = 'confirmees'
    elif probabilite <= .05:
        verdict = 'contredites'
    else:
        verdict = 'non_concluant'
    return {
        'version': version, 'n_avec_note': len(rows), 'global': _metriques(rows),
        'par_niveau': par_niveau, 'par_categorie': par_categorie,
        'par_desaccord_elo_simulation': desaccords,
        'contraste_correct_ou_solide_vs_fragile_ou_prudent': contraste,
        'effectifs_contraste': {'notes_fragile_ou_prudent': len(bas), 'notes_correct_ou_solide': len(haut)},
        'spearman_note_vs_perte': monotone,
        'statut': 'interpretable' if pret else 'accumulation', 'verdict_notes': verdict,
        'regle': ("Au moins 30 matchs dans chacun des deux groupes de notes et quatre semaines appariées. "
                  "Notes confirmées seulement si P(hautes notes meilleures) >= 95 % et Spearman négatif ; "
                  "contredites si cette probabilité <= 5 % ; non concluant sinon. Aucune modification automatique."),
        'interpretation_spearman': 'Une valeur négative est souhaitée : note haute, perte faible.',
    }


def main(racine='.'):
    path = os.path.join(racine, AB.RESULTATS)
    try:
        resultats = json.load(open(path, encoding='utf-8'))
    except (OSError, ValueError):
        resultats = {}
    out = evaluer(resultats)
    out['genere_le'] = dt.datetime.now(dt.timezone.utc).isoformat()
    path = os.path.join(racine, 'simulateur', 'rapport_validation_fiabilite.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('Validation fiabilité :', out['statut'], out['n_avec_note'], 'matchs', flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--racine', default='.')
    args = ap.parse_args()
    main(args.racine)
