#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_depart_itf.py — les joueurs vus d'abord en ITF hommes partent-ils trop haut ? (11/11/2026, audit, paquet 230)

D'où vient la question. L'étude etude_joueurs_peu_vus.py passe sa règle sur l'archive (Challenger, +0,00105 ± 0,00027
sur 2023 → juin 2026), mais l'archive n'a pas les résultats ITF hommes que la production met dans l'Elo depuis le
28/10/2026. Rejoué AVEC ces résultats (du 01/06/2024 à juin 2026), l'Elo du Challenger change de visage : il devient
PAS ASSEZ tranché dans toutes les tranches d'expérience (favori 67,3 % réels pour 66,1 % annoncés entre 30 et 99
matchs, 63,3 % pour 62,0 % au-delà), et les pentes de l'étude y feraient PERDRE 0,00115. Elles ne sont donc pas mises
en production. Piste : un joueur vu d'abord en ITF part aujourd'hui à 1200, comme un joueur vu d'abord en Challenger,
alors que le niveau est plus bas ; il serait trop bien noté face aux habitués du Challenger.

Cette piste NE PEUT PAS être jugée sur 2018–2022 puis 2023 → : les résultats ITF hommes n'existent que depuis juin
2024. Avant d'écrire cette règle, j'ai vu une seule chose de la période : les pentes par tranche citées ci-dessus,
mesurées sur toute la fenêtre 2025 → juin 2026. Aucun départ ITF n'a été essayé.

Rejeu : archive Sackmann depuis 2012 + résultats ITF hommes du dépôt (resultats_itf/), Elo réglé COMME LA PRODUCTION
(elo.de_production), mis à jour après chaque match. Matchs jugés : Challenger (et ATP pour contrôle), sans abandon,
sans compétitions par équipes.

RÈGLE ÉCRITE LE 11/11/2026, AVANT TOUT ESSAI :
  la FORME est choisie sur le Challenger du 01/01/2025 au 30/09/2025 (plus grand gain de log loss) parmi :
    - départ des joueurs vus d'abord en ITF hommes à 1150, 1100, 1050 ou 1000 (le départ Challenger reste à 1200) ;
    - une pente unique sur le Challenger, p' = σ(pente · logit p), le départ ITF restant à 1200.
  Elle est jugée UNE SEULE FOIS sur le Challenger du 01/10/2025 à juin 2026 et retenue si : gain ≥ 0,001 sur ≥ 1 000
  matchs, gain positif sur les deux périodes, et ATP non dégradé de plus de 0,0005 sur la même période.
  Erreur type et Brier publiés ; la condition « 2 erreurs types » est publiée à part.
  Avant toute mise en production : le classement complet (backtest_pronostic.py) est rejoué avec le réglage retenu, et
  « nos matchs » (août → octobre 2026, hors de tout ce qui précède) ne doivent pas faire moins bien.

RÉSULTAT (11/11/2026) : forme choisie = départ ITF à 1000 (bord de la grille) ; jugée sur 7 722 matchs Challenger :
gain 0,0057 ± 0,0007, Brier 0,2055 → 0,2030 ; ATP inchangé. RETENUE. Contrôle de production fait le même jour
(CONTROLE_PRODUCTION ci-dessous) : nos matchs passent de 0,6225 à 0,6205 de log loss. Mise en production :
elo.DEPARTS_PAR_NIVEAU, lu par backtest_pronostic.py ; retrait : règle cumulée écrite dans elo.py.
Le choix tombe au bord de la grille : un départ plus bas encore n'est PAS essayé ici (la période jugée a servi) ;
il sera jugé sur nos matchs à venir (rapport_audit.json, suites).

Usage : python simulateur/etude_depart_itf.py /tmp/sackmann .
"""
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import backtest_pronostic as BP  # noqa: E402
import donnees as DN  # noqa: E402
import elo as E  # noqa: E402
import etude_outsiders as EO  # noqa: E402  (pente, bilan : mêmes mesures)

DEBUT, COUPURE, FIN = dt.date(2025, 1, 1), dt.date(2025, 10, 1), dt.date(2026, 7, 1)
MIN_JUGES, MARGE, MIN_ERREURS_TYPES, DEGRADATION_MAX = 1000, 0.001, 2.0, 0.0005
DEPARTS_ITF = (1150.0, 1100.0, 1050.0, 1000.0)
SORTIE = os.path.join(ICI, 'rapport_depart_itf.json')
# Contrôle prévu par la règle, fait le 11/11/2026 : backtest_pronostic.py rejoué en entier avec l'ancien départ (1200)
# puis avec le départ retenu (1000). « Nos matchs » = août → octobre 2026, hors de tout ce que l'étude a vu.
CONTROLE_PRODUCTION = {
    'fait_le': '2026-11-11',
    'nos_matchs_tous_niveaux': {'matchs': 2859, 'log_loss_avant': 0.6225, 'log_loss': 0.6205, 'brier': 0.2159},
    'nos_matchs_challenger': {'matchs': 912, 'gain_log_loss': 0.00767, 'erreur_type': 0.00207,
                              'brier_avant': 0.21731, 'brier': 0.21407},
    'atp_wta_2024_2026': {'matchs': 9277, 'log_loss_avant': 0.6064, 'log_loss': 0.6065},
    'verdict': "nos matchs ne font pas moins bien : mise en production",
}


def matchs(archive, racine):
    M = DN.charger(archive, 2012)
    fin = max(m['date'] for m in M)
    itf = [m for m in BP.resultats_itf(racine) if m['date'] <= fin and m['circuit'] == 'ITFH']
    return sorted(M + itf, key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0))), len(itf)


def rejouer(M, racine, depart_itf=None):
    """[(circuit, date, z du vainqueur)] pour le Challenger et l'ATP depuis DEBUT. depart_itf : note de départ des joueurs
    vus d'abord en ITF hommes (None = la même que le Challenger, comme aujourd'hui)."""
    el, bas = E.de_production(racine)
    rows = []
    for m in M:
        g, p = E.cle(m.get('nom_g')), E.cle(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m.get('surface')
        if bas and c in BP.BAS:
            d0 = depart_itf if (c == 'ITFH' and depart_itf is not None) else bas      # None : l'ancien réglage, 1200
            el.presenter(g, d0)
            el.presenter(p, d0)
        if c in ('CH', 'ATP') and DEBUT <= m['date'] < FIN and not m.get('abandon') and m.get('niveau') != 'D':
            rows.append((c, m['date'], EO._lg(el.proba(g, p, s))))
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    return rows


def _z(rows, c, periode):
    return [z for cc, d, z in rows if cc == c and (d < COUPURE) == (periode == 'appr')]


def etudier(M, racine):
    base = rejouer(M, racine)
    cands = {}
    for d in DEPARTS_ITF:
        rows = rejouer(M, racine, depart_itf=d)
        cands[f"départ ITF {d:g}"] = {'depart_itf': d, 'rows': rows,
                                      'appr': EO.bilan(_z(base, 'CH', 'appr'), _z(rows, 'CH', 'appr'))}
    k = EO.pente(_z(base, 'CH', 'appr'))
    pentu = [(c, d, (k * z if c == 'CH' else z)) for c, d, z in base]
    cands['pente Challenger'] = {'pente': round(k, 3), 'rows': pentu,
                                 'appr': EO.bilan(_z(base, 'CH', 'appr'), _z(pentu, 'CH', 'appr'))}
    choix = max(cands, key=lambda n: cands[n]['appr']['gain'])
    C = cands[choix]
    juge = EO.bilan(_z(base, 'CH', 'juge'), _z(C['rows'], 'CH', 'juge'))
    atp = EO.bilan(_z(base, 'ATP', 'juge'), _z(C['rows'], 'ATP', 'juge'))
    raisons = []
    if juge.get('matchs', 0) < MIN_JUGES:
        raisons.append(f"moins de {MIN_JUGES} matchs jugés")
    if juge.get('gain', -1) < MARGE:
        raisons.append(f"gain sous {MARGE}")
    if C['appr'].get('gain', -1) <= 0 or juge.get('gain', -1) <= 0:
        raisons.append("gain non positif sur les deux périodes")
    if atp.get('gain', 0) < -DEGRADATION_MAX:
        raisons.append(f"ATP dégradé de plus de {DEGRADATION_MAX}")
    return {'candidats_2025_01_a_2025_09': {n: {kk: vv for kk, vv in c.items() if kk != 'rows'} for n, c in cands.items()},
            'forme_choisie': choix, 'reglage': {kk: vv for kk, vv in C.items() if kk in ('depart_itf', 'pente')},
            'challenger_2025_10_a_2026_06': juge, 'atp_2025_10_a_2026_06': atp,
            'autres_candidats_sur_la_periode_jugee_pour_memoire': {
                n: EO.bilan(_z(base, 'CH', 'juge'), _z(c['rows'], 'CH', 'juge'))['gain'] for n, c in cands.items() if n != choix},
            'retenue': not raisons, 'raisons': raisons,
            'passe_deux_erreurs_types': (not raisons) and (juge.get('erreurs_types') or 0) >= MIN_ERREURS_TYPES}


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    M, n_itf = matchs(archive, racine)
    doc = etudier(M, racine)
    doc.update(genere_le=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), itf_hommes_dans_le_rejeu=n_itf,
               regle=("forme choisie sur le Challenger du 01/01/2025 au 30/09/2025 (départ ITF hommes à 1150, 1100, 1050 ou "
                      "1000, ou pente unique), jugée une fois sur le Challenger du 01/10/2025 à juin 2026 : gain ≥ 0,001 sur "
                      "≥ 1 000 matchs, positif sur les deux périodes, ATP non dégradé de plus de 0,0005"),
               pourquoi_ces_dates="les résultats ITF hommes n'existent que depuis juin 2024 : 2018–2022 est impossible",
               elo="réglé comme la production (elo.de_production), résultats ITF hommes compris, mis à jour après chaque match",
               controle_production=CONTROLE_PRODUCTION,
               production=({'depart': dict(E.DEPARTS_PAR_NIVEAU), 'ancien_depart': 1200.0,
                            'retrait': (f"le classement est rejoué à chaque passage avec l'ancien départ ; sur nos matchs "
                                        f"Challenger depuis le {E.DEPARTS_SUIVI_DEPUIS}, dès {E.DEPARTS_RETRAIT_MIN_MATCHS} matchs, "
                                        f"gain cumulé négatif de plus de {E.DEPARTS_RETRAIT_ERREURS_TYPES:g} erreurs types → retour "
                                        f"à 1200"),
                            'suivi': 'simulateur/rapport_pronostic.json, clé depart_itf_hommes'}
                           if doc['retenue'] else None),
               limite=("le choix tombe au bord de la grille (1000) : un départ plus bas n'a pas été essayé, la période jugée "
                       "ayant servi ; à juger sur nos matchs à venir"))
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for n, c in doc['candidats_2025_01_a_2025_09'].items():
        print(f"  {n:20s} apprentissage : gain {c['appr']['gain']} ± {c['appr']['erreur_type']} ({c['appr']['matchs']} matchs)")
    j = doc['challenger_2025_10_a_2026_06']
    print(f"CHOISI : {doc['forme_choisie']} {doc['reglage']} | jugé sur {j['matchs']} matchs : gain {j['gain']} ± {j['erreur_type']} "
          f"({j['erreurs_types']} erreurs types), Brier {j['brier_base']} → {j['brier']}, favori {j['favori_reel_pct']} % pour {j['favori_annonce_pct']} % "
          f"| ATP {doc['atp_2025_10_a_2026_06']['gain']} | retenue : {doc['retenue']} {doc['raisons']}")
    print('  pour mémoire, les autres sur la période jugée :', doc['autres_candidats_sur_la_periode_jugee_pour_memoire'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
