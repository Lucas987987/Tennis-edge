"""Interactions service–retour horodatées, évaluées comme challenger indépendant.

Un profil n'existe qu'avec les feuilles dont le tournoi est terminé avant le match.
L'interaction est symétrique et ne consulte ni cote ni résultat du match courant.
Le champion reste la victoire pure des profils hiérarchiques ; aucune promotion automatique.
"""
import argparse
import datetime as dt
import heapq
import json
import math
import os
import random

import donnees
import elo as E
import match_simule as MS
import profils_service as PS
import profils_robustes as PR

LAMBDAS = (0.0, .005, .01, .02)
MIN_DECOUVERTE = 100
MIN_CONFIRMATION = 100
MARGE = .001


def _lg(p):
    p = min(max(float(p), 1e-6), 1-1e-6)
    return math.log(p/(1-p))


def _sg(z):
    return 1/(1+math.exp(-max(-40, min(40, z))))


def instantane(P, joueur, circuit, surface, jour):
    """Photographie pré-match explicite : jour de validité et documentation effective."""
    profil, n = P.profil(joueur, circuit, surface, jour)
    return {'joueur': joueur, 'disponible_avant': jour.isoformat(), 'balles_effectives': round(n, 2),
            'profil': profil}


def _force_service(p):
    return .60*p['w1'] + .40*p['w2j']


def _faiblesse_retour(p):
    # r1/r2j sont les points gagnés par le serveur adverse : haut = retour plus perméable.
    return .60*p['r1'] + .40*p['r2j']


def interaction(ph, pa, mu):
    """Interaction de styles, centrée sur le circuit et bornée contre les profils extrêmes."""
    sh, sa = (_force_service(ph)-_force_service(mu))/.05, (_force_service(pa)-_force_service(mu))/.05
    ra, rh = (_faiblesse_retour(pa)-_faiblesse_retour(mu))/.05, (_faiblesse_retour(ph)-_faiblesse_retour(mu))/.05
    return max(-4.0, min(4.0, sh*ra-sa*rh))


def evaluer(M, choisis, coupure, demi_vie=PS.DEMI_VIE, prior_mult=1.0, sigma=.15):
    P = PS.Profils(demi_vie, prior_mult)
    attente, serial = [], 0
    pertes = {x: {'decouverte': [], 'confirmation': []} for x in LAMBDAS}
    for m in M:
        debut = dt.datetime.combine(m['date'], dt.time())
        while attente and attente[0][0] < debut:
            _, _, ancien = heapq.heappop(attente)
            P.ajouter(ancien)  # disponible seulement après la fin réelle du tournoi
        if id(m) in choisis:
            h, a = m['gagnant'], m['perdant']  # orientation fixe du backtest, comme le champion
            ih, ia = instantane(P, h, m['circuit'], m['surface'], m['date']), instantane(P, a, m['circuit'], m['surface'], m['date'])
            mu = P.moyenne(m['circuit'], m['surface'])
            ch, ca = MS.composantes(ih['profil'], ia['profil'], mu), MS.composantes(ia['profil'], ih['profil'], mu)
            p0 = MS.victoire_pure(ch, ca, m['bo']//2+1, sigma)
            z = interaction(ih['profil'], ia['profil'], mu)
            periode = 'decouverte' if m['date'] < coupure else 'confirmation'
            for lam in LAMBDAS:
                p = _sg(_lg(p0)+lam*z)
                pertes[lam][periode].append(-math.log(min(1-1e-12, max(1e-12, p))))
        heapq.heappush(attente, (dt.datetime.combine(m['fin'], dt.time()), serial, m))
        serial += 1
    return {str(lam): {periode: PR._resume(vals) for periode, vals in groupes.items()}
            for lam, groupes in pertes.items()}


def decider(rapports):
    base = rapports[str(0.0)]
    eligibles = [x for x in LAMBDAS if x and rapports[str(x)]['decouverte']['n'] >= MIN_DECOUVERTE
                 and rapports[str(x)]['confirmation']['n'] >= MIN_CONFIRMATION]
    if not eligibles:
        return {'adopte': False, 'challenger': None, 'raison': 'échantillon insuffisant ; champion inchangé'}
    meilleur = min(eligibles, key=lambda x: rapports[str(x)]['decouverte']['log_loss'])
    gain = base['confirmation']['log_loss']-rapports[str(meilleur)]['confirmation']['log_loss']
    return {'adopte': gain >= MARGE, 'challenger': 'interaction_service_retour', 'lambda': meilleur,
            'gain_log_loss_confirmation': round(gain, 6), 'marge': MARGE,
            'll_champion': base['confirmation']['log_loss'], 'll_challenger': rapports[str(meilleur)]['confirmation']['log_loss'],
            'raison': 'challenger choisi sur découverte seulement, puis jugé sur confirmation disjointe'}


def _semaine(jour):
    annee, semaine, _ = jour.isocalendar()
    return f'{annee}-S{semaine:02d}'


def observations_controle(M, choisis, demi_vie=PS.DEMI_VIE, prior_mult=1.0, sigma=.15):
    """Observations pré-match orientées sans regarder le résultat.

    L'orientation alphabétique évite le biais de l'ancien backtest qui plaçait
    toujours le futur vainqueur à home. Elo est mis à jour APRÈS chaque match ;
    les profils service–retour ne sont libérés qu'après la fin du tournoi.
    """
    P, elo = PS.Profils(demi_vie, prior_mult), E.Elo()
    attente, serial, out = [], 0, []
    for m in M:
        debut = dt.datetime.combine(m['date'], dt.time())
        while attente and attente[0][0] < debut:
            _, _, ancien = heapq.heappop(attente)
            P.ajouter(ancien)
        gagnant, perdant = m['gagnant'], m['perdant']
        if m['circuit'] in ('CH', 'ITF'):
            elo.presenter(gagnant, 1200.0)
            elo.presenter(perdant, 1200.0)
        if id(m) in choisis:
            # Ordre indépendant du vainqueur : y vaut donc 0 ou 1.
            h, a = sorted((gagnant, perdant))
            ih, ia = instantane(P, h, m['circuit'], m['surface'], m['date']), instantane(P, a, m['circuit'], m['surface'], m['date'])
            mu = P.moyenne(m['circuit'], m['surface'])
            ch, ca = MS.composantes(ih['profil'], ia['profil'], mu), MS.composantes(ia['profil'], ih['profil'], mu)
            out.append({
                'date': m['date'], 'semaine': _semaine(m['date']), 'y': int(gagnant == h),
                'elo': elo.proba(h, a, m['surface']),
                'service_retour': MS.victoire_pure(ch, ca, m['bo']//2+1, sigma),
                'style': interaction(ih['profil'], ia['profil'], mu),
                'surface': m['surface'], 'circuit': m['circuit'],
                'documentation_balles': min(ih['balles_effectives'], ia['balles_effectives']),
                'documentation_matchs': min(elo.matchs(h), elo.matchs(a)),
            })
        heapq.heappush(attente, (dt.datetime.combine(m['fin'], dt.time()), serial, m))
        serial += 1
        elo.maj(gagnant, perdant, m['surface'], m.get('niveau') == 'G',
                E.part_jeux(m['sets']) if m.get('complet') else None)
    return out


def _variables(r, avec_style=False):
    x = [1.0, _lg(r['elo']), _lg(r['service_retour']),
         float(r['surface'] == 'Clay'), float(r['surface'] == 'Grass'),
         float(r['circuit'] == 'WTA'), float(r['circuit'] == 'CH'), float(r['circuit'] == 'ITF'),
         math.log1p(max(0.0, r['documentation_balles'])),
         math.log1p(max(0.0, r['documentation_matchs'])),
         float(r['documentation_balles'] < 500)]
    return x + ([r['style']] if avec_style else [])


def _standardisation(X):
    moyennes, ecarts = [0.0] * len(X[0]), [1.0] * len(X[0])
    for j in range(1, len(X[0])):
        moyennes[j] = sum(x[j] for x in X) / len(X)
        variance = sum((x[j] - moyennes[j]) ** 2 for x in X) / len(X)
        ecarts[j] = math.sqrt(variance) if variance > 1e-12 else 1.0
    return moyennes, ecarts


def _matrice(X, moyennes, ecarts):
    return [[1.0 if j == 0 else (x[j] - moyennes[j]) / ecarts[j]
             for j in range(len(x))] for x in X]


def _objectif(X, y, beta, ridge):
    total = 0.0
    for x, cible in zip(X, y):
        z = max(-40.0, min(40.0, sum(a*b for a, b in zip(x, beta))))
        total += cible * z - math.log1p(math.exp(z))
    return total - .5 * ridge * sum(b*b for b in beta[1:])


def _resoudre(A, b):
    """Pivot de Gauss pour le petit système de Newton (aucune dépendance externe)."""
    n = len(b)
    A, b = [list(row) + [b[i]] for i, row in enumerate(A)], list(range(n))
    for i in range(n):
        pivot = max(range(i, n), key=lambda k: abs(A[k][i]))
        A[i], A[pivot] = A[pivot], A[i]
        if abs(A[i][i]) < 1e-12:
            A[i][i] = 1e-12
        for k in range(i + 1, n):
            facteur = A[k][i] / A[i][i]
            for j in range(i, n + 1):
                A[k][j] -= facteur * A[i][j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (A[i][n] - sum(A[i][j] * x[j] for j in range(i + 1, n))) / A[i][i]
    return x


def _ajuster(X, y, ridge=1.0, iterations=50):
    """Régression logistique ridge, ajustée uniquement sur la découverte."""
    if not X or len(set(y)) < 2:
        return None
    moyennes, ecarts = _standardisation(X)
    Z = _matrice(X, moyennes, ecarts)
    beta = [0.0] * len(Z[0])
    converged = False
    for _ in range(iterations):
        p = [_sg(sum(a*b for a, b in zip(x, beta))) for x in Z]
        gradient = [sum((cible - pi) * x[j] for x, pi, cible in zip(Z, p, y)) for j in range(len(beta))]
        hessien = [[sum(pi * (1-pi) * x[j] * x[k] for x, pi in zip(Z, p))
                    for k in range(len(beta))] for j in range(len(beta))]
        for j in range(1, len(beta)):
            gradient[j] -= ridge * beta[j]
            hessien[j][j] += ridge
        hessien[0][0] += 1e-8
        delta = _resoudre(hessien, gradient)
        if max(abs(v) for v in delta) < 1e-7:
            converged = True
            break
        ancien = _objectif(Z, y, beta, ridge)
        pas = 1.0
        for _ in range(20):
            candidat = [b + pas*d for b, d in zip(beta, delta)]
            if _objectif(Z, y, candidat, ridge) >= ancien - 1e-10:
                beta = candidat
                break
            pas *= .5
        else:
            break
    return {'beta': beta, 'moyennes': moyennes, 'ecarts': ecarts, 'converged': converged}


def _predire(modele, X):
    if modele is None:
        return []
    Z = _matrice(X, modele['moyennes'], modele['ecarts'])
    return [_sg(sum(a*b for a, b in zip(x, modele['beta']))) for x in Z]


def _metriques(y, p):
    if not y:
        return {'n': 0}
    if len(y) != len(p):
        return {'n': len(y), 'log_loss': None, 'brier': None, 'reussite_pct': None}
    ll = sum(-math.log(min(1-1e-12, max(1e-12, pi if cible else 1-pi))) for cible, pi in zip(y, p)) / len(y)
    brier = sum((pi-cible) ** 2 for cible, pi in zip(y, p)) / len(y)
    exact = sum((pi > .5) == bool(cible) for cible, pi in zip(y, p)) / len(y)
    return {'n': len(y), 'log_loss': round(ll, 6), 'brier': round(brier, 6),
            'reussite_pct': round(100*exact, 2)}


def _gains(y, sans, avec):
    a, b = _metriques(y, sans), _metriques(y, avec)
    if not y or a.get('log_loss') is None or b.get('log_loss') is None:
        return {'log_loss': None, 'brier': None}
    return {'log_loss': round(a['log_loss']-b['log_loss'], 6),
            'brier': round(a['brier']-b['brier'], 6),
            'sens': 'positif = apport des styles'}


def _ic_gains(rows, sans, avec, repetitions=2000, graine=20261027):
    semaines = sorted({r['semaine'] for r in rows})
    if len(semaines) < 2 or repetitions <= 0:
        return {'log_loss': None, 'brier': None}
    groupes = {s: [i for i, r in enumerate(rows) if r['semaine'] == s] for s in semaines}
    rnd, valeurs = random.Random(graine), {'log_loss': [], 'brier': []}
    for _ in range(repetitions):
        indices = [i for s in (rnd.choice(semaines) for _ in semaines) for i in groupes[s]]
        gains = _gains([rows[i]['y'] for i in indices], [sans[i] for i in indices], [avec[i] for i in indices])
        for k in valeurs:
            valeurs[k].append(gains[k])
    out = {}
    for k, vals in valeurs.items():
        vals.sort()
        out[k] = {'bas': round(vals[int(.025*(len(vals)-1))], 6),
                  'haut': round(vals[int(.975*(len(vals)-1))], 6)}
    return out


def evaluer_controle(M, choisis, coupure, demi_vie=PS.DEMI_VIE, prior_mult=1.0,
                     sigma=.15, bootstrap=2000):
    """Apport incrémental des styles après contrôles pré-match, sans activation.

    Le champion contrôlé contient Elo, surface, circuit, service–retour et deux
    mesures de documentation. Le challenger ajoute seulement l'interaction de
    styles. Les coefficients sont appris sur découverte puis figés pour confirmation.
    """
    rows = observations_controle(M, choisis, demi_vie, prior_mult, sigma)
    dec = [r for r in rows if r['date'] < coupure]
    conf = [r for r in rows if r['date'] >= coupure]
    X0 = [_variables(r) for r in dec]
    X1 = [_variables(r, True) for r in dec]
    y_dec = [r['y'] for r in dec]
    m0, m1 = _ajuster(X0, y_dec), _ajuster(X1, y_dec)
    y_conf = [r['y'] for r in conf]
    sans = _predire(m0, [_variables(r) for r in conf])
    avec = _predire(m1, [_variables(r, True) for r in conf])
    p_dec0, p_dec1 = _predire(m0, X0), _predire(m1, X1)
    groupes = {'global': list(range(len(conf)))}
    for surface in ('Hard', 'Clay', 'Grass'):
        groupes[f'surface:{surface}'] = [i for i, r in enumerate(conf) if r['surface'] == surface]
    for nom, test in (
            ('documentation:<100_balles', lambda r: r['documentation_balles'] < 100),
            ('documentation:100-499_balles', lambda r: 100 <= r['documentation_balles'] < 500),
            ('documentation:>=500_balles', lambda r: r['documentation_balles'] >= 500)):
        groupes[nom] = [i for i, r in enumerate(conf) if test(r)]
    sous_groupes = {}
    for nom, indices in groupes.items():
        if nom == 'global' or len(indices) < 30:
            continue
        yy = [y_conf[i] for i in indices]
        sous_groupes[nom] = {'sans_styles': _metriques(yy, [sans[i] for i in indices]),
                             'avec_styles': _metriques(yy, [avec[i] for i in indices]),
                             'gains': _gains(yy, [sans[i] for i in indices], [avec[i] for i in indices])}
    gains = _gains(y_conf, sans, avec)
    assez = len(dec) >= MIN_DECOUVERTE and len(conf) >= MIN_CONFIRMATION
    out = {
        'n': len(rows), 'n_decouverte': len(dec), 'n_confirmation': len(conf),
        'coupure': coupure.isoformat(), 'orientation': 'ordre alphabétique des identifiants, indépendant du résultat',
        'controles': ['Elo général et surface', 'surface', 'circuit', 'service–retour pur',
                      'balles effectives minimales', 'matchs Elo minimaux', 'indicateur moins de 500 balles'],
        'ajout_challenger': 'interaction service–retour de styles seule',
        'modeles_ajustes_sur': 'découverte seulement ; coefficients figés sur confirmation',
        'convergence': {'sans_styles': bool(m0 and m0['converged']), 'avec_styles': bool(m1 and m1['converged'])},
        'decouverte': {'sans_styles': _metriques(y_dec, p_dec0), 'avec_styles': _metriques(y_dec, p_dec1)},
        'confirmation': {'sans_styles': _metriques(y_conf, sans), 'avec_styles': _metriques(y_conf, avec),
                         'gains': gains, 'ic95_bootstrap_semaine': _ic_gains(conf, sans, avec, bootstrap)},
        'sous_groupes_confirmation': sous_groupes,
        'activation': False,
        'verdict': ('apport à reproduire, sans activation automatique'
                    if assez and gains['log_loss'] is not None and gains['brier'] is not None
                    and gains['log_loss'] >= MARGE and gains['brier'] >= 0
                    else 'apport non confirmé ; champion inchangé' if assez
                    else 'échantillon insuffisant ; champion inchangé'),
        'regle': 'aucune cote, aucun résultat futur, aucune modification du modèle actif',
    }
    return out


def main(archive, racine='.', maximum=2000, coupure=dt.date(2025, 1, 1), debut=dt.date(2024, 1, 1)):
    M = donnees.charger(archive, 2021)
    choisis = PR.selection(M, debut, maximum)
    try:
        choix = json.load(open(os.path.join(racine, 'simulateur', 'choix_simulation.json'), encoding='utf-8'))
        reglage = choix.get('profils_hierarchiques') or {}
        actif = reglage if reglage.get('adopte') else {}
    except (OSError, ValueError):
        actif = {}
    demi_vie = actif.get('demi_vie', PS.DEMI_VIE)
    prior_mult = actif.get('prior_mult', 1.0)
    rapports = evaluer(M, choisis, coupure, demi_vie=demi_vie, prior_mult=prior_mult)
    controle = evaluer_controle(M, choisis, coupure, demi_vie=demi_vie, prior_mult=prior_mult)
    out = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(),
           'champion_profil': {'demi_vie': demi_vie, 'prior_mult': prior_mult},
           'coupure': coupure.isoformat(), 'n': len(choisis), 'lambdas': list(LAMBDAS),
           'regle': 'profils disponibles après fin des matchs seulement ; aucune variable de marché ; champion inchangé par ce rapport',
           'candidats': rapports, 'decision': decider(rapports),
           'controle_incremental': controle}
    path = os.path.join(racine, 'simulateur', 'rapport_styles_joueurs.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('Styles :', out['decision'], flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('archive')
    ap.add_argument('--racine', default='.')
    ap.add_argument('--max', type=int, default=2000)
    args = ap.parse_args()
    main(args.archive, args.racine, args.max)
