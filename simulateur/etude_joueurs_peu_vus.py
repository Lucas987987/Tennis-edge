#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_joueurs_peu_vus.py — en Challenger, l'Elo est-il mal étalonné selon l'expérience du joueur le moins vu ?
(11/11/2026, audit, paquet 230)

Constat de l'audit, fait sur 2018–2022 SEULEMENT (simulateur/rapport_audit.json, paquet 227) : l'option « incertitude »
de l'Elo (elo.proba) resserre trop le % avant 10 matchs (favori 71,4 % réels pour 66,8 % annoncés, pente 1,28) et pas
assez entre 10 et 100 matchs (pentes 0,84 et 0,88). La correction en place depuis le 05/11/2026 (« matchs peu
documentés », pente 1,84 sous 500 points de service) a été apprise sur 325 matchs et jugée sur 156.

Rejeu : archive Sackmann depuis 2012, Elo réglé COMME LA PRODUCTION (elo.de_production), mis à jour après chaque
match. Matchs jugés : Challenger, sans abandon. LIMITE CONNUE : l'archive n'a pas les résultats ITF hommes que la
production met dans l'Elo ; un joueur y paraît donc moins vu qu'en production.

RÈGLE ÉCRITE LE 11/11/2026 (rapport_audit.json, paquet 227), AVANT DE REGARDER 2023 → :
  une pente par tranche d'expérience du joueur le moins vu (moins de 10 matchs, 10 à 29, 30 à 99, 100 et plus),
  p' = σ(pente · logit p), apprise sur 2018–2022, jugée une seule fois sur 2023 → juin 2026 en Challenger. Retenue si
  le gain de log loss sur TOUS les matchs Challenger jugés atteint 0,001 sur au moins 1 000 matchs et s'il est positif
  sur les deux périodes. Erreur type et Brier publiés ; la condition « 2 erreurs types » est publiée à part.

Usage : python simulateur/etude_joueurs_peu_vus.py /tmp/sackmann .
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
import etude_outsiders as EO  # noqa: E402  (pente, bilan, _lg : mêmes mesures)

DEBUT, COUPURE, FIN = dt.date(2018, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
MIN_JUGES, MARGE, MIN_ERREURS_TYPES = 1000, 0.001, 2.0
TRANCHES = ((0, 10, 'moins de 10'), (10, 30, '10 à 29'), (30, 100, '30 à 99'), (100, 10 ** 9, '100 et plus'))
SORTIE = os.path.join(ICI, 'rapport_joueurs_peu_vus.json')
# CONTRÔLE « COMME EN PRODUCTION », fait le 11/11/2026 après le verdict : le même Elo AVEC les résultats ITF hommes
# (que la production utilise depuis le 28/10/2026 et que l'archive n'a pas), Challenger du 01/01/2025 à juin 2026.
# L'expérience d'un joueur n'y est plus la même (15 % des matchs « moins de 10 » sans l'ITF, 3 % avec) et l'Elo y est
# PAS ASSEZ tranché dans toutes les tranches : les pentes de l'étude y feraient perdre. Elles ne sont donc PAS mises en
# production. La cause est traitée à la source par etude_depart_itf.py (départ des joueurs vus d'abord en ITF).
CONTROLE_PRODUCTION = {
    'fait_le': '2026-11-11', 'periode': '01/01/2025 → juin 2026', 'matchs': 16471,
    'sans_itf_comme_l_etude': {'gain_des_pentes': 0.00087, 'erreur_type': 0.00041},
    'avec_itf_comme_la_production': {
        'gain_des_pentes': -0.00115, 'erreur_type': 0.00027,
        'pente_propre_par_tranche': {'moins de 10': 1.47, '10 à 29': 1.08, '30 à 99': 1.14, '100 et plus': 1.11},
        'part_des_matchs_pct': {'moins de 10': 2.7, '10 à 29': 6.5, '30 à 99': 35.6, '100 et plus': 55.2}},
    'verdict': "passe sur l'archive, échoue avec l'Elo de production : pas de mise en production",
}


def tranche(n):
    for lo, hi, nom in TRANCHES:
        if lo <= n < hi:
            return nom
    return TRANCHES[-1][2]


def lignes(archive, racine, circuit='CH'):
    """[(date, matchs du joueur le moins vu, z du vainqueur)] — Elo de production, lu avant le match."""
    M = DN.charger(archive, 2012)
    etat = E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8')))
    alias = dict(etat.get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    el, bas = E.de_production(racine)
    rows = []
    for m in M:
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m['surface']
        if bas and c in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        if c == circuit and DEBUT <= m['date'] < FIN and not m.get('abandon') and m.get('niveau') != 'D':
            rows.append((m['date'], min(el.matchs(g), el.matchs(p)), EO._lg(el.proba(g, p, s))))
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') else None)
    return rows


def etudier(rows):
    A = [r for r in rows if r[0] < COUPURE]
    J = [r for r in rows if r[0] >= COUPURE]
    pentes, detail = {}, {}
    for _lo, _hi, nom in TRANCHES:
        za = [z for _d, n, z in A if tranche(n) == nom]
        zj = [z for _d, n, z in J if tranche(n) == nom]
        k = EO.pente(za) if len(za) >= 200 else 1.0
        pentes[nom] = round(k, 3)
        detail[nom] = {'pente_apprise': round(k, 3), 'pente_sur_2023': round(EO.pente(zj), 3) if len(zj) >= 200 else None,
                       '2018–2022': EO.bilan(za, [k * z for z in za]), '2023 → juin 2026': EO.bilan(zj, [k * z for z in zj])}
    f = lambda L: ([z for _d, _n, z in L], [pentes[tranche(n)] * z for _d, n, z in L])
    appr, juge = EO.bilan(*f(A)), EO.bilan(*f(J))
    raisons = []
    if juge.get('matchs', 0) < MIN_JUGES:
        raisons.append(f"moins de {MIN_JUGES} matchs jugés")
    if juge.get('gain', -1) < MARGE:
        raisons.append(f"gain sous {MARGE}")
    if appr.get('gain', -1) <= 0 or juge.get('gain', -1) <= 0:
        raisons.append("gain non positif sur les deux périodes")
    return {'pentes': pentes, 'par_tranche': detail, '2018–2022': appr, '2023 → juin 2026': juge,
            'retenue': not raisons, 'raisons': raisons,
            'passe_deux_erreurs_types': (not raisons) and (juge.get('erreurs_types') or 0) >= MIN_ERREURS_TYPES}


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    doc = etudier(lignes(archive, racine))
    doc.update(genere_le=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
               regle=("Challenger : une pente par tranche d'expérience du joueur le moins vu, apprise sur 2018–2022, jugée une "
                      "fois sur 2023 → juin 2026 ; retenue si le gain sur tous les matchs jugés atteint 0,001 sur au moins "
                      "1 000 matchs et s'il est positif sur les deux périodes"),
               elo="réglé comme la production (elo.de_production), mis à jour après chaque match",
               limite="l'archive n'a pas les résultats ITF hommes : un joueur y paraît moins vu qu'en production",
               controle_production=CONTROLE_PRODUCTION, en_production=False)
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for nom, v in doc['par_tranche'].items():
        j = v['2023 → juin 2026']
        print(f"{nom:12s} pente {v['pente_apprise']} (sur 2023 → : {v['pente_sur_2023']}) ; {j['matchs']} matchs, favori {j.get('favori_reel_pct')} % "
              f"pour {j.get('favori_annonce_pct')} % ; gain {j.get('gain')} ± {j.get('erreur_type')}")
    j = doc['2023 → juin 2026']
    print(f"ENSEMBLE : {j['matchs']} matchs, gain {j['gain']} ± {j['erreur_type']} ({j['erreurs_types']} erreurs types), Brier {j['brier_base']} → {j['brier']} ; "
          f"retenue : {doc['retenue']} {doc['raisons']}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
