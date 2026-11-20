#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_hesitation.py — « LÀ OÙ L'ALGO HÉSITE » (20/11/2026, paquet 313, décision de Lucas : « Lance l'étude 1 »).

Constat de départ (suivi en direct depuis le 05/11, 684 matchs) : la plus grosse tranche est celle où l'algo donne son
favori entre 50 et 60 % (273 matchs), et c'est là qu'il départage le moins bien. Le suivi en direct ne sert pas à
corriger (trop peu de matchs, et la correction par tranches a déjà été rejetée par l'étude de recalibrage) : on
cherche sur l'archive ce qui, CONNU AVANT LE MATCH, sépare le vainqueur du perdant dans ces matchs serrés.

Rejeu : archive Sackmann depuis 2012, Elo réglé COMME LA PRODUCTION (elo.de_production), mis à jour après chaque
match. BASE = ce que l'algo annonce aujourd'hui : Elo de production + les trois signaux solides (changement de surface,
retour d'absence, âge ; β appris sur 2018–2022) + EN CHALLENGER les deux décalages déjà en place
(simulateur/outsiders_ch.json). Matchs jugés : ATP, WTA, Challenger, sans abandon ni compétition par équipes.
ZONE D'HÉSITATION : la base donne le favori entre 50 et 60 % (l'autre joueur entre 40 et 50 %).

CINQ INDICES CANDIDATS (vus du favori de la base, tous connus avant le match, aucun n'est encore dans l'algo pour
cette zone) :
  1. classement  — écart de classement officiel : log2(rang de l'adversaire) − log2(rang du favori), borné à ±4
                   (positif quand le favori est aussi le mieux classé ; 0 si un classement manque) ;
  2. entree      — l'adversaire sort des qualifications (Q ou LL, déjà des matchs joués sur place) et pas le favori :
                   +1 ; l'inverse : −1 ;
  3. invitation  — le favori est invité (WC) et pas l'adversaire : +1 ; l'inverse : −1 ;
  4. domicile    — le favori joue dans son pays (feuilles/lieux_archive.json) et pas l'adversaire : +1 ; l'inverse : −1 ;
  5. experience  — log(1 + matchs ATP/WTA/Challenger déjà joués dans l'archive) du favori moins celui de l'adversaire.

RÈGLE ÉCRITE LE 20/11/2026, AVANT DE REGARDER LES RÉSULTATS (ne pas la modifier après coup), indice par indice et
CIRCUIT PAR CIRCUIT : un coefficient (logit) est appris sur 2018–2022 sur les matchs de la zone, puis jugé une seule
fois sur 2023 → juin 2026 sur les matchs de la zone. RETENU si : au moins 1 000 matchs jugés où l'indice n'est pas nul ;
gain de log loss ≥ 0,001 sur ces matchs ; gain ≥ 2 erreurs types ; et le coefficient réappris sur 2023 → juin 2026
est du MÊME SIGNE que celui de 2018–2022. Un indice retenu n'entre dans l'algo que par un paquet à part, avec sa règle
de retrait. Rapport public : simulateur/rapport_hesitation.json (aucun nom de joueur). Descriptif : le % ne change pas.
Usage : python simulateur/etude_hesitation.py /tmp/sackmann .
"""
import datetime as dt
import json
import math
import os
import sys

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
import etude_outsiders_vague2 as EV2  # noqa: E402

DEBUT, COUPURE, FIN = EO.DEBUT, EO.COUPURE, EO.FIN
MIN_JUGES, MARGE, MIN_ERREURS_TYPES = 1000, 0.001, 2.0
ZONE = (0.50, 0.60)
INDICES = ('classement', 'entree', 'invitation', 'domicile', 'experience')
SORTIE = os.path.join(ICI, 'rapport_hesitation.json')
_lg, _sg = EOG._lg, EOG._sg


def _log2(r):
    return math.log2(r) if r and r > 0 else None


def lignes(archive, racine):
    """Une ligne par match jugé, vue du VAINQUEUR : z de l'Elo, x5 des signaux en place, et ce que chaque indice voit
    des deux joueurs (vg : vainqueur, vp : perdant)."""
    M = DN.charger(archive, 2012)
    X, P = EOG.extras(archive), EOG.pays_tournois(racine)
    etat = E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8')))
    alias = dict(etat.get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None  # noqa: E731
    naiss = EA.naissances(archive, k)
    el, bas = E.de_production(racine)
    su, rt, rows = ECS.Suivi(), ERA.Retours(), []
    dernier, nb = {}, {}                 # joueur → (tournoi, match long) ; joueur → matchs ATP/WTA/CH déjà joués
    for m in M:
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s, d, tid = m['circuit'], m['surface'], m['date'], m.get('tournoi_id')
        if bas and c in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        if c in ('ATP', 'WTA', 'CH') and DEBUT <= d < FIN and not m.get('abandon') and m.get('niveau') != 'D':
            z = _lg(el.proba(g, p, s))
            xa = ERA.variables(rt.etat(g, d), rt.etat(p, d))
            xg = EA.variables(EA.age_au(naiss, g, d), EA.age_au(naiss, p, d)) or (0.0, 0.0)
            ex = X.get((str(tid or ''), m.get('num') or 0, m.get('nom_g') or ''))
            pt = EOG.pays_du(m.get('tournoi'), P)

            def vue(j, ioc, rang, entree):
                dj = dernier.get(j)
                return {'long': bool(dj and dj[0] == tid and dj[1]), 'court': bool(not dj or dj[0] != tid or not dj[1]),
                        'rang': rang, 'qualifie': entree in ('Q', 'LL'), 'invite': entree == 'WC',
                        'domicile': bool(pt and EOG.CIO.get(ioc) == pt), 'experience': nb.get(j, 0)}
            vg = vue(g, ex[0] if ex else '', ex[2] if ex else None, m.get('entree_g') or '')
            vp = vue(p, ex[1] if ex else '', ex[3] if ex else None, m.get('entree_p') or '')
            rows.append({'c': c, 'd': d, 'z': z, 'x5': (float(su.nouveau(g, d, s) - su.nouveau(p, d, s)), xa[0], xa[1],
                                                         xg[0], xg[1]), 'vg': vg, 'vp': vp})
        su.jouer(g, d, s)
        su.jouer(p, d, s)
        rt.jouer(g, d)
        rt.jouer(p, d)
        long_match = len(m.get('sets') or []) >= (5 if m.get('bo') == 5 else 3)
        for j in (g, p):
            dernier[j] = (tid, long_match)
            if c in ('ATP', 'WTA', 'CH'):
                nb[j] = nb.get(j, 0) + 1
        part = E.part_jeux(m['sets']) if m.get('complet') else None
        el.maj(g, p, s, m.get('niveau') == 'G', part)
    return rows


def indice(nom, f, a):
    """Valeur de l'indice vue du favori f contre l'adversaire a."""
    if nom == 'classement':
        rf, ra = _log2(f['rang']), _log2(a['rang'])
        return 0.0 if rf is None or ra is None else max(-4.0, min(4.0, ra - rf))
    if nom == 'entree':
        return float(a['qualifie']) - float(f['qualifie'])
    if nom == 'invitation':
        return float(f['invite']) - float(a['invite'])
    if nom == 'domicile':
        return float(f['domicile']) - float(a['domicile'])
    if nom == 'experience':
        return math.log1p(f['experience']) - math.log1p(a['experience'])
    return 0.0


def zone(r):
    """(z du favori, vue du favori, vue de l'adversaire, y = 1 si le favori gagne) dans la zone, sinon None."""
    pw = _sg(r['zb'])
    if pw == 0.5:
        return None
    pf = max(pw, 1 - pw)
    if not (ZONE[0] < pf < ZONE[1]):
        return None
    if pw > 0.5:
        return abs(r['zb']), r['vg'], r['vp'], 1
    return abs(r['zb']), r['vp'], r['vg'], 0


def cas(rows, c, nom, avant):
    """[(z du VAINQUEUR, (x vu du vainqueur,))] : la forme attendue par ESC.apprendre et EO.bilan."""
    out = []
    for r in rows:
        if r['c'] != c or (r['d'] < COUPURE) != avant:
            continue
        x = zone(r)
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


def ensemble(rows, c, noms):
    """Hors règle, pour préparer une éventuelle mise en place : les indices retenus d'un circuit appris ENSEMBLE sur
    2018–2022 (ils se recoupent : classement et expérience), jugés sur 2023 → juin 2026 sur toute la zone."""
    def data(avant):
        out = []
        for r in rows:
            if r['c'] != c or (r['d'] < COUPURE) != avant:
                continue
            x = zone(r)
            if not x:
                continue
            zf, f, a, y = x
            v = tuple(indice(n, f, a) for n in noms)
            out.append((zf, v) if y else (-zf, tuple(-t for t in v)))
        return out
    A, J = data(True), data(False)
    b = ESC.apprendre(A, k=len(noms))
    f_ = lambda z, x: z + sum(bi * xi for bi, xi in zip(b, x))  # noqa: E731
    tous = sum(1 for r in rows if r['c'] == c and r['d'] >= COUPURE)
    return {'indices': list(noms), 'coefficients_2018_2022': [round(v, 4) for v in b],
            'zone_2023 → juin 2026': EO.bilan([z for z, _ in J], [f_(z, x) for z, x in J]),
            'part_des_matchs_du_circuit_dans_la_zone': round(len(J) / tous, 3) if tous else None}


def regle():
    return (__doc__.split('RÈGLE ÉCRITE LE 20/11/2026, AVANT DE REGARDER LES RÉSULTATS (ne pas la modifier après coup),')[1]
            .split('Usage')[0].replace('\n', ' ').replace('  ', ' ').strip())


def taille_zone(rows):
    out = {}
    for c in ('ATP', 'WTA', 'CH'):
        n18 = sum(1 for r in rows if r['c'] == c and r['d'] < COUPURE and zone(r))
        n23 = sum(1 for r in rows if r['c'] == c and r['d'] >= COUPURE and zone(r))
        g23 = [zone(r) for r in rows if r['c'] == c and r['d'] >= COUPURE and zone(r)]
        out[c] = {'matchs_2018_2022': n18, 'matchs_2023': n23,
                  'favori_reel_2023_pct': round(100 * sum(x[3] for x in g23) / len(g23), 1) if g23 else None,
                  'favori_annonce_2023_pct': round(100 * sum(_sg(x[0]) for x in g23) / len(g23), 1) if g23 else None}
    return out


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    rows = lignes(archive, racine)
    betas = EO.poser_la_base(rows)
    D = EV2.decalages_ch(racine)
    n_ch = EV2.poser_ch_en_place(rows, D)
    res = {nom: {c: juger(rows, c, nom) for c in ('ATP', 'WTA', 'CH')} for nom in INDICES}
    retenus = [f'{nom} · {c}' for nom, v in res.items() for c, r in v.items() if r.get('retenu')]
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 313,
           'regle': regle(), 'zone': f'favori de la base entre {ZONE[0]:.0%} et {ZONE[1]:.0%}',
           'indices_definis': {
               'classement': 'log2(rang adversaire) − log2(rang favori), borné à ±4 ; 0 si un classement manque',
               'entree': 'adversaire issu des qualifications (Q, LL) et pas le favori : +1 ; l\'inverse : −1',
               'invitation': 'favori invité (WC) et pas l\'adversaire : +1 ; l\'inverse : −1',
               'domicile': 'favori dans son pays et pas l\'adversaire : +1 ; l\'inverse : −1',
               'experience': 'log(1 + matchs ATP/WTA/Challenger joués) du favori moins celui de l\'adversaire'},
           'base': {'elo': 'réglé comme la production', 'signaux': 'surface, absence, âge', 'betas_2018_2022': betas,
                    'challenger_en_place': {k: round(v, 4) for k, v in D.items()}, 'challenger_cas_corriges': n_ch},
           'zone_par_circuit': taille_zone(rows),
           'indices': res, 'retenus': retenus,
           'ensemble_des_retenus': {c: ensemble(rows, c, [n for n in INDICES if res[n][c].get('retenu')])
                                    for c in ('ATP', 'WTA', 'CH') if any(res[n][c].get('retenu') for n in INDICES)},
           'conclusion': ('retenus : ' + ', '.join(retenus)) if retenus else 'aucun indice ne passe la règle',
           'descriptif': 'le % de victoire ne change pas'}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc['zone_par_circuit'], ensure_ascii=False))
    for nom, v in res.items():
        for c, r in v.items():
            j = r.get('2023 → juin 2026') or {}
            print(f"{nom:11s} {c:3s} β18={r.get('coefficient_2018_2022')} β23={r.get('coefficient_2023')} "
                  f"n18={r.get('2018–2022', {}).get('matchs', r.get('matchs_2018_2022'))} n23={j.get('matchs', r.get('matchs_2023'))} "
                  f"gain={j.get('gain')} et={j.get('erreurs_types')} {'RETENU' if r.get('retenu') else ', '.join(r.get('raisons', []))}")
    print(doc['conclusion'])


if __name__ == '__main__':
    main(sys.argv)
