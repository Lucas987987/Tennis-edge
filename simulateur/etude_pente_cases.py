#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_pente_cases.py — CORRIGER LE % AVEC LA NOTE DE FIABILITÉ (21/11/2026, paquet 317, décision de Lucas : « Lance
l'étude », après l'analyse des niveaux : en Challenger, les matchs « fragile » et « prudent » sont trop confiants).

La note de fiabilité v3 (etude_fiabilite_v3.py) est la PENTE d'étalonnage a de la case du match (circuit × expérience
du moins connu × ampleur de la correction combinée), apprise sur 2016–2022 : réel ~ σ(a · logit p annoncé). Aujourd'hui
elle ne change aucun %. Question : appliquer cette pente au % (logit corrigé = a · logit) améliore-t-il les pronostics
sur des matchs jamais vus ? Rejeu et cases : exactement ceux de etude_fiabilite_v3.py (archive, Elo + correction
combinée, β et pentes appris sur 2016–2022).

DEUX VARIANTES, jugées CIRCUIT PAR CIRCUIT (ATP, WTA, Challenger) sur 2023 → juin 2026 :
  1. toutes_les_cases — chaque match corrigé par la pente de sa case ;
  2. notes_basses     — seulement les matchs dont la note est sous 85 (niveaux « fragile » et « prudent »).

RÈGLE ÉCRITE LE 21/11/2026, AVANT DE REGARDER LES RÉSULTATS (ne pas la modifier après coup), variante par variante et
circuit par circuit : RETENUE si, sur les matchs corrigés de 2023 → juin 2026 : au moins 1 000 matchs ; gain de log
loss ≥ 0,001 ; gain ≥ 2 erreurs types ; et la pente réapprise sur 2023 → juin 2026 sur ces mêmes matchs (avant
correction) est du MÊME CÔTÉ DE 1 que la pente moyenne appliquée. Une variante retenue n'entre dans l'algo que par un
paquet à part, avec sa règle de retrait. Rapport public : simulateur/rapport_pente_cases.json. Le % ne change pas.
Usage : python simulateur/etude_pente_cases.py /tmp/sackmann .
"""
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_signaux_combines as ESC  # noqa: E402
import etude_fiabilite_v3 as V3  # noqa: E402
import etude_outsiders as EO  # noqa: E402

COUPURE, FIN = V3.COUPURE, dt.date(2026, 7, 1)
MIN_JUGES, MARGE, MIN_ERREURS_TYPES = 1000, 0.001, 2.0
SEUIL_NOTE = 85
VARIANTES = ('toutes_les_cases', 'notes_basses')
SORTIE = os.path.join(ICI, 'rapport_pente_cases.json')


def preparer(archive, racine):
    rows = ESC.lignes(archive, racine)
    betas = {c: ESC.apprendre([(r['z'], r['x']) for r in rows if r['c'] == c and r['d'] < COUPURE]) for c in ('ATP', 'WTA', 'CH')}
    X = []
    for r in rows:
        d = sum(bi * xi for bi, xi in zip(betas[r['c']], r['x']))
        X.append({'d': r['d'], 'c': r['c'], 'z': r['z'] + d, 'k': V3.case(r['c'], min(r['n']), d)})
    modele = V3.apprendre_cases([(x['k'], x['c'], x['z']) for x in X if x['d'] < COUPURE])
    J = [x for x in X if COUPURE <= x['d'] < FIN]
    for x in J:
        m = modele.get(x['k'])
        x['a'] = m['pente'] if m else modele['_circuits'][x['c']]
        x['note'] = V3.note(x['a'])
    return J, modele


def juger(J, c, variante):
    G = [x for x in J if x['c'] == c and (variante == 'toutes_les_cases' or x['note'] < SEUIL_NOTE)]
    if not G:
        return {'matchs': 0, 'retenue': False, 'raisons': ['aucun match']}
    b = EO.bilan([x['z'] for x in G], [x['a'] * x['z'] for x in G])
    a_moy = sum(x['a'] for x in G) / len(G)
    a_jugee = V3.pente([x['z'] for x in G])
    raisons = []
    if b['matchs'] < MIN_JUGES:
        raisons.append(f'moins de {MIN_JUGES} matchs')
    if b['gain'] < MARGE:
        raisons.append(f'gain sous {MARGE}')
    if (b.get('erreurs_types') or 0) < MIN_ERREURS_TYPES:
        raisons.append(f'gain sous {MIN_ERREURS_TYPES:g} erreurs types')
    if (a_moy - 1) * (a_jugee - 1) <= 0:
        raisons.append("la pente de 2023 → juin 2026 n'est pas du même côté de 1")
    return {'pente_moyenne_appliquee': round(a_moy, 4), 'pente_2023': round(a_jugee, 4), '2023 → juin 2026': b,
            'retenue': not raisons, 'raisons': raisons}


def regle():
    return (__doc__.split('RÈGLE ÉCRITE LE 21/11/2026, AVANT DE REGARDER LES RÉSULTATS (ne pas la modifier après coup),')[1]
            .split('Usage')[0].replace('\n', ' ').replace('  ', ' ').strip())


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    J, modele = preparer(archive, racine)
    res = {v: {c: juger(J, c, v) for c in ('ATP', 'WTA', 'CH')} for v in VARIANTES}
    retenues = [f'{v} · {c}' for v, d in res.items() for c, r in d.items() if r.get('retenue')]
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 317, 'regle': regle(),
           'seuil_notes_basses': SEUIL_NOTE, 'variantes': res, 'retenues': retenues,
           'conclusion': ('retenues : ' + ', '.join(retenues)) if retenues else 'aucune variante ne passe la règle',
           'descriptif': 'le % de victoire ne change pas'}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for v, d in res.items():
        for c, r in d.items():
            b = r.get('2023 → juin 2026') or {}
            print(f"{v:17s} {c:3s} n={b.get('matchs')} a_appl={r.get('pente_moyenne_appliquee')} a23={r.get('pente_2023')} "
                  f"gain={b.get('gain')} et={b.get('erreurs_types')} brier {b.get('brier_base')}→{b.get('brier')} "
                  f"{'RETENUE' if r.get('retenue') else ', '.join(r.get('raisons', []))}")
    print(doc['conclusion'])


if __name__ == '__main__':
    main(sys.argv)
