#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_hesitation_sr.py — « LÀ OÙ L'ALGO HÉSITE », ATP ET WTA, AVEC LES STATS DE SERVICE ET DE RETOUR (20/11/2026,
paquet 316, décision de Lucas : « On lance »).

Suite de etude_hesitation.py (paquet 313), qui n'a rien retenu en ATP ni en WTA avec le classement, l'entrée,
l'invitation, le domicile et l'expérience. Ici : les statistiques RÉCENTES de service et de retour, relevées point par
point dans l'archive (points joués et gagnés au service par chaque joueur, matchs ATP, WTA et Challenger avec
statistiques). Même rejeu, même BASE que le paquet 313 (Elo de production + changement de surface, retour d'absence,
âge ; β appris sur 2018–2022). Matchs jugés : ATP et WTA, sans abandon ni compétition par équipes.
ZONE D'HÉSITATION : la base donne le favori entre 50 et 60 %.

QUATRE INDICES CANDIDATS (vus du favori de la base, en points de pourcentage divisés par 10, tous connus avant le
match ; calculés sur les 365 jours précédents, seulement si les DEUX joueurs ont au moins 10 matchs avec statistiques
sur cette période, sinon l'indice est nul) :
  1. points_gagnes — % de points gagnés (service + retour) du favori moins celui de l'adversaire ;
  2. service       — % de points gagnés au service du favori moins celui de l'adversaire ;
  3. retour        — % de points gagnés au retour du favori moins celui de l'adversaire ;
  4. tendance      — (% de points gagnés sur 90 jours − % sur 365 jours) du favori moins celui de l'adversaire ;
                     seulement si les deux joueurs ont aussi au moins 5 matchs avec statistiques sur 90 jours.

RÈGLE ÉCRITE LE 20/11/2026, AVANT DE REGARDER LES RÉSULTATS (ne pas la modifier après coup), indice par indice et
CIRCUIT PAR CIRCUIT (ATP, WTA) : un coefficient (logit) est appris sur 2018–2022 sur les matchs de la zone où l'indice
n'est pas nul, puis jugé une seule fois sur 2023 → juin 2026 sur ces matchs. RETENU si : au moins 1 000 matchs jugés ;
gain de log loss ≥ 0,001 ; gain ≥ 2 erreurs types ; et le coefficient réappris sur 2023 → juin 2026 est du MÊME SIGNE
que celui de 2018–2022. Un indice retenu n'entre dans l'algo que par un paquet à part, avec sa règle de retrait.
Rapport public : simulateur/rapport_hesitation_sr.json (aucun nom de joueur). Descriptif : le % ne change pas.
Usage : python simulateur/etude_hesitation_sr.py /tmp/sackmann .
"""
import datetime as dt
import json
import os
import sys
from collections import deque

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees as DN  # noqa: E402
import elo as E  # noqa: E402
import etude_age as EA  # noqa: E402
import etude_changement_surface as ECS  # noqa: E402
import etude_retour_absence as ERA  # noqa: E402
import etude_signaux_combines as ESC  # noqa: E402
import etude_outsiders as EO  # noqa: E402
import etude_outsiders_gagnants as EOG  # noqa: E402
import etude_hesitation as EH  # noqa: E402

DEBUT, COUPURE, FIN = EO.DEBUT, EO.COUPURE, EO.FIN
MIN_JUGES, MARGE, MIN_ERREURS_TYPES = 1000, 0.001, 2.0
ZONE = EH.ZONE
CIRCUITS = ('ATP', 'WTA')
INDICES = ('points_gagnes', 'service', 'retour', 'tendance')
LONG, COURT, MIN_LONG, MIN_COURT = 365, 90, 10, 5
SORTIE = os.path.join(ICI, 'rapport_hesitation_sr.json')
_lg, _sg = EOG._lg, EOG._sg


def resume(hist, d):
    """{'n', 'srv', 'ret', 'tot', 'n90', 'tot90'} du joueur avant la date d (matchs avec stats), ou None."""
    L = [x for x in hist if 0 < (d - x[0]).days <= LONG]
    if not L:
        return None
    s = lambda X, i: sum(x[i] for x in X)  # noqa: E731
    C = [x for x in L if (d - x[0]).days <= COURT]
    sj, sg_, rj, rg = s(L, 1), s(L, 2), s(L, 3), s(L, 4)
    out = {'n': len(L), 'srv': 100 * sg_ / sj if sj else None, 'ret': 100 * rg / rj if rj else None,
           'tot': 100 * (sg_ + rg) / (sj + rj) if sj + rj else None, 'n90': len(C), 'tot90': None}
    if C:
        cj, cg = s(C, 1) + s(C, 3), s(C, 2) + s(C, 4)
        out['tot90'] = 100 * cg / cj if cj else None
    return out


def lignes(archive, racine):
    """Une ligne par match jugé (ATP, WTA), vue du VAINQUEUR, avec le résumé service–retour des deux joueurs."""
    M = DN.charger(archive, 2012)
    etat = E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8')))
    alias = dict(etat.get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None  # noqa: E731
    naiss = EA.naissances(archive, k)
    el, bas = E.de_production(racine)
    su, rt, rows = ECS.Suivi(), ERA.Retours(), []
    hist = {}                     # joueur → deque[(date, points servis, gagnés au service, points reçus, gagnés au retour)]
    for m in M:
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s, d = m['circuit'], m['surface'], m['date']
        if bas and c in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        if c in CIRCUITS and DEBUT <= d < FIN and not m.get('abandon') and m.get('niveau') != 'D':
            z = _lg(el.proba(g, p, s))
            xa = ERA.variables(rt.etat(g, d), rt.etat(p, d))
            xg = EA.variables(EA.age_au(naiss, g, d), EA.age_au(naiss, p, d)) or (0.0, 0.0)
            rows.append({'c': c, 'd': d, 'z': z, 'x5': (float(su.nouveau(g, d, s) - su.nouveau(p, d, s)), xa[0], xa[1],
                                                         xg[0], xg[1]),
                         'vg': resume(hist.get(g, ()), d), 'vp': resume(hist.get(p, ()), d)})
        su.jouer(g, d, s)
        su.jouer(p, d, s)
        rt.jouer(g, d)
        rt.jouer(p, d)
        st = m.get('stats')
        if st and c in ('ATP', 'WTA', 'CH'):
            (nw, kw), (nl, kl) = st['w'], st['l']
            for j, srv, ret in ((g, (nw, kw), (nl, nl - kl)), (p, (nl, kl), (nw, nw - kw))):
                q = hist.setdefault(j, deque(maxlen=120))
                q.append((d, srv[0], srv[1], ret[0], ret[1]))
                while q and (d - q[0][0]).days > LONG + 30:
                    q.popleft()
        part = E.part_jeux(m['sets']) if m.get('complet') else None
        el.maj(g, p, s, m.get('niveau') == 'G', part)
    return rows


def indice(nom, f, a):
    """Valeur de l'indice vue du favori f contre l'adversaire a (résumés), en points de % / 10 ; 0 si non applicable."""
    if not f or not a or f['n'] < MIN_LONG or a['n'] < MIN_LONG:
        return 0.0
    if nom == 'tendance':
        if f['n90'] < MIN_COURT or a['n90'] < MIN_COURT or None in (f['tot90'], a['tot90'], f['tot'], a['tot']):
            return 0.0
        return ((f['tot90'] - f['tot']) - (a['tot90'] - a['tot'])) / 10
    cle = {'points_gagnes': 'tot', 'service': 'srv', 'retour': 'ret'}[nom]
    if f[cle] is None or a[cle] is None:
        return 0.0
    return (f[cle] - a[cle]) / 10


def cas(rows, c, nom, avant):
    out = []
    for r in rows:
        if r['c'] != c or (r['d'] < COUPURE) != avant:
            continue
        x = EH.zone(r)
        if not x:
            continue
        zf, f, a, y = x
        v = indice(nom, f, a)
        if not v:
            continue
        out.append((zf, (v,)) if y else (-zf, (-v,)))
    return out


def juger(rows, c, nom):
    A, J = cas(rows, c, nom, True), cas(rows, c, nom, False)
    if len(A) < 50:
        return {'matchs_2018_2022': len(A), 'matchs_2023': len(J), 'retenu': False, 'raisons': ['trop peu de cas']}
    beta = ESC.apprendre(A, k=1)[0]
    beta_j = ESC.apprendre(J, k=1)[0] if len(J) >= 50 else None
    f_ = lambda z, x: z + beta * x[0]  # noqa: E731
    appr = EO.bilan([z for z, _ in A], [f_(z, x) for z, x in A])
    juge = EO.bilan([z for z, _ in J], [f_(z, x) for z, x in J]) if J else {'matchs': 0}
    raisons = []
    if juge.get('matchs', 0) < MIN_JUGES:
        raisons.append(f'moins de {MIN_JUGES} matchs jugés')
    if juge.get('gain', -1) < MARGE:
        raisons.append(f'gain sous {MARGE}')
    if (juge.get('erreurs_types') or 0) < MIN_ERREURS_TYPES:
        raisons.append(f'gain sous {MIN_ERREURS_TYPES:g} erreurs types')
    if beta_j is None or beta * beta_j <= 0:
        raisons.append("le coefficient n'a pas le même sens sur les deux périodes")
    return {'coefficient_2018_2022': round(beta, 4), 'coefficient_2023': None if beta_j is None else round(beta_j, 4),
            '2018–2022': appr, '2023 → juin 2026': juge, 'retenu': not raisons, 'raisons': raisons}


def regle():
    return (__doc__.split('RÈGLE ÉCRITE LE 20/11/2026, AVANT DE REGARDER LES RÉSULTATS (ne pas la modifier après coup),')[1]
            .split('Usage')[0].replace('\n', ' ').replace('  ', ' ').strip())


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    rows = lignes(archive, racine)
    betas = EO.poser_la_base(rows)
    res = {nom: {c: juger(rows, c, nom) for c in CIRCUITS} for nom in INDICES}
    retenus = [f'{nom} · {c}' for nom, v in res.items() for c, r in v.items() if r.get('retenu')]
    couverture = {}
    for c in CIRCUITS:
        Z = [EH.zone(r) for r in rows if r['c'] == c and r['d'] >= COUPURE]
        Z = [x for x in Z if x]
        couverture[c] = {'zone_2023': len(Z), 'avec_statistiques': sum(1 for x in Z if indice('points_gagnes', x[1], x[2]))}
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 316,
           'regle': regle(), 'zone': f'favori de la base entre {ZONE[0]:.0%} et {ZONE[1]:.0%}',
           'indices_definis': {
               'points_gagnes': '% de points gagnés sur 365 jours, favori moins adversaire (points de % / 10)',
               'service': '% de points gagnés au service sur 365 jours, favori moins adversaire',
               'retour': '% de points gagnés au retour sur 365 jours, favori moins adversaire',
               'tendance': '(% sur 90 jours − % sur 365 jours), favori moins adversaire',
               'condition': f'au moins {MIN_LONG} matchs avec statistiques sur 365 jours (et {MIN_COURT} sur 90 jours pour la tendance) pour les deux joueurs'},
           'base': {'elo': 'réglé comme la production', 'signaux': 'surface, absence, âge', 'betas_2018_2022': betas},
           'couverture_zone': couverture, 'indices': res, 'retenus': retenus,
           'conclusion': ('retenus : ' + ', '.join(retenus)) if retenus else 'aucun indice ne passe la règle',
           'descriptif': 'le % de victoire ne change pas'}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(couverture, ensure_ascii=False))
    for nom, v in res.items():
        for c, r in v.items():
            j = r.get('2023 → juin 2026') or {}
            print(f"{nom:13s} {c:3s} β18={r.get('coefficient_2018_2022')} β23={r.get('coefficient_2023')} "
                  f"n18={r.get('2018–2022', {}).get('matchs', r.get('matchs_2018_2022'))} n23={j.get('matchs', r.get('matchs_2023'))} "
                  f"gain={j.get('gain')} et={j.get('erreurs_types')} {'RETENU' if r.get('retenu') else ', '.join(r.get('raisons', []))}")
    print(doc['conclusion'])


if __name__ == '__main__':
    main(sys.argv)
