#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Matrice exhaustive et orientée des interactions entre les cinq profils réels.

Contrairement à l'étude compacte des serveurs, chaque paire de profils distincts
possède son propre coefficient dans chaque branche ATP, WTA et Challenger/ITF.
Le coefficient peut favoriser librement l'un ou l'autre profil. Le socle Elo,
surface, circuit, service–retour, documentation et bilan global reste partagé :
il ne s'agit pas de trois algorithmes autonomes.

Les 10 paires non orientées donnent 20 cellules directionnelles par branche.
Toutes sont rapportées, y compris les cases nulles ou défavorables. Aucun duel
n'est sélectionné après le diagnostic. Apprentissage ridge sur 2024 uniquement,
coefficients figés pour le diagnostic historique réutilisé 2025–2026. Aucun
marché, aucun bonus manuel et aucune activation automatique.

Usage : python simulateur/etude_matrice_profils_orientee.py /tmp/archive . --maximum 8000
Sorties : rapport_matrice_profils_orientee.json/.md et modele_matrice_profils_orientee.json.
"""
import argparse
import datetime as dt
import itertools
import json
import os
import random
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees  # noqa: E402
import profils_robustes as PR  # noqa: E402
import styles_joueurs as ST  # noqa: E402
import styles_valeur as SV  # noqa: E402

SCHEMA = 'matrice_profils_orientee_v1'
GEL_UTC = '2026-11-01T00:00:00+00:00'
COUPURE = dt.date(2025, 1, 1)
STYLES = ('grand_serveur', 'serveur_attaquant', 'retourneur_pressant', 'contreur', 'equilibre')
PAIRES = tuple(itertools.combinations(STYLES, 2))
PAIRES_MAP = {f'{a}|{b}': (a, b) for a, b in PAIRES}
BRANCHES = {'atp': ('ATP',), 'wta': ('WTA',), 'challenger': ('CH', 'ITF')}
NOMS_BASE = ['constante', 'elo', 'service_retour', 'terre', 'gazon', 'wta', 'challenger', 'itf',
             'documentation_balles', 'documentation_matchs', 'moins_500_balles', 'bilan_global']


def branche(circuit):
    for nom, circuits in BRANCHES.items():
        if circuit in circuits:
            return nom
    raise ValueError(f'Circuit non couvert : {circuit}')


def cle_direction(style_a, style_b):
    return f'{style_a}_contre_{style_b}'


def orientation_paire(row, paire):
    styles = (row['style_home'], row['style_away'])
    if styles == paire:
        return 1.0
    if styles == paire[::-1]:
        return -1.0
    return 0.0


def _variables(row, complet=False):
    x = ST._variables(row) + [row['bilan_global']]
    if complet:
        b = branche(row['circuit'])
        for nom in BRANCHES:
            for paire in PAIRES:
                x.append(orientation_paire(row, paire) if b == nom else 0.0)
    return x


def _noms():
    return NOMS_BASE + [f'{nom}:{paire[0]}|{paire[1]}' for nom in BRANCHES for paire in PAIRES]


def _metriques(rows, predictions):
    return ST._metriques([r['y'] for r in rows], predictions)


def _gains(rows, sans, avec):
    return ST._gains([r['y'] for r in rows], sans, avec)


def _coefficients_bruts(modele):
    """Coefficient de log-odds par unité orientée, après déstandardisation."""
    if not modele:
        return {}
    return {nom: modele['beta'][i]/modele['ecarts'][i] if modele['ecarts'][i] else 0.0
            for i, nom in enumerate(_noms())}


def _ic_residuel(rows, controle, repetitions=2000, graine=20261101):
    """IC du résiduel du premier profil canonique, groupé par semaine ISO."""
    if not rows or repetitions <= 0:
        return None
    semaines = sorted({r['semaine'] for r in rows})
    if len(semaines) < 2:
        return None
    groupes = {s: [i for i, r in enumerate(rows) if r['semaine'] == s] for s in semaines}
    rnd, valeurs = random.Random(graine), []
    for _ in range(repetitions):
        indices = [i for s in (rnd.choice(semaines) for _ in semaines) for i in groupes[s]]
        total = 0.0
        for i in indices:
            sens = 1 if (rows[i]['style_home'], rows[i]['style_away']) == PAIRES_MAP[rows[i]['_paire']] else -1
            total += sens*(rows[i]['y']-controle[i])
        valeurs.append(100*total/len(indices))
    valeurs.sort()
    return {'bas': round(valeurs[int(.025*(len(valeurs)-1))], 3),
            'haut': round(valeurs[int(.975*(len(valeurs)-1))], 3)}


def _cellule(rows, controle, challenger, paire, coefficient, bootstrap=0, graine=20261101):
    """Cellule canonique A contre B ; les deux orientations de match sont incluses."""
    rr = []
    for i, r in enumerate(rows):
        if (r['style_home'], r['style_away']) in (paire, paire[::-1]):
            rr.append(dict(r, _paire=f'{paire[0]}|{paire[1]}', _index=i))
    if not rr:
        return {'n': 0, 'coefficient_log_odds_favorisant_profil': round(coefficient, 8),
                'victoires_profil_pct': None, 'probabilite_controle_profil_pct': None,
                'residuel_controle_points': None, 'controle_avec_bilan': {'n': 0},
                'challenger': {'n': 0}, 'gains_incrementaux': {'log_loss': None, 'brier': None},
                'ic95_bootstrap_semaine': None}
    indices = [r['_index'] for r in rr]
    p0, p1 = [controle[i] for i in indices], [challenger[i] for i in indices]
    victoires, attendu, residus = [], [], []
    for r, p in zip(rr, p0):
        sens = 1 if (r['style_home'], r['style_away']) == paire else -1
        victoires.append(r['y'] if sens == 1 else 1-r['y'])
        attendu.append(p if sens == 1 else 1-p)
        residus.append(sens*(r['y']-p))
    out = {'n': len(rr), 'coefficient_log_odds_favorisant_profil': round(coefficient, 8),
           'victoires_profil_pct': round(100*sum(victoires)/len(rr), 2),
           'probabilite_controle_profil_pct': round(100*sum(attendu)/len(rr), 2),
           'residuel_controle_points': round(100*sum(residus)/len(rr), 3),
           'controle_avec_bilan': _metriques(rr, p0), 'challenger': _metriques(rr, p1),
           'gains_incrementaux': _gains(rr, p0, p1), 'ic95_bootstrap_semaine': None}
    if bootstrap:
        out['ic95_bootstrap_semaine'] = dict(ST._ic_gains(rr, p0, p1, bootstrap, graine))
        out['ic95_bootstrap_semaine']['residuel_controle_points'] = _ic_residuel(
            rr, p0, bootstrap, graine+10000)
    return out


def _inverser_cellule(cellule):
    """Traduit A contre B en B contre A sans recalculer ni choisir une nouvelle case."""
    if not cellule or cellule.get('n', 0) == 0:
        return dict(cellule, coefficient_log_odds_favorisant_profil=-cellule.get(
            'coefficient_log_odds_favorisant_profil', 0.0)) if cellule else cellule
    out = dict(cellule)
    out['coefficient_log_odds_favorisant_profil'] = -cellule['coefficient_log_odds_favorisant_profil']
    out['victoires_profil_pct'] = round(100-cellule['victoires_profil_pct'], 2)
    out['probabilite_controle_profil_pct'] = round(100-cellule['probabilite_controle_profil_pct'], 2)
    out['residuel_controle_points'] = -cellule['residuel_controle_points']
    ic = cellule.get('ic95_bootstrap_semaine')
    if ic:
        out['ic95_bootstrap_semaine'] = dict(ic)
        residu = ic.get('residuel_controle_points')
        if residu:
            out['ic95_bootstrap_semaine']['residuel_controle_points'] = {
                'bas': -residu['haut'], 'haut': -residu['bas']}
    return out


def evaluer(rows, coupure=COUPURE, bootstrap=2000):
    dec = [r for r in rows if r['date'] < coupure]
    conf = [r for r in rows if r['date'] >= coupure]
    y_dec = [r['y'] for r in dec]
    controle = ST._ajuster([_variables(r) for r in dec], y_dec)
    challenger = ST._ajuster([_variables(r, True) for r in dec], y_dec)
    p0_dec = ST._predire(controle, [_variables(r) for r in dec])
    p0_conf = ST._predire(controle, [_variables(r) for r in conf])
    p1_dec = ST._predire(challenger, [_variables(r, True) for r in dec])
    p1_conf = ST._predire(challenger, [_variables(r, True) for r in conf])
    coefficients = _coefficients_bruts(challenger)
    branches, matrices = {}, {}
    for k, (nom, circuits) in enumerate(BRANCHES.items()):
        d = [r for r in dec if r['circuit'] in circuits]
        c = [r for r in conf if r['circuit'] in circuits]
        id_d = [i for i, r in enumerate(dec) if r['circuit'] in circuits]
        id_c = [i for i, r in enumerate(conf) if r['circuit'] in circuits]
        d0, d1 = [p0_dec[i] for i in id_d], [p1_dec[i] for i in id_d]
        c0, c1 = [p0_conf[i] for i in id_c], [p1_conf[i] for i in id_c]
        gains = _gains(c, c0, c1)
        ic = ST._ic_gains(c, c0, c1, bootstrap, graine=20261110+k)
        branches[nom] = {
            'circuits': list(circuits), 'n_decouverte': len(d), 'n_diagnostic': len(c),
            'decouverte': {'controle_avec_bilan': _metriques(d, d0), 'challenger': _metriques(d, d1),
                           'gains_incrementaux': _gains(d, d0, d1)},
            'diagnostic': {'controle_avec_bilan': _metriques(c, c0), 'challenger': _metriques(c, c1),
                           'gains_incrementaux': gains, 'ic95_bootstrap_semaine': ic},
            'activation': False,
        }
        matrice = {}
        for j, paire in enumerate(PAIRES):
            coefficient = coefficients[f'{nom}:{paire[0]}|{paire[1]}']
            cell_dec = _cellule(d, d0, d1, paire, coefficient)
            cell_conf = _cellule(c, c0, c1, paire, coefficient, bootstrap,
                                 graine=20262000+100*k+j)
            cellule = {'n_decouverte': cell_dec['n'], 'n_diagnostic': cell_conf['n'],
                       'decouverte': cell_dec, 'diagnostic': cell_conf}
            matrice[cle_direction(*paire)] = cellule
            matrice[cle_direction(*paire[::-1])] = {
                'n_decouverte': cell_dec['n'], 'n_diagnostic': cell_conf['n'],
                'decouverte': _inverser_cellule(cell_dec), 'diagnostic': _inverser_cellule(cell_conf)}
        matrices[nom] = matrice
    gains_global = _gains(conf, p0_conf, p1_conf)
    return {
        'schema': SCHEMA, 'n': len(rows), 'n_decouverte': len(dec), 'n_diagnostic': len(conf),
        'coupure': coupure.isoformat(), 'styles': list(STYLES),
        'paires_canoniques': [list(p) for p in PAIRES], 'cellules_directionnelles_par_branche': 20,
        'orientation': 'ordre alphabétique des joueurs ; chaque paire a un coefficient libre dans chaque branche',
        'socle_partage': True, 'algorithmes_autonomes_par_circuit': False,
        'reference_incrementale': 'contrôles Elo/service–retour + bilan global ; 30 interactions paire × branche',
        'decouverte_globale': {'controle_avec_bilan': _metriques(dec, p0_dec),
                               'challenger': _metriques(dec, p1_dec), 'gains_incrementaux': _gains(dec, p0_dec, p1_dec)},
        'diagnostic_global': {'controle_avec_bilan': _metriques(conf, p0_conf),
                              'challenger': _metriques(conf, p1_conf), 'gains_incrementaux': gains_global,
                              'ic95_bootstrap_semaine': ST._ic_gains(conf, p0_conf, p1_conf, bootstrap, 20261130)},
        'branches': branches, 'matrice_directionnelle': matrices,
        'convergence': {'controle': bool(controle and controle['converged']),
                        'challenger': bool(challenger and challenger['converged'])},
        'coefficients_standardises_decouverte': dict(zip(_noms(), challenger['beta'])) if challenger else None,
        'coefficients_non_standardises': coefficients,
        'modeles_complets_decouverte': {'controle': controle, 'challenger': challenger},
        'nature_diagnostic': '2025–2026 historique réutilisé ; jamais une confirmation prospective nouvelle',
        'comparaisons_multiples': '60 cellules directionnelles affichées exhaustivement ; aucune case positive sélectionnée comme règle',
        'marche_utilise': False, 'activation': False, 'champion_actif_modifie': False,
        'regle': 'ridge 1.0 sur 2024 uniquement ; coefficients figés ; aucune activation automatique',
    }


def markdown(rapport):
    lignes = ['# Matrice orientée exhaustive des profils', '',
              'Cinq profils réels, vingt directions par branche. Diagnostic historique réutilisé ; aucune activation.', '',
              '## Synthèse des corrections complètes', '',
              '| Branche | n | Gain log loss | Gain Brier | IC95 log loss | Exactitude contrôle → challenger |',
              '|---|---:|---:|---:|---:|---:|']
    for nom, b in rapport['branches'].items():
        d = b['diagnostic']
        g, ic = d['gains_incrementaux'], d['ic95_bootstrap_semaine'].get('log_loss')
        ict = f"[{ic['bas']:+.6f} ; {ic['haut']:+.6f}]" if ic else '—'
        lignes.append(f"| {nom} | {b['n_diagnostic']} | {g['log_loss']:+.6f} | {g['brier']:+.6f} | {ict} | "
                      f"{d['controle_avec_bilan'].get('reussite_pct')} % → {d['challenger'].get('reussite_pct')} % |")
    lignes += ['', '## Cellules directionnelles du diagnostic', '',
               'Le résiduel est celui du premier profil après Elo, service–retour et bilan global. Les métriques de la case inverse portent sur les mêmes matchs.', '',
               '| Branche | Direction | n | Résiduel (points) | IC95 résiduel | Gain log loss | Gain Brier | Exactitude C → M |',
               '|---|---|---:|---:|---:|---:|---:|---:|']
    for nom, matrice in rapport['matrice_directionnelle'].items():
        for direction in sorted(matrice):
            c = matrice[direction]['diagnostic']
            if not c['n']:
                lignes.append(f'| {nom} | {direction} | 0 | — | — | — | — | — |')
                continue
            ic = (c.get('ic95_bootstrap_semaine') or {}).get('residuel_controle_points')
            ict = f"[{ic['bas']:+.3f} ; {ic['haut']:+.3f}]" if ic else '—'
            g = c['gains_incrementaux']
            lignes.append(f"| {nom} | {direction} | {c['n']} | {c['residuel_controle_points']:+.3f} | {ict} | "
                          f"{g['log_loss']:+.6f} | {g['brier']:+.6f} | {c['controle_avec_bilan']['reussite_pct']} % → "
                          f"{c['challenger']['reussite_pct']} % |")
    return '\n'.join(lignes)+'\n'


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('archive')
    parser.add_argument('racine', nargs='?', default='.')
    parser.add_argument('--maximum', type=int, default=8000)
    parser.add_argument('--bootstrap', type=int, default=2000)
    args = parser.parse_args(argv)
    matchs = donnees.charger(args.archive, 2021)
    choisis = PR.selection(matchs, dt.date(2024, 1, 1), args.maximum)
    rows = SV.observations(matchs, choisis)
    out = evaluer(rows, bootstrap=args.bootstrap)
    dossier = os.path.join(args.racine, 'simulateur')
    with open(os.path.join(dossier, 'rapport_matrice_profils_orientee.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open(os.path.join(dossier, 'rapport_matrice_profils_orientee.md'), 'w', encoding='utf-8') as f:
        f.write(markdown(out))
    modele = {'schema': SCHEMA, 'gel_utc': GEL_UTC, 'activation': False,
              'utilisation': 'recherche et diagnostic uniquement ; aucune journalisation ou production',
              'ajustement': 'régression logistique ridge 1.0 sur découverte 2024 uniquement',
              'orientation_apprentissage': 'identifiants joueurs par ordre alphabétique',
              'styles': list(STYLES), 'paires': [list(p) for p in PAIRES],
              'branches': {nom: list(circuits) for nom, circuits in BRANCHES.items()},
              'controle': out['modeles_complets_decouverte']['controle'],
              'challenger': out['modeles_complets_decouverte']['challenger'],
              'nature_diagnostic': out['nature_diagnostic']}
    with open(os.path.join(dossier, 'modele_matrice_profils_orientee.json'), 'w', encoding='utf-8') as f:
        json.dump(modele, f, ensure_ascii=False, indent=2)
    print(json.dumps({'n': out['n'], 'diagnostic_global': out['diagnostic_global'],
                      'branches': {nom: b['diagnostic'] for nom, b in out['branches'].items()}},
                     ensure_ascii=False, indent=2))
    return out


if __name__ == '__main__':
    main()
