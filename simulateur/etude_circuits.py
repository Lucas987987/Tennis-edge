#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deux algorithmes ATP/WTA et Challenger/ITF, historiques joueurs partagés.

La séparation porte uniquement sur les coefficients et les variables retenues.
Elo, service–retour, calendrier, H2H et pression sont reconstruits une seule fois
sur tous les circuits : les transitions entre circuits restent donc informatives.
Le choix des variantes est fait sur 2024, puis figé pour 2025–2026. Aucun marché
n'est lu et aucun champion actif n'est modifié.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees  # noqa: E402
import elo_recherche as ER  # noqa: E402
import etude_pistes as EP  # noqa: E402
import pistes_observations as PO  # noqa: E402
import profils_robustes as PR  # noqa: E402
import styles_joueurs as ST  # noqa: E402

GROUPES = {'atp_wta': ('ATP', 'WTA'), 'challenger_itf': ('CH', 'ITF')}


def groupe(circuit):
    for nom, circuits in GROUPES.items():
        if circuit in circuits:
            return nom
    raise ValueError(f'Circuit non couvert : {circuit}')


def _fit(rows, ajouts=(), elo=None):
    return ST._ajuster([EP._variables(r, ajouts, elo.get(r['uid']) if elo else None) for r in rows],
                       [r['y'] for r in rows])


def _predire(modele, rows, ajouts=(), elo=None):
    return ST._predire(modele, [EP._variables(r, ajouts, elo.get(r['uid']) if elo else None) for r in rows])


def _metriques(rows, p):
    return ST._metriques([r['y'] for r in rows], p)


def _candidat(dec, p0, ajouts=(), elo=None):
    modele = _fit(dec, ajouts, elo)
    p = _predire(modele, dec, ajouts, elo)
    return {'modele': modele, 'ajouts': tuple(ajouts), 'elo': elo,
            'decouverte': _metriques(dec, p),
            'gains_decouverte': EP._gains_bruts([r['y'] for r in dec], p0, p),
            'convergence': bool(modele and modele['converged'])}


def _public(c):
    return {'decouverte': c['decouverte'], 'gains_decouverte': c['gains_decouverte'],
            'convergence': c['convergence']}


def selectionner(dec, predictions_elo):
    """Choisit un seul candidat sur la découverte, sans lire la confirmation."""
    base_modele = _fit(dec)
    p0 = _predire(base_modele, dec)
    base = _candidat(dec, p0)
    candidats = {'controle_local': base}

    meilleur_elo, candidats_elo = None, {}
    for nom in (n for n in ER.VARIANTES if n != 'controle'):
        pe = {uid: valeurs[nom] for uid, valeurs in predictions_elo.items()}
        c = _candidat(dec, p0, elo=pe)
        candidats_elo[nom] = c
        candidats['elo:' + nom] = c
    meilleur_elo = min(candidats_elo, key=lambda n: candidats_elo[n]['decouverte']['log_loss'])

    familles = {}
    for nom, variables in EP.FAMILLES.items():
        c = _candidat(dec, p0, variables)
        familles[nom] = c
        candidats['famille:' + nom] = c

    eligibles = [nom for nom, c in familles.items()
                 if c['gains_decouverte']['log_loss'] > 0 and c['gains_decouverte']['brier'] >= 0]
    elo_eligible = (candidats_elo[meilleur_elo]['gains_decouverte']['log_loss'] > 0
                    and candidats_elo[meilleur_elo]['gains_decouverte']['brier'] >= 0)
    composantes = list(eligibles) + (['elo_dynamique'] if elo_eligible else [])
    if len(composantes) >= 2:
        variables = [v for nom in eligibles for v in EP.FAMILLES[nom]]
        pe = {uid: valeurs[meilleur_elo] for uid, valeurs in predictions_elo.items()} if elo_eligible else None
        candidats['combinaison'] = _candidat(dec, p0, variables, pe)

    choisi = min(candidats, key=lambda n: candidats[n]['decouverte']['log_loss'])
    public = {'candidats': {nom: _public(c) for nom, c in candidats.items()},
              'elo_choisi_pour_combinaison': meilleur_elo,
              'composantes_eligibles': composantes,
              'variante_choisie_sur_decouverte': choisi,
              'regle': 'un seul candidat retenu par plus faible log loss sur 2024 ; coefficients ensuite figés'}
    return {'candidat': candidats[choisi], 'base': base, 'selection': public}


def _predictions(selection, rows):
    c = selection['candidat']
    return _predire(c['modele'], rows, c['ajouts'], c['elo'])


def _predictions_base(selection, rows):
    c = selection['base']
    return _predire(c['modele'], rows, c['ajouts'], c['elo'])


def _rapport(dec, conf, p_dec, p_conf, ref_dec, ref_conf, bootstrap, graine):
    return EP._rapport_challenger(dec, conf, p_dec, p_conf, ref_dec, ref_conf, bootstrap, graine)


def evaluer(rows, predictions_elo, bootstrap=2000):
    dec = [r for r in rows if r['date'] < EP.COUPURE]
    conf = [r for r in rows if r['date'] >= EP.COUPURE]
    partage = selectionner(dec, predictions_elo)
    p0_dec, p0_conf = _predictions_base(partage, dec), _predictions_base(partage, conf)
    ps_dec, ps_conf = _predictions(partage, dec), _predictions(partage, conf)
    ref0_dec = dict(zip((r['uid'] for r in dec), p0_dec))
    ref0_conf = dict(zip((r['uid'] for r in conf), p0_conf))
    refs_dec = dict(zip((r['uid'] for r in dec), ps_dec))
    refs_conf = dict(zip((r['uid'] for r in conf), ps_conf))

    groupes, locaux_dec, locaux_conf = {}, {}, {}
    for k, (nom, circuits) in enumerate(GROUPES.items()):
        d = [r for r in dec if r['circuit'] in circuits]
        c = [r for r in conf if r['circuit'] in circuits]
        local = selectionner(d, predictions_elo)
        plb_dec, plb_conf = _predictions_base(local, d), _predictions_base(local, c)
        pl_dec, pl_conf = _predictions(local, d), _predictions(local, c)
        locaux_dec.update({r['uid']: p for r, p in zip(d, pl_dec)})
        locaux_conf.update({r['uid']: p for r, p in zip(c, pl_conf)})
        r0d = [ref0_dec[r['uid']] for r in d]
        r0c = [ref0_conf[r['uid']] for r in c]
        rsd = [refs_dec[r['uid']] for r in d]
        rsc = [refs_conf[r['uid']] for r in c]
        groupes[nom] = {
            'circuits': list(circuits), 'n_decouverte': len(d), 'n_confirmation': len(c),
            'selection_decouverte': local['selection'],
            'separation_seule_vs_controle_partage': _rapport(
                d, c, plb_dec, plb_conf, r0d, r0c, bootstrap, 20262000+k),
            'algorithme_local_vs_controle_partage': _rapport(
                d, c, pl_dec, pl_conf, r0d, r0c, bootstrap, 20262100+k),
            'algorithme_local_vs_algorithme_partage': _rapport(
                d, c, pl_dec, pl_conf, rsd, rsc, bootstrap, 20262200+k),
            'activation': False,
        }

    deux_dec = [locaux_dec[r['uid']] for r in dec]
    deux_conf = [locaux_conf[r['uid']] for r in conf]
    global_controle = _rapport(dec, conf, deux_dec, deux_conf, p0_dec, p0_conf,
                               bootstrap, 20262300)
    global_partage = _rapport(dec, conf, deux_dec, deux_conf, ps_dec, ps_conf,
                              bootstrap, 20262301)
    return {
        'algorithme_partage': {
            'selection_decouverte': partage['selection'],
            'decouverte': _metriques(dec, ps_dec), 'confirmation': _metriques(conf, ps_conf),
            'activation': False,
        },
        'groupes': groupes,
        'deux_algorithmes_vs_controle_partage': global_controle,
        'deux_algorithmes_vs_algorithme_partage': global_partage,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('archive')
    parser.add_argument('racine', nargs='?', default='.')
    parser.add_argument('--maximum', type=int, default=16000)
    parser.add_argument('--bootstrap', type=int, default=2000)
    args = parser.parse_args(argv)
    debut = time.time()
    M = donnees.charger(args.archive, 2021)
    if not M:
        raise SystemExit('Aucun match Sackmann lisible.')
    choisis = PR.selection(M, dt.date(2024, 1, 1), args.maximum)
    print(f'Archive : {len(M)} matchs ; échantillon commun : {len(choisis)}', flush=True)
    rows = PO.observations(M, choisis)
    print(f'Observations partagées : {len(rows)} ; prédictions Elo en cours', flush=True)
    predictions_elo = ER.predictions(M, choisis)
    resultats = evaluer(rows, predictions_elo, args.bootstrap)
    out = {
        'schema': 'algorithmes_circuits_v1',
        'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'source': 'archive Jeff Sackmann, CC BY-NC-SA 4.0, usage non commercial et attribution requis',
        'protocole': {
            'n': len(rows), 'n_decouverte': sum(r['date'] < EP.COUPURE for r in rows),
            'n_confirmation': sum(r['date'] >= EP.COUPURE for r in rows),
            'coupure': EP.COUPURE.isoformat(), 'groupes': {k: list(v) for k, v in GROUPES.items()},
            'historiques_joueurs_partages': True, 'transitions_inter_circuits_conservees': True,
            'separation': 'coefficients et variables retenues seulement',
            'selection': '2024 seulement ; confirmation 2025–2026 ; bootstrap par semaine ISO',
            'bootstrap_semaines_iso': args.bootstrap, 'marche_utilise': False,
            'activation_automatique': False,
        },
        **resultats,
        'champion_actif_modifie': False,
        'duree_s': round(time.time()-debut),
    }
    chemin = os.path.join(args.racine, 'simulateur', 'rapport_algorithmes_circuits.json')
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    resume = {'protocole': out['protocole'],
              'algorithme_partage': out['algorithme_partage']['selection_decouverte']['variante_choisie_sur_decouverte'],
              'groupes': {nom: {
                  'variante': b['selection_decouverte']['variante_choisie_sur_decouverte'],
                  'vs_controle_partage': b['algorithme_local_vs_controle_partage']['confirmation']['gains'],
                  'vs_algorithme_partage': b['algorithme_local_vs_algorithme_partage']['confirmation']['gains'],
                  'verdict': b['algorithme_local_vs_algorithme_partage']['verdict']}
                  for nom, b in out['groupes'].items()},
              'global_vs_algorithme_partage': out['deux_algorithmes_vs_algorithme_partage']['confirmation']['gains'],
              'champion_actif_modifie': False}
    print(json.dumps(resume, ensure_ascii=False, indent=2))
    return out


if __name__ == '__main__':
    main()
