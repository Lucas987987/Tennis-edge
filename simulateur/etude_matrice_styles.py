#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Matrice descriptive des paires de styles avec le bilan global figé.

Le modèle global seul est ajusté sur 2024 puis figé. Chaque paire est décrite
sans sélection post hoc : effectifs, semaines, log loss, Brier, exactitude avec
IC de Wilson, gains contre 50 % et bootstrap par semaine ISO. La période
2025–2026 est un diagnostic historique réutilisé, jamais une activation.

Usage : python simulateur/etude_matrice_styles.py /tmp/sackmann . [--maximum 8000]
Sorties : simulateur/rapport_matrice_styles.json et .md
"""
import argparse
import datetime as dt
import itertools
import json
import math
import os
import random
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees  # noqa: E402
import profils_robustes as PR  # noqa: E402
import styles_joueurs as ST  # noqa: E402
import styles_valeur as SV  # noqa: E402
import etude_styles_seuls as SS  # noqa: E402

STYLES = ('grand_serveur', 'serveur_attaquant', 'retourneur_pressant',
          'contreur', 'equilibre', 'indetermine')
NOMS = {
    'grand_serveur': 'Grand serveur', 'serveur_attaquant': 'Serveur attaquant',
    'retourneur_pressant': 'Retourneur pressant', 'contreur': 'Contreur',
    'equilibre': 'Équilibré', 'indetermine': 'Indéterminé',
}


def paires():
    """Les 21 paires non orientées, dans un ordre fixe et non choisi sur les résultats."""
    return [(a, b, '|'.join(sorted((a, b)))) for a, b in itertools.combinations_with_replacement(STYLES, 2)]


def wilson(victoires, n, z=1.959963984540054):
    if not n:
        return [None, None]
    p = victoires / n
    den = 1 + z*z/n
    centre = (p + z*z/(2*n)) / den
    marge = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return [round(100*max(0.0, centre-marge), 2), round(100*min(1.0, centre+marge), 2)]


def _quantile(valeurs, q):
    valeurs = sorted(valeurs)
    return round(valeurs[int(q*(len(valeurs)-1))], 6)


def _intervalle(valeurs):
    return {'bas': _quantile(valeurs, .025), 'haut': _quantile(valeurs, .975)}


def _bootstrap(rows, predictions, repetitions=2000, graine=20261028):
    """IC des métriques et des gains contre 50 %, en rééchantillonnant les semaines."""
    semaines = sorted({r['semaine'] for r in rows})
    if repetitions <= 0 or len(semaines) < 2 or not rows:
        return {'log_loss': None, 'brier': None, 'gain_log_loss': None, 'gain_brier': None}
    groupes = {s: [] for s in semaines}
    for i, r in enumerate(rows):
        groupes[r['semaine']].append(i)
    agregats = {}
    for semaine, indices in groupes.items():
        n = len(indices)
        ll = ll0 = br = br0 = 0.0
        for i in indices:
            y = rows[i]['y']
            p = min(max(predictions[i], 1e-12), 1-1e-12)
            ll += -math.log(p if y else 1-p)
            ll0 += -math.log(.5)
            br += (p-y)**2
            br0 += (.5-y)**2
        agregats[semaine] = (n, ll, ll0, br, br0)
    rnd = random.Random(graine)
    valeurs = {k: [] for k in ('log_loss', 'brier', 'gain_log_loss', 'gain_brier')}
    for _ in range(repetitions):
        n = ll = ll0 = br = br0 = 0.0
        for semaine in (rnd.choice(semaines) for _ in semaines):
            ni, lli, ll0i, bri, br0i = agregats[semaine]
            n += ni
            ll += lli
            ll0 += ll0i
            br += bri
            br0 += br0i
        valeurs['log_loss'].append(ll/n)
        valeurs['brier'].append(br/n)
        valeurs['gain_log_loss'].append((ll0-ll)/n)
        valeurs['gain_brier'].append((br0-br)/n)
    return {nom: _intervalle(vals) for nom, vals in valeurs.items()}


def _bloc(rows, predictions, bootstrap=2000, graine=20261028):
    n = len(rows)
    if not n:
        return {'n': 0, 'semaines': 0, 'lecture': 'aucun match observé'}
    y = [r['y'] for r in rows]
    neutres = [.5]*n
    metriques = ST._metriques(y, predictions)
    exactes = sum((p > .5) == bool(cible) for p, cible in zip(predictions, y))
    metriques['ic95_exactitude_wilson'] = wilson(exactes, n)
    semaines = len({r['semaine'] for r in rows})
    fragile = n < 30 or semaines < 4
    return {
        'n': n, 'semaines': semaines,
        'neutre_50': ST._metriques(y, neutres),
        'profils_global': metriques,
        'gains_contre_neutre': ST._gains(y, neutres, predictions),
        'ic95_bootstrap_semaine': _bootstrap(rows, predictions, bootstrap, graine),
        'estimation_fragile': fragile,
        'lecture': ('estimation fragile : moins de 30 matchs ou de quatre semaines' if fragile
                    else 'estimation descriptive ; pas une confirmation prospective indépendante'),
    }


def _analyse(rows, predictions, bootstrap):
    blocs = {}
    for a, b, cle in paires():
        indices = [i for i, r in enumerate(rows) if r['paire_styles'] == cle]
        blocs[cle] = {
            'styles': [a, b],
            'noms': [NOMS[a], NOMS[b]],
            **_bloc([rows[i] for i in indices], [predictions[i] for i in indices],
                    bootstrap, 20261028 + sum(cle.encode())),
        }
    return blocs


def evaluer(rows, coupure=dt.date(2025, 1, 1), bootstrap=2000):
    dec = [r for r in rows if r['date'] < coupure]
    conf = [r for r in rows if r['date'] >= coupure]
    modele = ST._ajuster([SS._variables(r, 'global') for r in dec], [r['y'] for r in dec])
    p_dec = ST._predire(modele, [SS._variables(r, 'global') for r in dec])
    p_conf = ST._predire(modele, [SS._variables(r, 'global') for r in conf])
    matrices = {
        'decouverte': _analyse(dec, p_dec, bootstrap),
        'confirmation': _analyse(conf, p_conf, bootstrap),
    }
    return {
        'schema': 'matrice_styles_v1',
        'n': len(rows), 'n_decouverte': len(dec), 'n_confirmation': len(conf),
        'coupure': coupure.isoformat(),
        'modele': 'bilan global seul ; régression logistique ridge 1.0 ajustée sur 2024 puis figée',
        'modele_complet_decouverte': modele,
        'reference': 'probabilité neutre de 50 % sur exactement les mêmes matchs',
        'paires': '21 paires non orientées ; les cinq styles réels et indéterminé sont tous conservés',
        'orientation_resultat': 'joueur home alphabétique ; la paire de styles est non orientée',
        'incertitude': {
            'exactitude': 'IC95 de Wilson',
            'log_loss_brier_et_gains': 'IC95 bootstrap par semaine ISO, 2 000 répétitions par défaut',
            'fragile': 'moins de 30 matchs ou moins de quatre semaines',
        },
        'matrices': matrices,
        'n_paires_avec_au_moins_30_confirmation': sum(
            b['n'] >= 30 for b in matrices['confirmation'].values()),
        'nature_confirmation': 'diagnostic historique 2025–2026 réutilisé ; pas une confirmation prospective nouvelle',
        'selection_sous_groupe': False,
        'marche_utilise': False,
        'activation': False,
        'champion_actif_modifie': False,
        'verdict': 'matrice descriptive exhaustive ; aucun duel sélectionné et champion inchangé',
        'regle': 'aucune cote, aucun résultat futur, aucune activation à partir des paires historiques',
    }


def _f(v):
    return '—' if v is None else f'{v:.6f}'.replace('.', ',')


def _ic(bloc, nom):
    x = (bloc.get('ic95_bootstrap_semaine') or {}).get(nom)
    return '—' if not x else f"[{_f(x['bas'])} ; {_f(x['haut'])}]"


def markdown(rapport):
    lignes = [
        '# Matrice des paires de styles', '',
        'Modèle figé : **bilan global seul**, appris sur 2024. Référence : 50 %. '
        'La période 2025–2026 est un diagnostic historique réutilisé.', '',
        'Les IC d’exactitude sont ceux de Wilson. Les IC des gains sont des bootstraps '
        'par semaine ISO. Une estimation est fragile sous 30 matchs ou quatre semaines.', '',
        '| Paire de styles | n | Sem. | Log loss | Brier | Exactitude [IC95] | Gain log loss [IC95] | Gain Brier [IC95] |',
        '|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for a, b, cle in paires():
        bloc = rapport['matrices']['confirmation'][cle]
        nom = f"{NOMS[a]} × {NOMS[b]}"
        if not bloc['n']:
            lignes.append(f'| {nom} ⚠ | 0 | 0 | — | — | — | — | — |')
            continue
        m = bloc['profils_global']
        g = bloc['gains_contre_neutre']
        fragile = ' ⚠' if bloc['estimation_fragile'] else ''
        lignes.append(
            f"| {nom}{fragile} | {bloc['n']} | {bloc['semaines']} | {_f(m['log_loss'])} | {_f(m['brier'])} | "
            f"{m['reussite_pct']:.2f} % {m['ic95_exactitude_wilson']} | "
            f"{_f(g['log_loss'])} {_ic(bloc, 'gain_log_loss')} | "
            f"{_f(g['brier'])} {_ic(bloc, 'gain_brier')} |")
    lignes += ['', '**Aucune paire n’est sélectionnée ou activée à partir de ce tableau.** '
               'Les petits effectifs et les comparaisons multiples interdisent une conclusion causale ou prospective.', '']
    return '\n'.join(lignes)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('archive')
    parser.add_argument('racine', nargs='?', default='.')
    parser.add_argument('--maximum', type=int, default=8000)
    parser.add_argument('--bootstrap', type=int, default=2000)
    args = parser.parse_args(argv)
    M = donnees.charger(args.archive, 2021)
    choisis = PR.selection(M, dt.date(2024, 1, 1), args.maximum)
    rows = SV.observations(M, choisis)
    out = evaluer(rows, bootstrap=args.bootstrap)
    dossier = os.path.join(args.racine, 'simulateur')
    with open(os.path.join(dossier, 'rapport_matrice_styles.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open(os.path.join(dossier, 'rapport_matrice_styles.md'), 'w', encoding='utf-8') as f:
        f.write(markdown(out))
    print(json.dumps({
        'n': out['n'], 'n_decouverte': out['n_decouverte'], 'n_confirmation': out['n_confirmation'],
        'paires_avec_au_moins_30_confirmation': out['n_paires_avec_au_moins_30_confirmation'],
        'effectifs_confirmation': {cle: b['n'] for cle, b in out['matrices']['confirmation'].items()},
        'verdict': out['verdict'],
    }, ensure_ascii=False, indent=2))
    return out


if __name__ == '__main__':
    main()
