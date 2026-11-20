"""Évalue toutes les sorties figées : vainqueur, sets, scores, jeux et feuilles.

Aucune donnée de marché n'est lue. Seuls les premiers pronostics pré-match et les
résultats effectivement raccordés sont utilisés ; les métriques de scores ou de
statistiques restent absentes lorsque la donnée réelle correspondante manque.
"""
import argparse
import datetime as dt
import json
import math
import os
from collections import defaultdict

import ablation as AB
import fiabilite as FI

EPS = 1e-12
VERSIONS = ('combinaison', 'simulation', 'stats')
STATS = ('premiere_pct', 'gagnes_1re_pct', 'gagnes_2e_pct', 'aces', 'doubles_fautes', 'breaks', 'jeux')


def _loss(p):
    return -math.log(min(1.0 - EPS, max(EPS, p)))


def _resume(vals):
    vals = [v for v in vals if v is not None and math.isfinite(v)]
    return {'n': len(vals), 'valeur': round(sum(vals) / len(vals), 6)} if vals else {'n': 0, 'valeur': None}


def _ajouter(g, version, m, v):
    """Ajoute un match au groupe ; une mesure non observable n'entre pas dans son dénominateur."""
    g['matchs'] += 1
    p = min(1.0 - EPS, max(EPS, v['p_home']))
    g['victoire']['log_loss'].append(_loss(p if m['gagnant'] == 'home' else 1 - p))
    g['victoire']['brier'].append((p - (m['gagnant'] == 'home')) ** 2)
    g['victoire']['exact'].append(float((p >= .5) == (m['gagnant'] == 'home')))
    j = v
    if isinstance(j.get('proba_des_sets_reels'), (int, float)):
        g['sets']['log_loss'].append(_loss(j['proba_des_sets_reels']))
        g['sets']['exact'].append(float(bool(j.get('sets_justes'))))
    if isinstance(j.get('score_juste'), bool):
        g['scores']['exact'].append(float(j['score_juste']))
    if isinstance(j.get('score_juste'), bool):
        rang = j.get('rang_du_score_reel')
        g['scores']['rang_reciproque'].append(1.0 / rang if isinstance(rang, int) and rang > 0 else 0.0)
        g['scores']['dans_top3'].append(float(isinstance(rang, int) and 1 <= rang <= 3))
    if isinstance(j.get('ecart_jeux'), (int, float)):
        g['jeux']['mae'].append(abs(j['ecart_jeux']))
    diagnostic_version = m.get('diagnostic_version')
    if diagnostic_version is None and m.get('diagnostic'):
        p_affiche = m.get('p_affiche')
        diagnostic_version = version if p_affiche is not None and abs(p_affiche-v.get('p_home', -1)) < 1e-9 else None
    diagnostics = ((m.get('diagnostic') or {}).get('stats') or {}) if diagnostic_version == version else {}
    for nom, par_cote in diagnostics.items():
        for cote, d in par_cote.items():
            if nom not in STATS or cote not in ('home', 'away'):
                continue
            prevu, reel = d.get('prevu'), d.get('reel')
            if not isinstance(prevu, (int, float)) or not isinstance(reel, (int, float)):
                continue
            g['statistiques'][nom]['mae'].append(abs(prevu - reel))
            g['statistiques'][nom]['biais'].append(prevu - reel)
            if isinstance(d.get('dans'), bool):
                g['statistiques'][nom]['couverture80'].append(float(d['dans']))


def _groupe():
    return {
        'matchs': 0,
        'victoire': defaultdict(list), 'sets': defaultdict(list),
        'scores': defaultdict(list), 'jeux': defaultdict(list),
        'statistiques': defaultdict(lambda: defaultdict(list)),
    }


def _exporter(g):
    return {
        'matchs': g['matchs'],
        'victoire': {k: _resume(v) for k, v in g['victoire'].items()},
        'sets': {k: _resume(v) for k, v in g['sets'].items()},
        'scores': {k: _resume(v) for k, v in g['scores'].items()},
        'jeux': {k: _resume(v) for k, v in g['jeux'].items()},
        'statistiques': {nom: {k: _resume(v) for k, v in mesures.items()}
                         for nom, mesures in sorted(g['statistiques'].items())},
    }


def evaluer(resultats, versions=VERSIONS):
    groupes = {v: _groupe() for v in versions}
    par_surface = defaultdict(lambda: {v: _groupe() for v in versions})
    par_circuit = defaultdict(lambda: {v: _groupe() for v in versions})
    par_fiabilite = defaultdict(lambda: {v: _groupe() for v in versions})
    par_documentation = defaultdict(lambda: {v: _groupe() for v in versions})
    utilises, rejetes = AB.utilisables(resultats, 'combinaison')
    for m in utilises:
        surface = (m.get('surface') or 'Inconnue').strip()
        circuit = (m.get('circuit') or 'Inconnu').strip()
        for v in versions:
            prevu = (m.get('prevus') or {}).get(v)
            if not isinstance(prevu, dict) or not isinstance(prevu.get('p_home'), (int, float)):
                continue
            f = m.get('fiabilite') or (prevu or {}).get('fiabilite') or {}
            niveau = FI.niveau(f['note']) if isinstance(f.get('note'), (int, float)) else 'non_note'
            sim = prevu.get('match_simule') or {}
            profils = sim.get('profil_connu')
            if isinstance(profils, list) and len(profils) == 2:
                documentation = 'documente' if all(profils) else 'tres_peu_documente' if not any(profils) else 'peu_documente'
            else:
                score_doc = (f.get('composantes') or {}).get('donnees', 0)
                documentation = 'documente' if score_doc >= 65 else 'peu_documente' if score_doc >= 20 else 'tres_peu_documente'
            for g in (groupes[v], par_surface[surface][v], par_circuit[circuit][v],
                      par_fiabilite[niveau][v], par_documentation[documentation][v]):
                _ajouter(g, v, m, prevu)
    return {
        'global': {v: _exporter(g) for v, g in groupes.items()},
        'par_surface': {k: {v: _exporter(g) for v, g in d.items()} for k, d in par_surface.items()},
        'par_circuit': {k: {v: _exporter(g) for v, g in d.items()} for k, d in par_circuit.items()},
        'par_fiabilite': {k: {v: _exporter(g) for v, g in d.items()} for k, d in par_fiabilite.items()},
        'par_documentation': {k: {v: _exporter(g) for v, g in d.items()} for k, d in par_documentation.items()},
        'matchs_retenus_vainqueur': len(utilises),
        'entrees_ecartees': len(rejetes),
    }


def main(racine='.'):
    try:
        doc = json.load(open(os.path.join(racine, AB.RESULTATS), encoding='utf-8'))
    except (OSError, ValueError):
        doc = {}
    out = evaluer(doc)
    out.update({
        'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(),
        'source': 'pronostics pré-match figés et résultats raccordés, sans marché',
        'couverture_nominale': .80,
        'note': "Le rang du score est nul-indexé ; les mesures indisponibles ne sont pas remplacées par zéro.",
    })
    chemin = os.path.join(racine, 'simulateur', 'rapport_evaluation_sorties.json')
    json.dump(out, open(chemin, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('Évaluation des sorties :', chemin, flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--racine', default='.')
    args = ap.parse_args()
    main(args.racine)
