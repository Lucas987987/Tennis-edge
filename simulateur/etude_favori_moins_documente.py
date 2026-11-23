#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_favori_moins_documente.py — tranche 500–1 500 : l'algo est-il trop sûr quand le FAVORI est le joueur le moins
documenté ? (23/11/2026, paquet 373, demande de Lucas « améliorons ça »)

CONSTAT EN DIRECT (site, documentation au jour du match, paquet 372) : tranche 500–1 500 points, 154 matchs, favoris
annoncés 68,2 %, gagnants 61,0 %. Le classement Elo seul (68,3 → 63,0) et la simulation seule (68,2 → 59,5) sont
tous deux trop sûrs. Piste : quand le favori est le MOINS documenté des deux (26 matchs : 61,3 % annoncés, 42,3 %
gagnés), contre 70,2 % → 67,3 % quand le favori est le plus documenté (101 matchs). 26 matchs ne prouvent rien.
Les études précédentes sur rejeu ne trouvaient pas d'écart dans la tranche entière (paquet 368 : pente 1,00 ; balayage
« expérience du moins vu », Challenger moins de 30 matchs : pente 1,04) ; aucune ne séparait le côté du favori.

RÈGLE ÉCRITE LE 23/11/2026 AVANT D'EXÉCUTER L'ÉTUDE :
  • rejeu de l'Elo de PRODUCTION (E.de_production, départs en place, résultats ITF hommes collectés compris) sur
    l'archive depuis 2012, pronostic AVANT la mise à jour de chaque match ;
  • documentation = points de service cumulés avant le jour du match (même compteur que la production) ;
  • cases : circuit (ATP, WTA, Challenger séparés) × tranche du joueur le moins documenté (500–1 500, et les autres
    tranches pour comparaison) × côté du favori (le moins documenté / le plus documenté) ;
  • correction : p' = σ(a · logit p) sur la probabilité du favori, a appris sur 2018–2022, jugé sur 2023 → fin de
    l'archive ;
  • RETENUE seulement si, dans la case : au moins 1 000 matchs jugés, la log loss du jugement baisse d'au moins 0,001,
    ET la pente mesurée sur chacune des deux périodes est du même côté de 1 (même sens sur les deux périodes).
  • Une case retenue n'est PAS mise en service par ce script : elle est proposée à Lucas (paquet suivant).
Usage : python simulateur/etude_favori_moins_documente.py /tmp/sackmann .
Sortie : simulateur/rapport_favori_moins_documente.json
"""
import collections
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo as E  # noqa: E402
import etude_documentation as EDO  # noqa: E402

DEBUT_APPR, COUPURE = '2018-01-01', '2023-01-01'
MIN_JUGES, MARGE = 1000, 0.001
TRANCHES = ((0, 500, 'moins de 500'), (500, 1500, '500 à 1 500'), (1500, 3000, '1 500 à 3 000'),
            (3000, float('inf'), '3 000 et plus'))
CIRCUITS = ('ATP', 'WTA', 'CH')
SORTIE = os.path.join(ICI, 'rapport_favori_moins_documente.json')


def tranche(b):
    return next(lib for a, z, lib in TRANCHES if a <= b < z)


def rejouer(M, evenements, racine):
    """[(jour ISO, circuit, tranche, côté du favori, p du favori, y)] depuis DEBUT_APPR, ATP/WTA/CH."""
    import backtest_pronostic as BP
    el, bas = E.de_production(racine)
    C = EDO.Compteur(evenements)
    rows = []
    for m in M:
        g, p = E.cle(m.get('nom_g')), E.cle(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m.get('surface')
        if bas and c in BP.BAS:
            el.presenter(g, E.depart_du_niveau(c, bas))
            el.presenter(p, E.depart_du_niveau(c, bas))
        jour = m['date'].isoformat()
        if c in CIRCUITS and jour >= DEBUT_APPR and not m.get('abandon') and m.get('niveau') != 'D':
            n = C.au(jour)
            dg, dp = n.get(g, 0), n.get(p, 0)
            pg = el.proba(g, p, s)
            fav_g = pg >= .5
            pf = pg if fav_g else 1 - pg
            d_fav, d_aut = (dg, dp) if fav_g else (dp, dg)
            cote = 'favori_moins_documente' if d_fav < d_aut else 'favori_plus_documente'
            rows.append((jour, c, tranche(min(dg, dp)), cote, pf, 1 if fav_g else 0))
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    return rows


def _resume(R):
    n = len(R)
    return {'n': n, 'annonce_pct': round(100 * sum(p for p, _ in R) / n, 1) if n else None,
            'gagne_pct': round(100 * sum(y for _, y in R) / n, 1) if n else None}


def juger_case(A, J):
    out = {'apprentissage': _resume(A), 'jugement': _resume(J)}
    if len(A) < 100 or not J:
        out.update(retenue=False, raison='trop peu de matchs')
        return out
    a = EDO.pente(A)
    a_j = EDO.pente(J)
    sans, avec = EDO.ll(J), EDO.ll(J, a)
    gain = sans - avec
    meme_sens = (a - 1) * (a_j - 1) > 0
    ok = len(J) >= MIN_JUGES and gain >= MARGE and meme_sens
    out.update(pente_apprise=round(a, 3), pente_jugement=round(a_j, 3), log_loss_sans=round(sans, 5),
               log_loss_avec=round(avec, 5), gain=round(gain, 5), meme_sens=meme_sens, retenue=ok)
    if not ok:
        out['raison'] = ('moins de 1 000 matchs jugés' if len(J) < MIN_JUGES else
                         'gain inférieur à 0,001' if gain < MARGE else 'pas le même sens sur les deux périodes')
    return out


def etudier(rows):
    G = collections.defaultdict(lambda: ([], []))
    for jour, c, tr, cote, pf, y in rows:
        G[(c, tr, cote)][0 if jour < COUPURE else 1].append((pf, y))
        G[(c, tr, 'tous')][0 if jour < COUPURE else 1].append((pf, y))
    cases = []
    for (c, tr, cote), (A, J) in sorted(G.items()):
        cases.append(dict(circuit=c, tranche=tr, cote=cote, **juger_case(A, J)))
    return cases


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    import etude_depart_itf as ED
    M, n_itf = ED.matchs(archive, racine)
    rows = rejouer(M, EDO.evenements(archive, racine), racine)
    cases = etudier(rows)
    fin = max(r[0] for r in rows) if rows else None
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'periodes': {'apprentissage': f"{DEBUT_APPR} → {COUPURE}", 'jugement': f"{COUPURE} → {fin}"},
           'matchs_rejoues': len(rows), 'resultats_itf_hommes_dans_le_rejeu': n_itf,
           'regle': ("pente a sur la probabilité du favori, apprise sur 2018–2022, jugée sur 2023 → fin de l'archive ; "
                     "retenue si ≥ 1 000 matchs jugés, gain de log loss ≥ 0,001 et pente du même côté de 1 sur les deux "
                     "périodes ; jamais mise en service par ce script"),
           'cases': cases,
           'retenues': [{k: x[k] for k in ('circuit', 'tranche', 'cote', 'pente_apprise', 'gain')}
                        for x in cases if x.get('retenue')]}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"Favori moins documenté : {len(rows)} matchs rejoués, {len(cases)} cases, {len(doc['retenues'])} retenue(s)")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
