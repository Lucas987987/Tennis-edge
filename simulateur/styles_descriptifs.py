#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bilans descriptifs d'un joueur contre le style service–retour adverse.

Les catégories sont INTERNES et reproductibles : elles ne reprennent pas les
étiquettes d'un site tiers. À chaque match historique, le style de l'adversaire
est figé avec les seules feuilles déjà disponibles ; le résultat du match n'est
ajouté au bilan qu'ensuite. Les profils de service sont libérés après la fin du
tournoi, comme dans styles_joueurs.py.

Ce module ne produit aucune probabilité et ne modifie aucun pronostic. Sa sortie
est fusionnée à la vitrine par vitrine.py, uniquement pour l'affichage.

Usage : python simulateur/styles_descriptifs.py <archive Sackmann> [racine]
Sortie : simulateur/styles_descriptifs.json (artefact régénéré, non commité).
"""
import datetime as dt
import heapq
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees  # noqa: E402
import elo as E  # noqa: E402
import feuilles as FE  # noqa: E402
import nos_resultats as NR  # noqa: E402
import profils_service as PS  # noqa: E402
import pronostics_du_jour as PD  # noqa: E402
import styles_ajustes as SA  # noqa: E402
import styles_global as SG  # noqa: E402

SORTIE = os.path.join('simulateur', 'styles_descriptifs.json')
MIN_BALLES_STYLE = 500.0
SEUIL_SERVICE = .020
SEUIL_ACE = .020
SEUIL_RETOUR = .015
SEUIL_CONTRE_SERVICE = -.010
SEUIL_CONTRE_RETOUR = .010
STYLES = ('grand_serveur', 'serveur_attaquant', 'retourneur_pressant', 'contreur', 'equilibre', 'indetermine')
SURFACES = ('Hard', 'Clay', 'Grass')
TOUS_STYLES = '__tous__'
SOMMES_STATS = ('svpt', 'in1', 'w1', 'w2', 'ace', 'df', 'bpf', 'bps',
                'ret_svpt', 'ret_won', 'bp_obtenues', 'bp_converties')


def _service(p):
    return .60 * p['w1'] + .40 * p['w2j']


def _retour(p):
    # r1/r2j sont les points gagnés par le serveur adverse.
    return 1.0 - (.60 * p['r1'] + .40 * p['r2j'])


def classifier(profil, balles_effectives, moyenne, minimum=MIN_BALLES_STYLE):
    """Style observable, sans prétendre mesurer le lift ou la longueur des rallyes."""
    if not profil or balles_effectives < minimum:
        return 'indetermine'
    ds = _service(profil) - _service(moyenne)
    dr = _retour(profil) - _retour(moyenne)
    da = profil['a'] - moyenne['a']
    if ds >= SEUIL_SERVICE and da >= SEUIL_ACE:
        return 'grand_serveur'
    if ds >= SEUIL_SERVICE:
        return 'serveur_attaquant'
    if dr >= SEUIL_RETOUR and ds > SEUIL_CONTRE_SERVICE:
        return 'retourneur_pressant'
    if dr >= SEUIL_CONTRE_RETOUR and ds <= SEUIL_CONTRE_SERVICE:
        return 'contreur'
    return 'equilibre'


def wilson(victoires, n, z=1.959963984540054):
    """Intervalle de Wilson à 95 %, en points de pourcentage."""
    if not n:
        return None
    p = victoires / n
    den = 1 + z*z/n
    centre = (p + z*z/(2*n)) / den
    marge = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return [round(100*max(0.0, centre-marge), 1), round(100*min(1.0, centre+marge), 1)]


def documentation(n):
    if n < 10:
        return 'tres_faible'
    if n < 30:
        return 'faible'
    if n < 100:
        return 'intermediaire'
    return 'large'


def _pct(num, den):
    return round(100.0 * num / den, 1) if den > 0 else None


def _stats_match(m, victoire):
    """Sommes du joueur, sans utiliser son résultat pour figer le style adverse."""
    if not m.get('detail'):
        return None
    moi = m['detail']['w' if victoire else 'l']
    adv = m['detail']['l' if victoire else 'w']
    svpt, in1, w1, w2, ace, df, bpf, bps = moi[:8]
    osvpt, _, ow1, ow2, _, _, obpf, obps = adv[:8]
    return dict(zip(SOMMES_STATS, (svpt, in1, w1, w2, ace, df, bpf, bps,
                                  osvpt, osvpt - ow1 - ow2, obpf, obpf - obps)))


def statistiques(ligne, reference=None):
    """Taux bruts contre ce style et écart descriptif à tous les adversaires.

    Les numérateurs et dénominateurs restent agrégés : il ne s'agit pas d'une
    moyenne non pondérée de pourcentages de matchs, ni d'un effet causal du style.
    """
    if not ligne or not ligne.get('stats_n'):
        return None
    s = ligne['sommes']
    sec = s['svpt'] - s['in1']
    out = {
        'matchs': ligne['stats_n'], 'documentation': documentation(ligne['stats_n']),
        'points_service': s['svpt'], 'points_retour': s['ret_svpt'],
        'service_gagnes_pct': _pct(s['w1'] + s['w2'], s['svpt']),
        'retour_gagnes_pct': _pct(s['ret_won'], s['ret_svpt']),
        'points_gagnes_pct': _pct(s['w1'] + s['w2'] + s['ret_won'], s['svpt'] + s['ret_svpt']),
        'premiere_balle_pct': _pct(s['in1'], s['svpt']),
        'gagnes_1re_pct': _pct(s['w1'], s['in1']),
        'gagnes_2e_pct': _pct(s['w2'], sec),
        'aces_pct': _pct(s['ace'], s['svpt']),
        'doubles_fautes_pct': _pct(s['df'], sec),
        'balles_break_sauvees_pct': _pct(s['bps'], s['bpf']),
        'balles_break_converties_pct': _pct(s['bp_converties'], s['bp_obtenues']),
    }
    ref = statistiques(reference) if reference else None
    cles = tuple(k for k in out if k.endswith('_pct'))
    out['ecarts_tous_styles_points'] = {
        k: round(out[k] - ref[k], 1) if ref and out[k] is not None and ref.get(k) is not None else None
        for k in cles
    }
    return out


def variables_statistiques(acc, h, a, style_h, style_a):
    """Variables du challenger : écarts home–away à la référence tous styles.

    Si l'un des deux joueurs n'a aucune feuille contre ce style, toutes les
    variables sont neutres et la documentation vaut zéro : une absence n'est pas
    transformée en avantage pour l'autre joueur.
    """
    def ecarts(joueur, style):
        stats = statistiques(acc.get((joueur, style, 'global')),
                             acc.get((joueur, TOUS_STYLES, 'global')))
        return ((stats['ecarts_tous_styles_points'], stats['matchs']) if stats else None)

    eh, ea = ecarts(h, style_a), ecarts(a, style_h)
    documente = eh is not None and ea is not None
    noms = ('points_gagnes_pct', 'service_gagnes_pct', 'retour_gagnes_pct',
            'gagnes_2e_pct', 'balles_break_sauvees_pct', 'balles_break_converties_pct')
    out = {f'stats_{nom}': (((eh[0].get(nom) or 0.0) - (ea[0].get(nom) or 0.0)) / 100.0
                           if documente else 0.0) for nom in noms}
    out['documentation_stats'] = min(eh[1], ea[1]) if documente else 0
    return out


def resume(ligne, reference=None):
    if not ligne:
        return {'n': 0, 'victoires': 0, 'pct': None, 'ic95': None,
                'documentation': 'tres_faible', 'derniers': [], 'statistiques': None}
    n, v = ligne['n'], ligne['v']
    out = {'n': n, 'victoires': v, 'pct': round(100*v/n, 1),
           'ic95': wilson(v, n), 'documentation': documentation(n),
           'derniers': list(reversed(ligne['derniers'][-5:])),
           'statistiques': statistiques(ligne, reference)}
    # 28/10/2026 — ATTENDU vu la force des adversaires : moyenne des probabilités Elo d'avant-match de ces mêmes
    # matchs. « 38 % contre ce style » ne dit rien seul : contre Djokovic et Alcaraz, on attendait déjà peu.
    if ligne.get('n_att'):
        att = 100 * ligne['att'] / ligne['n_att']
        out['attendu_pct'] = round(att, 1)
        out['ecart_pts'] = round(100 * v / n - att, 1)
    return out


def _score(m, du_perdant=False):
    sets = m.get('sets') or []
    if not sets:
        return None
    return ' '.join(f'{b}-{a}' if du_perdant else f'{a}-{b}' for a, b in sets)


def _evenement(m, joueur, adversaire, nom_adversaire, victoire, style_adverse, attendu=None):
    ev = {'date': m['date'].isoformat(), 'adversaire': nom_adversaire,
          'victoire': bool(victoire), 'score': _score(m, not victoire),
          'surface': m['surface'], 'tournoi': m.get('tournoi') or '',
          'style_adverse': style_adverse}
    if attendu is not None:
        ev['attendu_pct'] = round(100 * attendu, 1)
    return ev


def _ajouter(acc, joueur, style_adverse, surface, evenement, victoire, stats=None, attendu=None):
    for scope in ('global', surface):
        cle = (joueur, style_adverse, scope)
        ligne = acc.setdefault(cle, {'n': 0, 'v': 0, 'derniers': [], 'stats_n': 0,
                                    'sommes': {k: 0 for k in SOMMES_STATS}})
        ligne['n'] += 1
        ligne['v'] += int(victoire)
        ligne['derniers'].append(evenement)
        if stats is not None:
            ligne['stats_n'] += 1
            for k, valeur in stats.items():
                ligne['sommes'][k] += valeur
        if attendu is not None:
            ligne['att'] = ligne.get('att', 0.0) + attendu
            ligne['n_att'] = ligne.get('n_att', 0) + 1


def calculer(M, cibles, jour, demi_vie=PS.DEMI_VIE, prior_mult=1.0, avec_ajustes=False):
    """Calcule bilans et styles courants pour {clé joueur: {circuit, surface}}.

    `jour` est la date de référence pré-match. Les matchs incomplets et abandons
    sont exclus. Le résultat courant n'est jamais utilisé pour classifier les
    deux joueurs avant ce même match.
    """
    P, elo = PS.Profils(demi_vie, prior_mult), E.Elo()
    attente, serial, acc = [], 0, {}
    acc_ajuste = SA.Accumulateur()
    resultats_veille, residus_veille, jour_courant = [], [], None

    def enregistrer(m, sg, sp, p_g=None):
        g, p, surface = m['_g'], m['_p'], m['surface']
        p_p = None if p_g is None else 1 - p_g          # 28/10/2026 : attendu (Elo d'avant-match) de chacun
        if g in cibles:
            ev = _evenement(m, g, p, m.get('nom_p') or p, True, sp, p_g)
            stats = _stats_match(m, True)
            if sp != 'indetermine':
                _ajouter(acc, g, sp, surface, ev, True, stats, p_g)
            _ajouter(acc, g, TOUS_STYLES, surface, ev, True, stats, p_g)
        if p in cibles:
            ev = _evenement(m, p, g, m.get('nom_g') or g, False, sg, p_p)
            stats = _stats_match(m, False)
            if sg != 'indetermine':
                _ajouter(acc, p, sg, surface, ev, False, stats, p_p)
            _ajouter(acc, p, TOUS_STYLES, surface, ev, False, stats, p_p)

    for original in sorted(M, key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0))):
        m = original
        if m['date'] > jour:
            break  # aucun résultat postérieur à la référence pré-match
        if jour_courant != m['date']:
            for ancien, sg, sp, pe in resultats_veille:
                enregistrer(ancien, sg, sp, pe)
            for ancien in residus_veille:
                acc_ajuste.ajouter(*ancien)
            resultats_veille, residus_veille, jour_courant = [], [], m['date']
        debut = dt.datetime.combine(m['date'], dt.time())
        while attente and attente[0][0] < debut:
            _, _, ancien = heapq.heappop(attente)
            P.ajouter(ancien, ancien['_g'], ancien['_p'])
        g, p = m['_g'], m['_p']
        if not g or not p or g == p:
            continue
        circuit, surface = m['circuit'], m['surface']
        if circuit in ('CH', 'ITF'):
            elo.presenter(g, 1200.0)
            elo.presenter(p, 1200.0)
        p_elo_gagnant = elo.proba(g, p, surface)
        ig, ng = P.profil(g, circuit, surface, m['date'])
        ip, np = P.profil(p, circuit, surface, m['date'])
        mug = P.moyenne(circuit, surface)
        sg = classifier(ig, ng, mug)
        sp = classifier(ip, np, mug)
        if m.get('complet') and not m.get('abandon'):
            # Sans heure historique fiable, les résultats du même jour restent indisponibles.
            resultats_veille.append((m, sg, sp, p_elo_gagnant))
            residus_veille.append((g, p, sg, sp, surface, m['date'], p_elo_gagnant))
        heapq.heappush(attente, (dt.datetime.combine(m['fin'], dt.time()), serial, m))
        serial += 1
        elo.maj(g, p, surface, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') else None)
    if jour_courant is not None and jour_courant < jour:
        for ancien, sg, sp, pe in resultats_veille:
            enregistrer(ancien, sg, sp, pe)
        for ancien in residus_veille:
            acc_ajuste.ajouter(*ancien)
    reference = dt.datetime.combine(jour, dt.time())
    while attente and attente[0][0] < reference:
        _, _, ancien = heapq.heappop(attente)
        P.ajouter(ancien, ancien['_g'], ancien['_p'])
    courants = {}
    for joueur, cible in cibles.items():
        circuit, surface = cible['circuit'], cible['surface']
        profil, n = P.profil(joueur, circuit, surface, jour)
        courants[joueur] = {'style': classifier(profil, n, P.moyenne(circuit, surface)),
                            'balles_effectives': round(n, 1)}
    return (acc, courants, acc_ajuste) if avec_ajustes else (acc, courants)


def _cibles(racine, maintenant):
    with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
        etat = E.migrer_etat(json.load(f))
    # matchs_a_venir utilise historiquement des dates UTC naïves.
    venir = PD.matchs_a_venir(racine, maintenant.replace(tzinfo=None))
    alias = dict(etat.get('alias') or {})
    alias.update(E.unifier({k: v.get('nom', k) for k, v in etat['joueurs'].items()},
                           [n for x in venir for n in (x['home'], x['away'])]))
    cle_c = lambda n: alias.get(E.cle(n), E.cle(n))
    noms = [v.get('nom', k) for k, v in etat['joueurs'].items()] + [n for x in venir for n in (x['home'], x['away'])]
    ambigus = {c['cle'] for c in E.collisions_identite(noms)}
    surf = etat.get('surfaces_tournois') or {}
    cibles, matchs = {}, []
    for x in venir:
        h, a = cle_c(x['home']), cle_c(x['away'])
        surface = NR.surface_de(x['tournoi'], surf)
        circuit = PD.circuit(x['tournoi'])
        if (not h or not a or h == a or h in ambigus or a in ambigus or surface not in SURFACES):
            continue
        uid = f"{x['debut'].date()}_{NR.slug(x['home'])}_{NR.slug(x['away'])}"
        matchs.append(dict(x, uid=uid, h=h, a=a, surface=surface, circuit=circuit))
        cibles[h] = {'circuit': circuit, 'surface': surface}
        cibles[a] = {'circuit': circuit, 'surface': surface}
    return matchs, cibles


def _bloc(joueur, nom, propre, adverse, surface, acc):
    return {'joueur': nom, 'style': propre['style'],
            'balles_effectives': propre['balles_effectives'],
            'style_adverse': adverse['style'],
            'global': resume(acc.get((joueur, adverse['style'], 'global')),
                             acc.get((joueur, TOUS_STYLES, 'global'))),
            'surface': resume(acc.get((joueur, adverse['style'], surface)),
                              acc.get((joueur, TOUS_STYLES, surface)))}


def construire(racine, archive, maintenant=None):
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    matchs, cibles = _cibles(racine, maintenant)
    M = donnees.charger(archive, 2018)
    if not M:
        raise ValueError(f'aucun match Sackmann sous {archive}')
    fin_sack = max(m['date'] for m in M)
    F = [m for m in FE.charger(racine) if m['date'] > fin_sack]
    # Les cibles sont déjà résolues par _cibles ; pour l'historique, on recharge
    # la table d'alias complète afin de rattacher les écritures récentes.
    with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
        etat = E.migrer_etat(json.load(f))
    table_alias = dict(etat.get('alias') or {})
    cle_c = lambda n: table_alias.get(E.cle(n), E.cle(n))
    tout = []
    for m in M + F:
        n = dict(m)
        n['_g'], n['_p'] = cle_c(m.get('nom_g')), cle_c(m.get('nom_p'))
        tout.append(n)
    acc, courants, acc_ajuste = calculer(tout, cibles, maintenant.date(), avec_ajustes=True)
    out = {}
    for x in matchs:
        h, a, s = x['h'], x['a'], x['surface']
        if h not in courants or a not in courants:
            continue
        ajustes = acc_ajuste.variables(h, a, courants[h]['style'], courants[a]['style'], s, maintenant.date())
        ajustes.update({'challenger_seulement': True, 'schema': SA.SCHEMA,
                        'styles': [courants[h]['style'], courants[a]['style']],
                        'reference': 'résultat moins probabilité Elo pré-match ; demi-vie 365 j ; prior 20'})
        global_styles = SG.variables(acc, h, a, courants[h]['style'], courants[a]['style'])
        global_styles.update({'challenger_seulement': True, 'schema': SG.SCHEMA,
                              'styles': [courants[h]['style'], courants[a]['style']],
                              'matrice_paires': 'descriptive ; aucun bonus par paire'})
        statistiques_styles = variables_statistiques(acc, h, a, courants[h]['style'], courants[a]['style'])
        statistiques_styles.update({
            'challenger_seulement': True, 'schema': 'statistiques_styles_adverses_v1',
            'styles': [courants[h]['style'], courants[a]['style']],
            'bilan_global': global_styles['bilan_global'], 'surface_cible': 'Hard',
            'selection': 'sous-groupe dur repéré après le diagnostic global ; confirmation prospective obligatoire'})
        out[x['uid']] = {
            'descriptif_seulement': True,
            'joueurs': [_bloc(h, x['home'], courants[h], courants[a], s, acc),
                        _bloc(a, x['away'], courants[a], courants[h], s, acc)],
            'styles_ajustes': ajustes, 'styles_global': global_styles,
            'statistiques_styles': statistiques_styles}
    return {'schema': 'styles_descriptifs_v1', 'genere_le': maintenant.isoformat(timespec='seconds'),
            'archive_jusqu_au': fin_sack.isoformat(), 'feuilles_recentes': len(F),
            'minimum_balles_style': MIN_BALLES_STYLE,
            'styles_ajustes': {'schema': SA.SCHEMA, 'demi_vie_jours': SA.DEMI_VIE_J,
                               'prior_matchs_equivalents': SA.PRIOR_MATCHS, 'activation': False},
            'styles_global': {'schema': SG.SCHEMA, 'prior_matchs_par_bilan': SG.PRIOR_MATCHS,
                              'second_avis_seulement': True, 'activation': False},
            'statistiques_styles': {
                'reference': 'tous les adversaires du même joueur, sur le même périmètre global ou surface',
                'ecarts': 'différence en points de pourcentage ; description, pas effet causal du style',
                'activation': False, 'change_le_pronostic': False,
                'couverture': 'matchs avec deux feuilles de service cohérentes ; effectif distinct du bilan V/D'},
            'regle': ('Style service–retour interne figé avant chaque match ; résultats et statistiques ajoutés ensuite. '
                      'Bilans et statistiques bruts descriptifs ; résidus ajustés et second avis global réservés aux challengers non actifs.'),
            'seuils': {'service': SEUIL_SERVICE, 'ace': SEUIL_ACE, 'retour': SEUIL_RETOUR,
                       'contre_service': SEUIL_CONTRE_SERVICE, 'contre_retour': SEUIL_CONTRE_RETOUR},
            'matchs': out}


def main(argv=None):
    argv = argv or sys.argv
    if len(argv) < 2:
        print('Usage : python simulateur/styles_descriptifs.py <archive Sackmann> [racine]')
        return 2
    archive = argv[1]
    racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    doc = construire(racine, archive)
    chemin = os.path.join(racine, SORTIE)
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    n = len(doc['matchs'])
    print(f'Styles descriptifs : {n} matchs · archive jusqu’au {doc["archive_jusqu_au"]} · {chemin}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
