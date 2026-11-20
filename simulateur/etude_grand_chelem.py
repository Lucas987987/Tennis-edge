#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_grand_chelem.py — pente commune ATP + WTA en Grand Chelem (11/11/2026, paquet 231) : DÉCISION DE LUCAS.

CE QUE CETTE ÉTUDE N'EST PAS. Ce n'est pas une étude qui passe sa règle. La règle écrite à l'avance (paquet 229 :
pente propre aux Grands Chelems en WTA, ≥ 0,001 sur ≥ 1 000 matchs, ≥ 2 erreurs types, même sens) a été jugée au
paquet 230 et n'est PAS passée : gain 0,0032 ± 0,0020, soit 1,6 erreur type (rapport_outsiders.json). L'ATP, regardé
pour mémoire, donne le même tableau. L'idée d'une pente COMMUNE aux deux circuits est venue APRÈS avoir vu ces
résultats : elle ne peut donc plus être « jugée » sur 2023 → juin 2026, et les chiffres de cette période sont publiés
ici pour mémoire, pas comme une preuve.

CE QU'ELLE FAIT. Lucas a décidé le 11/11/2026 de mettre cette pente en place, la règle de retrait jugeant la suite.
Pour ne rien régler sur la période déjà vue, la pente est apprise sur 2018–2022 SEULEMENT, les deux circuits ensemble,
tableau principal, sans abandon. Base : Elo de production + les trois signaux solides (etude_outsiders.py).

Constat : en Grand Chelem le favori gagne plus souvent que l'Elo ne l'annonce, dans les deux circuits et sur les deux
périodes. Raisons plausibles (non prouvées) : 3 sets gagnants chez les hommes, un jour de repos entre les tours,
des favoris qui préparent ces tournois.

En production : simulateur/grand_chelem.json, lu par pronostics_du_jour.py (controle_grand_chelem). Seule la part de
l'Elo du % bouge, comme pour le format du match. RETRAIT (écrit avant tout match suivi) : règle cumulée de
fantomes_circuits.py — par circuit, dès 300 matchs de Grand Chelem suivis, si le gain propre du signal est négatif de
plus de 2 erreurs types, il est retiré.

Usage : python simulateur/etude_grand_chelem.py /tmp/sackmann .
"""
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_outsiders as EO  # noqa: E402

SORTIE = os.path.join(ICI, 'rapport_grand_chelem.json')
# Contrôle fait le 11/11/2026 sur NOS matchs de Grand Chelem déjà joués (US Open 2026, tableau principal, à partir du
# 30/08), avec le classement de production rejoué : même sens, mais 196 matchs ne permettent pas de conclure.
CONTROLE_NOS_MATCHS = {
    'fait_le': '2026-11-11', 'tournoi': 'US Open 2026, tableau principal', 'matchs': 196,
    'favori_reel_pct': 76.0, 'favori_annonce_pct': 70.2, 'pente_propre': 1.25,
    'gain_de_la_pente_commune': 0.00469, 'erreur_type': 0.0066, 'brier_avant': 0.17711, 'brier': 0.1749,
    'lecture': "même sens que l'archive ; trop peu de matchs pour conclure (0,7 erreur type)",
    'qualifications_pour_memoire': {
        'matchs': 280, 'favori_reel_pct': 68.2, 'favori_annonce_pct': 62.2,
        'lecture': ("les qualifications ne sont pas dans l'étude et la pente ne s'y applique pas ; l'Elo y paraît lui aussi "
                    "trop prudent : à étudier à part")},
}
CIRCUITS = ('ATP', 'WTA')


def _z(rows, circuits, juge, gc=True):
    return [r['zb'] for r in rows if r['c'] in circuits and (r['niveau'] == 'G') == gc and (r['d'] >= EO.COUPURE) == juge]


def etudier(rows):
    A = _z(rows, CIRCUITS, False)
    k = EO.pente(A)
    doc = {'pente_commune_apprise_sur_2018_2022': round(k, 3),
           '2018–2022': EO.bilan(A, [k * z for z in A]),
           'pour_memoire_2023_juin_2026': {}, 'hors_grand_chelem_pente_propre_2018_2022': {}}
    for nom, cs in (('ATP + WTA', CIRCUITS), ('ATP', ('ATP',)), ('WTA', ('WTA',))):
        J = _z(rows, cs, True)
        b = EO.bilan(J, [k * z for z in J])
        b['pente_propre'] = round(EO.pente(J), 3) if len(J) >= 200 else None
        doc['pour_memoire_2023_juin_2026'][nom] = b
    for c in CIRCUITS:
        H = _z(rows, (c,), False, gc=False)
        doc['hors_grand_chelem_pente_propre_2018_2022'][c] = {'matchs': len(H), 'pente': round(EO.pente(H), 3)}
    return doc


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    rows = EO.lignes(archive, racine)
    EO.poser_la_base(rows)
    doc = etudier(rows)
    doc.update(genere_le=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
               statut=("DÉCISION DE LUCAS (11/11/2026). La règle écrite à l'avance (WTA seule, 2 erreurs types) n'est pas "
                       "passée au paquet 230. La pente commune n'était pas écrite à l'avance : les chiffres de 2023 → juin "
                       "2026 sont publiés pour mémoire, pas comme une preuve."),
               elo="réglé comme la production (elo.de_production), mis à jour après chaque match ; compétitions par équipes exclues",
               controle_nos_matchs=CONTROLE_NOS_MATCHS,
               production={'fichier': 'simulateur/grand_chelem.json',
                           'pentes': {c: doc['pente_commune_apprise_sur_2018_2022'] for c in CIRCUITS},
                           'ou': "tableau principal seulement : le tour doit être connu et ne pas être un tour de qualifications",
                           'comment': "décalage (logit) = poids de l'Elo dans le mélange × (pente − 1) × logit(p Elo)"},
               retrait=("règle cumulée (fantomes_circuits.REGLE_CUMULEE), par circuit : dès 300 matchs de Grand Chelem suivis, "
                        "si le gain propre du signal est négatif de plus de 2 erreurs types, il est retiré"))
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    a = doc['2018–2022']
    print(f"pente commune (2018–2022, {a['matchs']} matchs) : {doc['pente_commune_apprise_sur_2018_2022']} ; gain {a['gain']} ± {a['erreur_type']}")
    for nom, b in doc['pour_memoire_2023_juin_2026'].items():
        print(f"  pour mémoire 2023 → {nom:9s}: {b['matchs']} matchs, favori {b['favori_reel_pct']} % pour {b['favori_annonce_pct']} %, pente propre "
              f"{b['pente_propre']}, gain {b['gain']} ± {b['erreur_type']} ({b['erreurs_types']} e.t.), Brier {b['brier_base']} → {b['brier']}")
    print('  hors Grand Chelem, pente propre 2018–2022 :', doc['hors_grand_chelem_pente_propre_2018_2022'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
