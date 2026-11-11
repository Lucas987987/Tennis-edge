#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_outsiders.py — où l'outsider gagne-t-il plus, ou moins, qu'annoncé ? (11/11/2026, audit, paquet 230)

Constats de l'exploration, faits sur 2018–2022 SEULEMENT (simulateur/rapport_audit.json, paquet 229) :
  - Grand Chelem : aux deux premiers tours, l'outsider gagne MOINS qu'annoncé (WTA 27,8 % pour 30,7 % ; ATP 26,9 % pour
    30,5 %) ; en WTA, pente 1,23 sur 2 372 matchs de Grand Chelem. En ATP c'est le format en 3 sets gagnants, déjà jugé
    (etude_format_match.py : +0,0014 ± 0,0020, en attente).
  - Challenger : l'outsider gagne PLUS qu'annoncé, surtout s'il est en progression (39,8 % pour 36,8 %) ou issu des
    qualifications (34,5 % pour 32,0 %).

Rejeu : archive Sackmann depuis 2012, Elo réglé COMME LA PRODUCTION (elo.de_production), mis à jour après chaque
match ; un second Elo « rapide » (vitesse × 2,5) tourne à côté. Matchs jugés : sans abandon, sans compétitions par
équipes. BASE de chaque circuit : l'Elo de production plus les trois signaux solides (changement de surface, retour
d'absence, âge), β appris ensemble sur 2018–2022.

RÈGLES ÉCRITES LE 11/11/2026 (rapport_audit.json, paquets 228 et 229), AVANT DE REGARDER 2023 → :
  A — GRAND CHELEM EN WTA. Une pente propre aux matchs de Grand Chelem (tableau principal), p' = σ(pente · logit p),
      apprise sur 2018–2022, jugée une seule fois sur 2023 → juin 2026 sur ces matchs : gain ≥ 0,001 sur ≥ 1 000
      matchs, gain ≥ 2 erreurs types, biais de même sens sur les deux périodes.
  B — OUTSIDER EN CHALLENGER. Outsider = le joueur que la base donne entre 15 et 45 %. Deux décalages (logit) vers
      lui, appris ENSEMBLE sur 2018–2022 : (a) « en progression » : le duel vu par l'Elo rapide lui est plus favorable
      d'au moins 0,25 en logit que vu par l'Elo ; (b) « issu des qualifications » (entrée « Q »). Jugés une seule fois
      sur 2023 → juin 2026, sur les matchs concernés par l'un ou l'autre : gain ≥ 0,001 sur ≥ 1 000 matchs, et
      l'outsider concerné gagne plus qu'annoncé sur les deux périodes. Erreur type et Brier publiés ; la condition
      « 2 erreurs types » est publiée à part (elle ne décide pas pour B, elle fait partie de la règle écrite pour A).

Usage : python simulateur/etude_outsiders.py /tmp/sackmann .
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

DEBUT, COUPURE, FIN = dt.date(2018, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
MIN_JUGES, MARGE, MIN_ERREURS_TYPES = 1000, 0.001, 2.0
VITESSE_RAPIDE, SEUIL_PROGRESSION, OUTSIDER = 2.5, 0.25, (0.15, 0.45)
SORTIE = os.path.join(ICI, 'rapport_outsiders.json')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30.0), -30.0)))


def ll(z):
    return -math.log(min(max(_sg(z), 1e-9), 1 - 1e-9))


def brier(z):
    return (1 - _sg(z)) ** 2


def pente(Z):
    k = 1.0
    for _ in range(60):
        g = h = 0.0
        for z in Z:
            q = _sg(k * z)
            g += (q - 1) * z
            h += q * (1 - q) * z * z
        if h < 1e-9:
            break
        k -= g / h
    return k


def lignes(archive, racine):
    """Une ligne par match jugé, vue du VAINQUEUR : circuit, date, niveau, z de l'Elo, variables des trois signaux,
    progression (Elo rapide − Elo, en logit, pour le vainqueur) et entrées des deux joueurs."""
    M = DN.charger(archive, 2012)
    etat = E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8')))
    alias = dict(etat.get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    naiss = EA.naissances(archive, k)
    el, bas = E.de_production(racine)
    vite = E.Elo(**E.options_production(racine)[0])
    su, rt, rows = ECS.Suivi(), ERA.Retours(), []
    for m in M:
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s, d = m['circuit'], m['surface'], m['date']
        for e_ in (el, vite):
            if bas and c in ('CH', 'ITF'):
                e_.presenter(g, bas)
                e_.presenter(p, bas)
        vite.regler_vitesse(g, VITESSE_RAPIDE)
        vite.regler_vitesse(p, VITESSE_RAPIDE)
        if c in ('ATP', 'WTA', 'CH') and DEBUT <= d < FIN and not m.get('abandon') and m.get('niveau') != 'D':
            z = _lg(el.proba(g, p, s))
            xa = ERA.variables(rt.etat(g, d), rt.etat(p, d))
            xg = EA.variables(EA.age_au(naiss, g, d), EA.age_au(naiss, p, d)) or (0.0, 0.0)
            rows.append({'c': c, 'd': d, 'niveau': m.get('niveau'), 'bo': m['bo'], 'z': z,
                         'x5': (float(su.nouveau(g, d, s) - su.nouveau(p, d, s)), xa[0], xa[1], xg[0], xg[1]),
                         'progression_g': _lg(vite.proba(g, p, s)) - z,
                         'q_g': (m.get('entree_g') or '') == 'Q', 'q_p': (m.get('entree_p') or '') == 'Q'})
        su.jouer(g, d, s)
        su.jouer(p, d, s)
        rt.jouer(g, d)
        rt.jouer(p, d)
        part = E.part_jeux(m['sets']) if m.get('complet') else None
        el.maj(g, p, s, m.get('niveau') == 'G', part)
        vite.maj(g, p, s, m.get('niveau') == 'G', part)
    return rows


def poser_la_base(rows):
    """z de base = Elo + trois signaux solides, β appris par circuit sur 2018–2022. Renvoie les β."""
    betas = {}
    for c in ('ATP', 'WTA', 'CH'):
        A = [(r['z'], r['x5']) for r in rows if r['c'] == c and r['d'] < COUPURE]
        b = ESC.apprendre(A, k=5) if len(A) >= 500 else [0.0] * 5
        betas[c] = [round(v, 4) for v in b]
        for r in rows:
            if r['c'] == c:
                r['zb'] = r['z'] + sum(bi * xi for bi, xi in zip(b, r['x5']))
    return betas


def bilan(base, variante):
    n = len(base)
    if not n:
        return {'matchs': 0}
    d = [ll(a) - ll(b) for a, b in zip(base, variante)]
    moy = sum(d) / n
    et = math.sqrt(sum((x - moy) ** 2 for x in d) / n) / math.sqrt(n)
    return {'matchs': n, 'gain': round(moy, 5), 'erreur_type': round(et, 5), 'erreurs_types': round(moy / et, 2) if et else None,
            'log_loss_base': round(sum(ll(a) for a in base) / n, 5), 'log_loss': round(sum(ll(b) for b in variante) / n, 5),
            'brier_base': round(sum(brier(a) for a in base) / n, 5), 'brier': round(sum(brier(b) for b in variante) / n, 5),
            'favori_annonce_pct': round(100 * sum(max(_sg(a), 1 - _sg(a)) for a in base) / n, 1),
            'favori_reel_pct': round(100 * sum(1.0 if a > 0 else 0.5 if a == 0 else 0.0 for a in base) / n, 1)}


def grand_chelem(rows, circuit='WTA'):
    A = [r['zb'] for r in rows if r['c'] == circuit and r['niveau'] == 'G' and r['d'] < COUPURE]
    J = [r['zb'] for r in rows if r['c'] == circuit and r['niveau'] == 'G' and r['d'] >= COUPURE]
    k = pente(A)
    appr, juge = bilan(A, [k * z for z in A]), bilan(J, [k * z for z in J])
    kj = pente(J) if J else None
    raisons = []
    if juge.get('matchs', 0) < MIN_JUGES:
        raisons.append(f"moins de {MIN_JUGES} matchs jugés")
    if juge.get('gain', -1) < MARGE:
        raisons.append(f"gain sous {MARGE}")
    if (juge.get('erreurs_types') or 0) < MIN_ERREURS_TYPES:
        raisons.append(f"gain sous {MIN_ERREURS_TYPES:g} erreurs types")
    if kj is None or (kj - 1) * (k - 1) <= 0:
        raisons.append("biais de sens contraire sur 2023 →")
    return {'pente_apprise': round(k, 3), 'pente_sur_2023': round(kj, 3) if kj is not None else None,
            '2018–2022': appr, '2023 → juin 2026': juge, 'retenue': not raisons, 'raisons': raisons}


def cas_outsider(r):
    """(x progression, x qualifications) vus du vainqueur, ou None si l'outsider de la base n'est pas entre 15 et 45 %."""
    pw = _sg(r['zb'])
    if pw > 0.5:                                    # l'outsider est le perdant
        p_out, signe, prog, q = 1 - pw, -1.0, -r['progression_g'], r['q_p']
    else:
        p_out, signe, prog, q = pw, 1.0, r['progression_g'], r['q_g']
    if not (OUTSIDER[0] <= p_out <= OUTSIDER[1]):
        return None
    a, b = (1.0 if prog >= SEUIL_PROGRESSION else 0.0), (1.0 if q else 0.0)
    if not (a or b):
        return None
    return (signe * a, signe * b), p_out, (1 if signe > 0 else 0)


def outsider_challenger(rows):
    A, J = [], []
    for r in rows:
        if r['c'] != 'CH':
            continue
        cas = cas_outsider(r)
        if cas is not None:
            (A if r['d'] < COUPURE else J).append((r['zb'], cas))
    beta = ESC.apprendre([(z, x) for z, (x, _p, _y) in A], k=2)
    f = lambda z, x: z + beta[0] * x[0] + beta[1] * x[1]
    appr = bilan([z for z, _ in A], [f(z, c[0]) for z, c in A])
    juge = bilan([z for z, _ in J], [f(z, c[0]) for z, c in J])
    cote = lambda L: {'annonce_pct': round(100 * sum(c[1] for _, c in L) / len(L), 1),
                      'reel_pct': round(100 * sum(c[2] for _, c in L) / len(L), 1)} if L else {}
    oa, oj = cote(A), cote(J)
    raisons = []
    if juge.get('matchs', 0) < MIN_JUGES:
        raisons.append(f"moins de {MIN_JUGES} matchs jugés")
    if juge.get('gain', -1) < MARGE:
        raisons.append(f"gain sous {MARGE}")
    if not (oa and oj and oa['reel_pct'] > oa['annonce_pct'] and oj['reel_pct'] > oj['annonce_pct']):
        raisons.append("l'outsider concerné ne gagne pas plus qu'annoncé sur les deux périodes")
    detail = {}
    for nom, i in (('en_progression', 0), ('issu_des_qualifications', 1)):
        S = [c for _, c in J if c[0][i]]
        detail[nom] = {'matchs': len(S), 'annonce_pct': round(100 * sum(c[1] for c in S) / len(S), 1) if S else None,
                       'reel_pct': round(100 * sum(c[2] for c in S) / len(S), 1) if S else None}
    return {'decalages_appris': {'en_progression': round(beta[0], 4), 'issu_des_qualifications': round(beta[1], 4)},
            'outsider_2018_2022': oa, 'outsider_2023': oj, 'detail_2023': detail,
            '2018–2022': appr, '2023 → juin 2026': juge, 'retenu': not raisons, 'raisons': raisons,
            'passe_deux_erreurs_types': (not raisons) and (juge.get('erreurs_types') or 0) >= MIN_ERREURS_TYPES}


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    rows = lignes(archive, racine)
    betas = poser_la_base(rows)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("A — Grand Chelem en WTA : pente apprise sur 2018–2022, jugée une fois sur 2023 → juin 2026 (gain ≥ 0,001 "
                     "sur ≥ 1 000 matchs, ≥ 2 erreurs types, même sens). B — outsider en Challenger (15 à 45 %), en progression "
                     "ou issu des qualifications : deux décalages appris ensemble sur 2018–2022, jugés une fois sur 2023 → juin "
                     "2026 sur les matchs concernés (gain ≥ 0,001 sur ≥ 1 000 matchs, outsider au-dessus de l'annoncé sur les "
                     "deux périodes)"),
           'elo': "réglé comme la production (elo.de_production), mis à jour après chaque match ; compétitions par équipes exclues",
           'base': {'signaux': ['changement_surface', 'retour_absence_court', 'retour_absence_long', 'age_vieux', 'age_jeune'],
                    'betas_2018_2022': betas},
           'grand_chelem_wta': grand_chelem(rows, 'WTA'),
           'grand_chelem_atp_pour_memoire': grand_chelem(rows, 'ATP'),
           'outsider_challenger': outsider_challenger(rows),
           'en_production': False,
           'a_surveiller': ("Grand Chelem : quatre pentes voisines (WTA 1,23 puis 1,21 ; ATP 1,24 puis 1,21), mais aucun "
                            "circuit ne franchit seul les 2 erreurs types écrites dans la règle. Outsider en progression en "
                            "Challenger : au-dessus de l'annoncé sur les deux périodes, mais le décalage appris ne fait pas "
                            "gagner 0,001. Rien n'entre en production.")}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for nom in ('grand_chelem_wta', 'grand_chelem_atp_pour_memoire'):
        v = doc[nom]
        j = v['2023 → juin 2026']
        print(f"{nom} : pente {v['pente_apprise']} (sur 2023 → : {v['pente_sur_2023']}) ; {j['matchs']} matchs, favori {j['favori_reel_pct']} % "
              f"pour {j['favori_annonce_pct']} % ; gain {j['gain']} ± {j['erreur_type']} ; retenue : {v['retenue']} {v['raisons']}")
    o = doc['outsider_challenger']
    print('outsider Challenger :', o['decalages_appris'], '| 2018–2022', o['outsider_2018_2022'], o['2018–2022']['gain'], '| 2023 →', o['outsider_2023'],
          o['2023 → juin 2026']['matchs'], 'matchs, gain', o['2023 → juin 2026']['gain'], '±', o['2023 → juin 2026']['erreur_type'],
          '| détail', o['detail_2023'], '| retenu :', o['retenu'], o['raisons'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
