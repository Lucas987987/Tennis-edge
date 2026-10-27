#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ablations figées des évolutions service–retour, incertitude et interactions.

2024 sert à ajuster les coefficients. 2025–2026 est une période de DIAGNOSTIC
déjà réutilisée par le projet, pas une confirmation vierge. Aucun candidat n'est
activé ; la promotion exige les futurs pronostics définis dans le manifeste.
"""
import argparse
import datetime as dt
import json
import math
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import arbres as A  # noqa: E402
import donnees  # noqa: E402
import etude_pistes as EP  # noqa: E402
import gouvernance_candidats as GC  # noqa: E402
import pistes_observations as PO  # noqa: E402
import profils_robustes as PR  # noqa: E402
import styles_joueurs as ST  # noqa: E402

CHAMPS = {'hierarchie_service_retour': 'hierarchie_service_retour',
          'incertitude_dynamique': 'incertitude_dynamique',
          'hierarchie_incertitude': 'hierarchie_incertitude'}


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _variables(r, champs):
    return ST._variables(r) + [_lg(r[CHAMPS[c]]) for c in champs]


def _lineaire(dec, conf, champs, p0_dec, p0_conf, bootstrap, graine):
    modele = ST._ajuster([_variables(r, champs) for r in dec], [r['y'] for r in dec])
    pd = ST._predire(modele, [_variables(r, champs) for r in dec])
    pc = ST._predire(modele, [_variables(r, champs) for r in conf])
    bloc = EP._rapport_challenger(dec, conf, pd, pc, p0_dec, p0_conf, bootstrap, graine)
    bloc.update({'convergence': bool(modele and modele['converged']), 'variables': list(champs),
                 'coefficients_standardises_decouverte': dict(zip(EP.NOMS_CONTROLE + list(champs), modele['beta']))})
    return bloc


def _x_non_lineaire(r):
    ze, zs = _lg(r['elo']), _lg(r['service_retour'])
    return [ze, zs, ze - zs, math.log1p(max(0, r['documentation_balles'])),
            math.log1p(max(0, r['documentation_matchs'])),
            float(r['circuit'] == 'WTA'), float(r['circuit'] == 'CH'), float(r['circuit'] == 'ITF'),
            float(r['surface'] == 'Clay'), float(r['surface'] == 'Grass'), float(r['bo'] == 5)]


def _non_lineaire(dec, conf, p0_dec, p0_conf, bootstrap):
    X, y, offsets = [], [], []
    for r, p in zip(dec, p0_dec):
        x, off = _x_non_lineaire(r), _lg(p)
        X.extend((x, [-v if j in (0, 1, 2) else v for j, v in enumerate(x)]))
        y.extend((r['y'], 1 - r['y']))
        offsets.extend((off, -off))
    modele = A.apprendre(X, y, offsets)  # réglages gelés : 60 arbres, profondeur 2, feuilles >= 80
    pd = [A.predire_symetrique(modele, _x_non_lineaire(r), _lg(p), (0, 1, 2)) for r, p in zip(dec, p0_dec)]
    pc = [A.predire_symetrique(modele, _x_non_lineaire(r), _lg(p), (0, 1, 2)) for r, p in zip(conf, p0_conf)]
    bloc = EP._rapport_challenger(dec, conf, pd, pc, p0_dec, p0_conf, bootstrap, 20261030)
    bloc.update({'implementation': 'arbres.py, bibliothèque standard, modèle sérialisable et reproductible',
                 'parametres': {'profondeur': A.PROFONDEUR, 'tours': A.TOURS, 'pas': A.PAS,
                                'feuille_min': A.FEUILLE_MIN, 'seuils': A.N_SEUILS},
                 'variables': ['logit_elo', 'logit_service_retour', 'desaccord_signe', 'documentation_balles',
                               'documentation_matchs', 'circuit', 'surface', 'format']})
    return bloc


def evaluer(rows, bootstrap=2000):
    dec = [r for r in rows if r['date'] < EP.COUPURE]
    conf = [r for r in rows if r['date'] >= EP.COUPURE]
    controle = EP._fit(dec)
    p0_dec, p0_conf = EP._predire(controle, dec), EP._predire(controle, conf)
    out = {'controle': {'decouverte': ST._metriques([r['y'] for r in dec], p0_dec),
                        'diagnostic_2025_2026': ST._metriques([r['y'] for r in conf], p0_conf)}}
    for i, (nom, champs) in enumerate((('hierarchie_service_retour', ('hierarchie_service_retour',)),
                                       ('incertitude_dynamique', ('incertitude_dynamique',)),
                                       ('hierarchie_et_incertitude', tuple(CHAMPS)))):
        out[nom] = _lineaire(dec, conf, champs, p0_dec, p0_conf, bootstrap, 20261120 + i)
    out['non_lineaire_parcimonieux'] = _non_lineaire(dec, conf, p0_dec, p0_conf, bootstrap)
    for nom, bloc in out.items():
        if nom == 'controle':
            continue
        historiquement_solide = bloc['apport_confirme']
        bloc['criteres_historiques_satisfaits'] = historiquement_solide
        bloc['apport_confirme'] = False
        bloc['confirmation_future_requise'] = True
        bloc['verdict'] = ('critères historiques satisfaits, mais diagnostic seulement ; confirmation future requise'
                           if historiquement_solide else 'apport non établi ; champion inchangé et confirmation future requise')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('archive')
    ap.add_argument('racine', nargs='?', default='.')
    ap.add_argument('--maximum', type=int, default=16000)
    ap.add_argument('--bootstrap', type=int, default=2000)
    ap.add_argument('--sortie')
    args = ap.parse_args(argv)
    debut = time.time()
    M = donnees.charger(args.archive, 2021)
    choisis = PR.selection(M, dt.date(2024, 1, 1), args.maximum)
    print(f'Archive : {len(M)} matchs ; échantillon commun : {len(choisis)}', flush=True)
    rows = PO.observations(M, choisis, evolutions=True)
    print(f'Observations pré-match : {len(rows)} ; ajustements figés sur 2024', flush=True)
    rapport = evaluer(rows, args.bootstrap)
    manifeste = GC.charger(args.racine)
    out = {'schema': 'evolutions_algorithmes_v1',
           'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'source': 'archive Jeff Sackmann, CC BY-NC-SA 4.0, usage non commercial et attribution requis',
           'protocole': {'n': len(rows), 'n_decouverte_2024': sum(r['date'] < EP.COUPURE for r in rows),
                         'n_diagnostic_2025_2026': sum(r['date'] >= EP.COUPURE for r in rows),
                         'ablation': 'mêmes matchs, orientation alphabétique indépendante du résultat',
                         'temporalite': 'résultats versés à la date suivante ; service–retour à la fin du tournoi',
                         'diagnostic_reutilise': True, 'confirmation_vierge': False,
                         'marche_utilise': False, 'activation_automatique': False,
                         'empreintes_candidats': GC.empreintes(manifeste)},
           'resultats': rapport, 'champion_actif_modifie': False,
           'securite': manifeste['securite'], 'duree_s': round(time.time() - debut)}
    chemin = os.path.join(args.racine, 'simulateur', 'rapport_evolutions_algorithmes.json')
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    if args.sortie:
        with open(args.sortie, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    resume = {nom: {'gains': b.get('confirmation', {}).get('gains'), 'verdict': b.get('verdict')}
              for nom, b in rapport.items() if nom != 'controle'}
    print(json.dumps({'controle': rapport['controle'], 'challengers': resume}, ensure_ascii=False, indent=2))
    return out


if __name__ == '__main__':
    main()
