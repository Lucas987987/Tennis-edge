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

SORTIE = os.path.join('simulateur', 'styles_descriptifs.json')
MIN_BALLES_STYLE = 500.0
SEUIL_SERVICE = .020
SEUIL_ACE = .020
SEUIL_RETOUR = .015
SEUIL_CONTRE_SERVICE = -.010
SEUIL_CONTRE_RETOUR = .010
STYLES = ('grand_serveur', 'serveur_attaquant', 'retourneur_pressant', 'contreur', 'equilibre', 'indetermine')
SURFACES = ('Hard', 'Clay', 'Grass')


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


def resume(ligne):
    if not ligne:
        return {'n': 0, 'victoires': 0, 'pct': None, 'ic95': None,
                'documentation': 'tres_faible', 'derniers': []}
    n, v = ligne['n'], ligne['v']
    return {'n': n, 'victoires': v, 'pct': round(100*v/n, 1),
            'ic95': wilson(v, n), 'documentation': documentation(n),
            'derniers': list(reversed(ligne['derniers'][-5:]))}


def _score(m, du_perdant=False):
    sets = m.get('sets') or []
    if not sets:
        return None
    return ' '.join(f'{b}-{a}' if du_perdant else f'{a}-{b}' for a, b in sets)


def _evenement(m, joueur, adversaire, nom_adversaire, victoire, style_adverse):
    return {'date': m['date'].isoformat(), 'adversaire': nom_adversaire,
            'victoire': bool(victoire), 'score': _score(m, not victoire),
            'surface': m['surface'], 'tournoi': m.get('tournoi') or '',
            'style_adverse': style_adverse}


def _ajouter(acc, joueur, style_adverse, surface, evenement, victoire):
    for scope in ('global', surface):
        cle = (joueur, style_adverse, scope)
        ligne = acc.setdefault(cle, {'n': 0, 'v': 0, 'derniers': []})
        ligne['n'] += 1
        ligne['v'] += int(victoire)
        ligne['derniers'].append(evenement)


def calculer(M, cibles, jour, demi_vie=PS.DEMI_VIE, prior_mult=1.0):
    """Calcule bilans et styles courants pour {clé joueur: {circuit, surface}}.

    `jour` est la date de référence pré-match. Les matchs incomplets et abandons
    sont exclus. Le résultat courant n'est jamais utilisé pour classifier les
    deux joueurs avant ce même match.
    """
    P = PS.Profils(demi_vie, prior_mult)
    attente, serial, acc = [], 0, {}
    for original in sorted(M, key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0))):
        m = original
        if m['date'] > jour:
            break  # aucun résultat postérieur à la référence pré-match
        debut = dt.datetime.combine(m['date'], dt.time())
        while attente and attente[0][0] < debut:
            _, _, ancien = heapq.heappop(attente)
            P.ajouter(ancien, ancien['_g'], ancien['_p'])
        g, p = m['_g'], m['_p']
        if not g or not p or g == p:
            continue
        circuit, surface = m['circuit'], m['surface']
        ig, ng = P.profil(g, circuit, surface, m['date'])
        ip, np = P.profil(p, circuit, surface, m['date'])
        mug = P.moyenne(circuit, surface)
        sg = classifier(ig, ng, mug)
        sp = classifier(ip, np, mug)
        if m.get('complet') and not m.get('abandon'):
            if g in cibles and sp != 'indetermine':
                ev = _evenement(m, g, p, m.get('nom_p') or p, True, sp)
                _ajouter(acc, g, sp, surface, ev, True)
            if p in cibles and sg != 'indetermine':
                ev = _evenement(m, p, g, m.get('nom_g') or g, False, sg)
                _ajouter(acc, p, sg, surface, ev, False)
        heapq.heappush(attente, (dt.datetime.combine(m['fin'], dt.time()), serial, m))
        serial += 1
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
    return acc, courants


def _cibles(racine, maintenant):
    with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
        etat = E.migrer_etat(json.load(f))
    venir = PD.matchs_a_venir(racine, maintenant)
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
            'global': resume(acc.get((joueur, adverse['style'], 'global'))),
            'surface': resume(acc.get((joueur, adverse['style'], surface)))}


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
    acc, courants = calculer(tout, cibles, maintenant.date())
    out = {}
    for x in matchs:
        h, a, s = x['h'], x['a'], x['surface']
        if h not in courants or a not in courants:
            continue
        out[x['uid']] = {
            'descriptif_seulement': True,
            'joueurs': [_bloc(h, x['home'], courants[h], courants[a], s, acc),
                        _bloc(a, x['away'], courants[a], courants[h], s, acc)]}
    return {'schema': 'styles_descriptifs_v1', 'genere_le': maintenant.isoformat(timespec='seconds'),
            'archive_jusqu_au': fin_sack.isoformat(), 'feuilles_recentes': len(F),
            'minimum_balles_style': MIN_BALLES_STYLE,
            'regle': ('Style service–retour interne figé avant chaque match ; résultats ajoutés ensuite. '
                      'Descriptif seulement : aucune entrée du modèle de probabilité.'),
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
