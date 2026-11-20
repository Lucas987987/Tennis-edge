#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validation technique de la distribution exacte ; ne mesure pas un gain prédictif."""
import argparse
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import distribution_exacte as DE  # noqa: E402
import match_simule as MS  # noqa: E402


def main(racine='.', sortie=None, simulations=20000):
    cas, erreur_max = [], 0.0
    for bo in (2, 3):
        for pa, pb in ((.55, .52), (.63, .61), (.68, .60)):
            for bp in (False, True):
                da, db = (-.08, .05) if bp else (0.0, 0.0)
                d = DE.distribution_match(pa, pb, bo, dA=da, dB=db)
                exact = DE.victoire_depuis_distribution(d)
                reference = MS.victoire(pa, pb, bo, dA=da, dB=db)
                erreur = abs(exact - reference)
                erreur_max = max(erreur_max, erreur)
                cas.append({'bo': 2 * bo - 1, 'points': [pa, pb], 'balles_de_break_specifiques': bp,
                            'controle': DE.controle(d), 'victoire_exacte': exact,
                            'victoire_moteur_existant': reference, 'ecart_absolu': erreur})
    a = {'f': .60, 'a': .08, 'w1': .72, 'd': .03, 'w2j': .53}
    b = {'f': .62, 'a': .06, 'w1': .69, 'd': .04, 'w2j': .51}
    d = DE.distribution_forme(a, b, 2, .15)
    sim = MS.simuler(a, b, None, 2, n=simulations, sigma=.15, cle='validation-distribution-exacte')
    sim_scores = {s: p for s, p in sim['scores']}
    top_exact = [{'score': ' '.join(f'{x}-{y}' for x, y in r['score']),
                  'probabilite': round(r['probabilite'], 6),
                  'probabilite_simulee_si_top5': sim_scores.get(' '.join(f'{x}-{y}' for x, y in r['score']))}
                 for r in DE.scores_ordonnes(d)[:5]]
    out = {'schema': 'validation_distribution_exacte_v1',
           'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'cas': cas, 'erreur_victoire_max': erreur_max,
           'tous_les_cas_valides': all(c['controle']['ok'] and c['ecart_absolu'] < 1e-10 for c in cas),
           'forme_du_jour': {'controle': DE.controle(d), 'victoire_exacte': DE.victoire_depuis_distribution(d),
                             'victoire_simulee': sim['victoire_A'], 'n_simulations': simulations,
                             'scores_exact_les_plus_frequents': top_exact},
           'portee': 'Équivalence mathématique et stabilité numérique sous le modèle, pas preuve de meilleurs vainqueurs, scores réels ou ROI.',
           'simulations_conservees': 'vidéo, feuilles détaillées, tirage rejouable et scénario médoid',
           'champion_actif_modifie': False}
    chemin = os.path.join(racine, 'simulateur', 'rapport_distribution_exacte.json')
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    if sortie:
        with open(sortie, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps({'cas': len(cas), 'erreur_max': erreur_max, 'valides': out['tous_les_cas_valides'],
                      'forme': out['forme_du_jour']}, ensure_ascii=False, indent=2))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('racine', nargs='?', default='.')
    ap.add_argument('--sortie')
    ap.add_argument('--simulations', type=int, default=20000)
    args = ap.parse_args()
    main(args.racine, args.sortie, args.simulations)
