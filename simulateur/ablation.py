#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ablation appariée des modèles indépendants sur nos pronostics pré-match figés.

Les quatre modèles sont évalués sur EXACTEMENT les mêmes matchs :
  - elo : Elo seul ;
  - simulation : simulation pure ;
  - combinaison_base : mélange logit 50/50, sans correction ;
  - pipeline_complet : combinaison adoptée, sinon simulation, sinon Elo.

La combinaison de base est une référence fixe et non les poids réappris : les anciens
journaux ne contiennent pas toujours les composantes ayant produit la combinaison complète.
Les intervalles à 95 % sont un bootstrap par semaine ISO (les matchs d'une même semaine
restent ensemble). Une différence positive signifie que le pipeline complet est meilleur.

Usage : python simulateur/ablation.py [racine] [--bootstrap 2000]
"""
import argparse
import datetime as dt
import json
import math
import os
import random
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import match_simule as MS  # noqa: E402

MODELES = ('elo', 'simulation', 'combinaison_base', 'pipeline_complet')
RESULTATS = os.path.join('Tennis_Edge_Lab', 'live', 'pronostics_resultats.json')
SORTIE = os.path.join('simulateur', 'rapport_ablation.json')


def _p(x):
    return min(max(float(x), 1e-6), 1 - 1e-6)


def _semaine(debut):
    d = dt.date.fromisoformat(str(debut)[:10])
    annee, semaine, _ = d.isocalendar()
    return f'{annee}-S{semaine:02d}'



def utilisables(doc, version='combinaison'):
    """Matchs figés utilisables pour une version, avec rejet explicite des entrées invalides.

    Accepte le document complet ou sa liste de matchs. Contrairement à observations(),
    conserve les sorties détaillées et les métadonnées nécessaires aux autres audits.
    """
    source = (doc or {}).get('matchs') if isinstance(doc, dict) else (doc or [])
    out, rejetes, vus = [], [], set()
    for m in source:
        uid = m.get('uid')
        reel = m.get('reel') or {}
        premier = m.get('premier') or {}
        prevu = premier.get(version) or {}
        if (not uid or uid in vus or not m.get('debut') or reel.get('interrompu')
                or reel.get('gagnant') not in ('home', 'away')
                or not isinstance(prevu.get('p_home'), (int, float))):
            rejetes.append(m)
            continue
        vus.add(uid)
        ligne = dict(m, gagnant=reel['gagnant'], prevus=premier)
        out.append(ligne)
    return sorted(out, key=lambda r: r['debut']), rejetes

def observations(doc):
    """Une ligne par match, avec les quatre probabilités home et le résultat."""
    out, vus = [], set()
    for m in (doc or {}).get('matchs') or []:
        uid = m.get('uid')
        reel = m.get('reel') or {}
        if not uid or uid in vus or reel.get('interrompu') or reel.get('gagnant') not in ('home', 'away'):
            continue
        premier = m.get('premier') or {}
        elo, sim = premier.get('stats') or {}, premier.get('simulation') or {}
        if elo.get('p_home') is None or sim.get('p_home') is None:
            continue
        pe, ps = _p(elo['p_home']), _p(sim['p_home'])
        bloc = next((premier.get(k) for k in ('combinaison', 'simulation', 'stats')
                     if (premier.get(k) or {}).get('p_home') is not None), None)
        if bloc is None:
            continue
        vus.add(uid)
        out.append({'uid': uid, 'debut': m['debut'], 'semaine': _semaine(m['debut']),
                    'circuit': m.get('circuit') or '?', 'y': int(reel['gagnant'] == 'home'),
                    'elo': pe, 'simulation': ps,
                    'combinaison_base': MS.melange({'elo': 0.5, 'simulation': 0.5}, pe, ps),
                    'pipeline_complet': _p(bloc['p_home'])})
    return sorted(out, key=lambda r: r['uid'])


def mesures(lignes, modele):
    n = len(lignes)
    if not n:
        return {'n': 0}
    ll = brier = exact = 0.0
    for r in lignes:
        p, y = r[modele], r['y']
        ll += -(y * math.log(p) + (1 - y) * math.log(1 - p))
        brier += (p - y) ** 2
        exact += (p > 0.5) == bool(y)
    return {'n': n, 'log_loss': ll / n, 'brier': brier / n, 'reussite_pct': 100 * exact / n}


def _public(m):
    return {'n': m['n'], **({k: round(m[k], 5) for k in ('log_loss', 'brier', 'reussite_pct')} if m['n'] else {})}


def _difference(lignes, autre, metrique):
    cle = 'log_loss' if metrique == 'log_loss' else 'brier'
    return mesures(lignes, autre)[cle] - mesures(lignes, 'pipeline_complet')[cle]


def _bootstrap(lignes, autre, repetitions, rnd):
    groupes = {}
    for r in lignes:
        groupes.setdefault(r['semaine'], []).append(r)
    semaines = sorted(groupes)
    if len(semaines) < 2 or repetitions <= 0:
        return {'log_loss': None, 'brier': None}
    valeurs = {'log_loss': [], 'brier': []}
    for _ in range(repetitions):
        echantillon = [r for s in (rnd.choice(semaines) for _ in semaines) for r in groupes[s]]
        for metrique in valeurs:
            valeurs[metrique].append(_difference(echantillon, autre, metrique))
    out = {}
    for metrique, vals in valeurs.items():
        vals.sort()
        out[metrique] = {'bas': round(vals[int(0.025 * (len(vals) - 1))], 5),
                         'haut': round(vals[int(0.975 * (len(vals) - 1))], 5)}
    return out


def analyser(doc, bootstrap=2000, graine=20261026):
    lignes = observations(doc)
    out = {'n': len(lignes), 'semaines': len({r['semaine'] for r in lignes}),
           'source': 'premiers pronostics pré-match figés',
           'population': 'mêmes matchs pour les quatre modèles ; abandons, forfaits et entrées incomplètes exclus',
           'combinaison_base': 'mélange logit fixe 50 % Elo / 50 % simulation',
           'bootstrap': {'unite': 'semaine ISO', 'repetitions': bootstrap},
           'avertissement': ('Moins de 8 semaines : intervalles exploratoires, pas une preuve de supériorité.'
                             if len({r['semaine'] for r in lignes}) < 8 else None),
           'modeles': {k: _public(mesures(lignes, k)) for k in MODELES}, 'comparaisons': {}}
    rnd = random.Random(graine)
    for autre in MODELES[:-1]:
        intervalles = _bootstrap(lignes, autre, bootstrap, rnd)
        out['comparaisons'][f'pipeline_complet_contre_{autre}'] = {
            'difference': {k: round(_difference(lignes, autre, k), 5) for k in ('log_loss', 'brier')},
            'ic95': intervalles,
            'sens': 'positif = pipeline complet meilleur (perte de l’autre moins perte du pipeline)'}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('racine', nargs='?', default=os.path.join(ICI, '..'))
    ap.add_argument('--bootstrap', type=int, default=2000)
    args = ap.parse_args(argv)
    try:
        with open(os.path.join(args.racine, RESULTATS), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        doc = {}
    rapport = analyser(doc, bootstrap=max(args.bootstrap, 0))
    rapport['genere_le'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    chemin = os.path.join(args.racine, SORTIE)
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(rapport, f, ensure_ascii=False, indent=1)
    print(f"Ablation appariée : {rapport['n']} matchs, {rapport['semaines']} semaines → {SORTIE}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
