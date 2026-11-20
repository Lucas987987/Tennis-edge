#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_outsiders_gagnants.py — CHANTIER « REPÉRER LES OUTSIDERS QUI GAGNENT » (18/11/2026, paquet 273, décision de
Lucas ; priorité fixée le 11/11 : « repérer les cas où des outsiders peuvent gagner »).

Question : dans quelles situations, connues AVANT le match, l'outsider gagne-t-il plus souvent que nous ne l'annonçons ?
Rejeu : archive Sackmann depuis 2012, Elo réglé COMME LA PRODUCTION (elo.de_production), mis à jour après chaque
match ; BASE = Elo de production + les trois signaux solides (changement de surface, retour d'absence, âge), β appris
sur 2018–2022 (même base que etude_outsiders.py, paquet 230). Matchs jugés : ATP, WTA, Challenger, sans abandon ni
compétition par équipes. Outsider = le joueur que la base donne entre 15 et 45 %.

SIX SITUATIONS CANDIDATES (vues de l'outsider, toutes connues avant le match) :
  1. favori_fatigue      — le favori sort d'un match en 3 sets (5 en Grand Chelem hommes) dans ce tournoi, l'outsider
                           d'un match gagné sans perdre de set (ou c'est son premier match) ;
  2. outsider_domicile   — l'outsider joue dans son pays (feuilles/lieux_archive.json), pas le favori ;
  3. outsider_gaucher    — l'outsider est gaucher, le favori droitier ;
  4. outsider_en_serie   — l'outsider a gagné au moins 4 matchs dans les tournois commencés depuis 14 jours ;
  5. favori_titre_recent — le favori a gagné un tournoi commencé dans les 14 jours, et joue son 1er match ici ;
  6. outsider_mieux_classe — l'outsider a un meilleur classement officiel que le favori (classement et Elo en désaccord).

RÈGLE ÉCRITE LE 18/11/2026, AVANT DE REGARDER LES RÉSULTATS (ne pas la modifier après coup), situation par situation
et CIRCUIT PAR CIRCUIT : un décalage (logit) vers l'outsider est appris sur 2018–2022 sur les matchs concernés, puis
jugé une seule fois sur 2023 → juin 2026 sur les matchs concernés. RETENU si : au moins 1 000 matchs concernés jugés ;
gain de log loss ≥ 0,001 ; gain ≥ 2 erreurs types ; et l'outsider concerné gagne plus qu'annoncé sur les DEUX périodes.
Un résultat retenu n'entre dans l'algo que par un paquet à part, avec sa règle de retrait. Rapport public :
simulateur/rapport_outsiders_gagnants.json (aucun nom de joueur). Descriptif tant que rien n'est mis en place.
Usage : python simulateur/etude_outsiders_gagnants.py /tmp/sackmann .
"""
import csv
import datetime as dt
import glob
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

DEBUT, COUPURE, FIN = EO.DEBUT, EO.COUPURE, EO.FIN
MIN_JUGES, MARGE, MIN_ERREURS_TYPES = 1000, 0.001, 2.0
OUTSIDER = (0.15, 0.45)
SITUATIONS = ('favori_fatigue', 'outsider_domicile', 'outsider_gaucher', 'outsider_en_serie', 'favori_titre_recent',
              'outsider_mieux_classe')
SORTIE = os.path.join(ICI, 'rapport_outsiders_gagnants.json')
# CIO → ISO 3166 (pays des joueurs → pays des tournois)
CIO = {'ARG': 'AR', 'AUS': 'AU', 'AUT': 'AT', 'BEL': 'BE', 'BIH': 'BA', 'BLR': 'BY', 'BOL': 'BO', 'BRA': 'BR', 'BUL': 'BG',
       'CAN': 'CA', 'CHI': 'CL', 'CHN': 'CN', 'COL': 'CO', 'CRO': 'HR', 'CYP': 'CY', 'CZE': 'CZ', 'DEN': 'DK', 'DOM': 'DO',
       'ECU': 'EC', 'EGY': 'EG', 'ESA': 'SV', 'ESP': 'ES', 'EST': 'EE', 'FIN': 'FI', 'FRA': 'FR', 'GBR': 'GB', 'GEO': 'GE',
       'GER': 'DE', 'GRE': 'GR', 'HKG': 'HK', 'HUN': 'HU', 'INA': 'ID', 'IND': 'IN', 'IRL': 'IE', 'ISR': 'IL', 'ITA': 'IT',
       'JPN': 'JP', 'KAZ': 'KZ', 'KOR': 'KR', 'LAT': 'LV', 'LTU': 'LT', 'LUX': 'LU', 'MAR': 'MA', 'MDA': 'MD', 'MEX': 'MX',
       'MKD': 'MK', 'MNE': 'ME', 'NED': 'NL', 'NOR': 'NO', 'NZL': 'NZ', 'PAR': 'PY', 'PER': 'PE', 'PHI': 'PH', 'POL': 'PL',
       'POR': 'PT', 'PUR': 'PR', 'QAT': 'QA', 'ROU': 'RO', 'RSA': 'ZA', 'RUS': 'RU', 'SLO': 'SI', 'SRB': 'RS', 'SUI': 'CH',
       'SVK': 'SK', 'SWE': 'SE', 'THA': 'TH', 'TPE': 'TW', 'TUN': 'TN', 'TUR': 'TR', 'UAE': 'AE', 'UKR': 'UA', 'URU': 'UY',
       'USA': 'US', 'UZB': 'UZ', 'VEN': 'VE', 'VIE': 'VN', 'ZIM': 'ZW', 'ARM': 'AM', 'AZE': 'AZ', 'JOR': 'JO', 'KSA': 'SA',
       'SGP': 'SG', 'MAS': 'MY', 'NGR': 'NG', 'KEN': 'KE', 'CRC': 'CR', 'GUA': 'GT', 'BAR': 'BB', 'JAM': 'JM', 'MON': 'MC'}


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30.0), -30.0)))


def extras(archive):
    """{(tournoi_id, n° du match, nom du vainqueur): (pays CIO vainqueur, pays perdant, classement v., classement p.)}"""
    out = {}
    for f in sorted(glob.glob(os.path.join(archive, '**', '*_matches_*20*.csv'), recursive=True)):
        try:
            with open(f, encoding='utf-8', errors='replace', newline='') as fh:
                for r in csv.DictReader(fh):
                    try:
                        num = int(float(r.get('match_num') or 0))
                    except ValueError:
                        num = 0
                    rk = lambda v: int(float(v)) if v not in (None, '') else None  # noqa: E731
                    try:
                        out[(str(r.get('tourney_id') or ''), num, r.get('winner_name') or '')] = (
                            r.get('winner_ioc') or '', r.get('loser_ioc') or '', rk(r.get('winner_rank')), rk(r.get('loser_rank')))
                    except ValueError:
                        continue
        except OSError:
            continue
    return out


def pays_tournois(racine):
    try:
        with open(os.path.join(racine, 'feuilles', 'lieux_archive.json'), encoding='utf-8') as f:
            L = json.load(f)
    except (OSError, ValueError):
        return {}
    return {k.lower().strip(): (v or {}).get('code') for k, v in L.items() if (v or {}).get('code')}


def pays_du(nom, P):
    n = str(nom or '').lower().strip()
    for c in (n, n.replace(' ch', '').strip(), 'atp ' + n, 'wta ' + n, n + ' ch', n.split(' 1')[0], n.split(' 2')[0]):
        if c in P:
            return P[c]
    return None


def lignes(archive, racine):
    """Une ligne par match jugé, vue du VAINQUEUR, avec les six situations vues du vainqueur et du perdant."""
    M = DN.charger(archive, 2012)
    X, P = extras(archive), pays_tournois(racine)
    etat = E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8')))
    alias = dict(etat.get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None  # noqa: E731
    naiss = EA.naissances(archive, k)
    el, bas = E.de_production(racine)
    su, rt, rows = ECS.Suivi(), ERA.Retours(), []
    dernier = {}            # joueur → (tournoi_id, sets perdus par lui ? 3 sets ?, a gagné)
    victoires = {}          # joueur → [dates des victoires]
    titres = {}             # joueur → [(date du tournoi, tournoi_id)]
    couverture = {'pays_tournoi': 0, 'matchs': 0}
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
            pt = pays_du(m.get('tournoi'), P)
            couverture['matchs'] += 1
            couverture['pays_tournoi'] += bool(pt)

            def vue(j, adv, ioc, rang, rang_adv, main, main_adv):
                dj = dernier.get(j)
                long_ = bool(dj and dj[0] == tid and dj[1])
                court_ = bool(not dj or dj[0] != tid or (dj[0] == tid and not dj[1]))
                serie = sum(1 for v in victoires.get(j, []) if (d - v).days <= 14)
                titre = any(0 <= (d - td).days <= 14 and t_ != tid for td, t_ in titres.get(j, []))
                premier_ici = not dj or dj[0] != tid
                return {'long': long_, 'court': court_, 'serie': serie, 'titre_premier': titre and premier_ici,
                        'domicile': bool(pt and CIO.get(ioc) == pt), 'gaucher': main == 'L', 'droitier': main == 'R',
                        'rang': rang}
            if ex:
                vg = vue(g, p, ex[0], ex[2], ex[3], m.get('main_g'), m.get('main_p'))
                vp = vue(p, g, ex[1], ex[3], ex[2], m.get('main_p'), m.get('main_g'))
            else:
                vg = vue(g, p, '', None, None, m.get('main_g'), m.get('main_p'))
                vp = vue(p, g, '', None, None, m.get('main_p'), m.get('main_g'))
            rows.append({'c': c, 'd': d, 'z': z, 'x5': (float(su.nouveau(g, d, s) - su.nouveau(p, d, s)), xa[0], xa[1], xg[0], xg[1]),
                         'vg': vg, 'vp': vp})
        su.jouer(g, d, s)
        su.jouer(p, d, s)
        rt.jouer(g, d)
        rt.jouer(p, d)
        long_match = len(m.get('sets') or []) >= (5 if m.get('bo') == 5 else 3)
        dernier[g] = (tid, long_match)
        dernier[p] = (tid, long_match)
        victoires.setdefault(g, []).append(d)
        if len(victoires[g]) > 40:
            victoires[g] = victoires[g][-40:]
        if m.get('tour') == 10:
            titres.setdefault(g, []).append((d, tid))
        part = E.part_jeux(m['sets']) if m.get('complet') else None
        el.maj(g, p, s, m.get('niveau') == 'G', part)
    return rows, couverture


def situation(nom, o, f):
    """Vrai si la situation tient, vue de l'outsider o face au favori f."""
    if nom == 'favori_fatigue':
        return f['long'] and o['court']
    if nom == 'outsider_domicile':
        return o['domicile'] and not f['domicile']
    if nom == 'outsider_gaucher':
        return o['gaucher'] and f['droitier']
    if nom == 'outsider_en_serie':
        return o['serie'] >= 4
    if nom == 'favori_titre_recent':
        return f['titre_premier']
    if nom == 'outsider_mieux_classe':
        return o['rang'] is not None and f['rang'] is not None and o['rang'] < f['rang']
    return False


def cas(r, nom):
    """(signe, p de l'outsider, outsider gagnant) si l'outsider est entre 15 et 45 % et la situation tient."""
    pw = _sg(r['zb'])
    if pw > 0.5:
        o, f, p_out, signe = r['vp'], r['vg'], 1 - pw, -1.0
    else:
        o, f, p_out, signe = r['vg'], r['vp'], pw, 1.0
    if not (OUTSIDER[0] <= p_out <= OUTSIDER[1]) or not situation(nom, o, f):
        return None
    return signe, p_out, 1 if signe > 0 else 0


def juger(rows, c, nom):
    A, J = [], []
    for r in rows:
        if r['c'] != c:
            continue
        x = cas(r, nom)
        if x:
            (A if r['d'] < COUPURE else J).append((r['zb'], x))
    if len(A) < 50:
        return {'matchs_2018_2022': len(A), 'matchs_2023': len(J), 'retenu': False, 'raisons': ['trop peu de cas']}
    beta = ESC.apprendre([(z, (x[0],)) for z, x in A], k=1)[0]
    f_ = lambda z, x: z + beta * x[0]  # noqa: E731
    appr = EO.bilan([z for z, _ in A], [f_(z, x) for z, x in A])
    juge = EO.bilan([z for z, _ in J], [f_(z, x) for z, x in J]) if J else {'matchs': 0}
    cote = lambda L: {'annonce_pct': round(100 * sum(x[1] for _, x in L) / len(L), 1),  # noqa: E731
                      'reel_pct': round(100 * sum(x[2] for _, x in L) / len(L), 1)} if L else {}
    oa, oj = cote(A), cote(J)
    raisons = []
    if juge.get('matchs', 0) < MIN_JUGES:
        raisons.append(f'moins de {MIN_JUGES} matchs jugés')
    if juge.get('gain', -1) < MARGE:
        raisons.append(f'gain sous {MARGE}')
    if (juge.get('erreurs_types') or 0) < MIN_ERREURS_TYPES:
        raisons.append(f'gain sous {MIN_ERREURS_TYPES:g} erreurs types')
    if not (oa and oj and oa['reel_pct'] > oa['annonce_pct'] and oj['reel_pct'] > oj['annonce_pct']):
        raisons.append("l'outsider ne gagne pas plus qu'annoncé sur les deux périodes")
    return {'decalage_appris': round(beta, 4), 'outsider_2018_2022': oa, 'outsider_2023': oj,
            '2018–2022': appr, '2023 → juin 2026': juge, 'retenu': not raisons, 'raisons': raisons}


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    rows, couv = lignes(archive, racine)
    betas = EO.poser_la_base(rows)
    res = {nom: {c: juger(rows, c, nom) for c in ('ATP', 'WTA', 'CH')} for nom in SITUATIONS}
    retenus = [f'{nom} · {c}' for nom, v in res.items() for c, r in v.items() if r.get('retenu')]
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 273,
           'regle': __doc__.split('RÈGLE ÉCRITE LE 18/11/2026, AVANT DE REGARDER LES RÉSULTATS (ne pas la modifier après coup),')[1]
           .split('Usage')[0].replace('\n', ' ').strip(),
           'base': {'elo': 'réglé comme la production', 'signaux': 'surface, absence, âge', 'betas_2018_2022': betas},
           'couverture': couv, 'situations': res, 'retenus': retenus,
           'conclusion': ('retenus : ' + ', '.join(retenus)) if retenus else 'aucune situation ne passe la règle',
           'descriptif': 'le % de victoire ne change pas'}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for nom, v in res.items():
        for c, r in v.items():
            j, oa, oj = r.get('2023 → juin 2026') or {}, r.get('outsider_2018_2022') or {}, r.get('outsider_2023') or {}
            print(f"{nom:22s} {c:3s} β={r.get('decalage_appris')} n18={r.get('2018–2022', {}).get('matchs', r.get('matchs_2018_2022'))} "
                  f"n23={j.get('matchs', r.get('matchs_2023'))} gain={j.get('gain')} et={j.get('erreurs_types')} "
                  f"out18 {oa.get('reel_pct')}/{oa.get('annonce_pct')} out23 {oj.get('reel_pct')}/{oj.get('annonce_pct')} {'RETENU' if r.get('retenu') else ''}")
    print(doc['conclusion'], couv)


if __name__ == '__main__':
    main(sys.argv)
