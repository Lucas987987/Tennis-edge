#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_depart_itf_femmes.py — les joueuses vues d'abord en ITF partent-elles trop haut ? (11/11/2026, audit, paquet 231)

D'où vient la question. Au paquet 230, faire partir de 1000 (au lieu de 1200) les joueurs vus d'abord en ITF hommes a
fait gagner 0,0057 de log loss au Challenger. Chez les femmes, l'archive a l'ITF depuis toujours (circuit « ITF » :
tournois ITF et qualifications), et une joueuse vue d'abord à ce niveau part elle aussi de 1200. Ici la méthode de
l'audit s'applique en entier : apprendre sur 2018–2022, juger sur 2023 → juin 2026.

Rejeu : archive Sackmann depuis 2012, Elo réglé COMME LA PRODUCTION (elo.de_production), mis à jour après chaque
match. Matchs jugés : WTA, sans abandon, sans compétitions par équipes.

RÈGLE ÉCRITE LE 11/11/2026 DANS rapport_audit.json (paquet 230), AVANT TOUT ESSAI :
  la FORME (départ des joueuses vues d'abord en ITF à 1150, 1100, 1050, 1000 ou 950) est CHOISIE sur les matchs WTA de
  2018–2022 (plus grand gain de log loss), puis jugée UNE SEULE FOIS sur 2023 → juin 2026 : gain ≥ 0,001 sur ≥ 1 000
  matchs WTA, même sens sur les deux périodes. Erreur type et Brier publiés ; « 2 erreurs types » publié à part.
  Avant toute mise en production : le classement complet (backtest_pronostic.py) est rejoué avec le réglage retenu, et
  nos matchs ne doivent pas faire moins bien.

Usage : python simulateur/etude_depart_itf_femmes.py /tmp/sackmann .
"""
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees as DN  # noqa: E402
import elo as E  # noqa: E402
import etude_outsiders as EO  # noqa: E402  (bilan : mêmes mesures)

DEBUT, COUPURE, FIN = dt.date(2018, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
MIN_JUGES, MARGE, MIN_ERREURS_TYPES = 1000, 0.001, 2.0
DEPARTS = (1150.0, 1100.0, 1050.0, 1000.0, 950.0)
BAS = ('CH', 'ITF', 'ITFH')
SORTIE = os.path.join(ICI, 'rapport_depart_itf_femmes.json')


def rejouer(M, racine, depart_itf=None):
    """[(date, z de la gagnante)] des matchs WTA jugés. depart_itf : départ des joueuses vues d'abord en ITF (None = le
    départ bas commun, 1200, comme aujourd'hui)."""
    el, bas = E.de_production(racine)
    rows = []
    for m in M:
        g, p = E.cle(m.get('nom_g')), E.cle(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m.get('surface')
        if bas and c in BAS:
            d0 = depart_itf if (c == 'ITF' and depart_itf is not None) else bas
            el.presenter(g, d0)
            el.presenter(p, d0)
        if c == 'WTA' and DEBUT <= m['date'] < FIN and not m.get('abandon') and m.get('niveau') != 'D':
            rows.append((m['date'], EO._lg(el.proba(g, p, s))))
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    return rows


def _z(rows, periode):
    return [z for d, z in rows if (d < COUPURE) == (periode == 'appr')]


def etudier(M, racine):
    base = rejouer(M, racine)
    cands = {}
    for d in DEPARTS:
        rows = rejouer(M, racine, depart_itf=d)
        cands[f"départ ITF {d:g}"] = {'depart_itf': d, 'rows': rows, '2018–2022': EO.bilan(_z(base, 'appr'), _z(rows, 'appr'))}
    choix = max(cands, key=lambda n: cands[n]['2018–2022']['gain'])
    C = cands[choix]
    juge = EO.bilan(_z(base, 'juge'), _z(C['rows'], 'juge'))
    raisons = []
    if juge.get('matchs', 0) < MIN_JUGES:
        raisons.append(f"moins de {MIN_JUGES} matchs jugés")
    if juge.get('gain', -1) < MARGE:
        raisons.append(f"gain sous {MARGE}")
    if C['2018–2022'].get('gain', -1) <= 0 or juge.get('gain', -1) <= 0:
        raisons.append("gain non positif sur les deux périodes")
    return {'candidats_2018_2022': {n: {k: v for k, v in c.items() if k != 'rows'} for n, c in cands.items()},
            'forme_choisie': choix, 'reglage': {'depart_itf': C['depart_itf']},
            '2023 → juin 2026': juge,
            'retenue': not raisons, 'raisons': raisons,
            'passe_deux_erreurs_types': (not raisons) and (juge.get('erreurs_types') or 0) >= MIN_ERREURS_TYPES}


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    doc = etudier(DN.charger(archive, 2012), racine)
    doc.update(genere_le=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
               regle=("départ des joueuses vues d'abord en ITF (1150, 1100, 1050, 1000 ou 950) choisi sur les matchs WTA de "
                      "2018–2022, jugé une seule fois sur 2023 → juin 2026 : gain ≥ 0,001 sur ≥ 1 000 matchs WTA, même sens "
                      "sur les deux périodes ; puis contrôle sur le classement complet rejoué"),
               elo="réglé comme la production (elo.de_production), mis à jour après chaque match ; compétitions par équipes exclues",
               en_production=False)
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for n, c in doc['candidats_2018_2022'].items():
        a = c['2018–2022']
        print(f"  {n:18s} 2018–2022 : gain {a['gain']} ± {a['erreur_type']} ({a['matchs']} matchs)")
    j = doc['2023 → juin 2026']
    print(f"CHOISI : {doc['forme_choisie']} | jugé sur {j['matchs']} matchs WTA : gain {j['gain']} ± {j['erreur_type']} "
          f"({j['erreurs_types']} erreurs types), Brier {j['brier_base']} → {j['brier']}, favori {j['favori_reel_pct']} % pour "
          f"{j['favori_annonce_pct']} % | retenue : {doc['retenue']} {doc['raisons']}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
