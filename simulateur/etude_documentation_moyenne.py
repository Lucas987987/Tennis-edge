#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_documentation_moyenne.py — L'ALGO EST-IL TROP SÛR DE LUI SUR LES MATCHS MOYENNEMENT DOCUMENTÉS (500 À 1 500
POINTS) ? (23/11/2026, paquet 368, Lucas : « Faisons un test avec la même stratégie sur 500-1500 »)

CONSTAT (site, bilan selon la documentation ; nos pronostics en direct depuis le 22/10) : quand le joueur le moins
documenté du match a 500 à 1 500 points de service, le favori gagne 58,8 % des matchs pour 66,8 % annoncés (250
matchs, 94 % Challenger). L'écart vient surtout de la simulation (−12,5 points) ; il est le plus fort quand le joueur
peu documenté est lui-même le favori. Sous 500 points, l'étude du 05/11 (etude_documentation.py) avait trouvé l'inverse
(algo trop prudent) et une pente > 1 est en place en Challenger.

MÊME STRATÉGIE QUE L'ÉTUDE DU 05/11, SUR LA TRANCHE SUIVANTE :
  • données : les pronostics rejoués hors échantillon (pronostics_hors_echantillon.jsonl.gz, % de l'algo p_algo,
    27/07 → 16/11/2026) ; « documentation » = points de service du joueur le moins vu, cumulés AVANT le jour du match
    (archive Sackmann depuis 2012 + feuilles TennisApi après l'archive ; même compteur que etude_documentation.py) ;
  • tranche : 500 ≤ points < 1 500 ;
  • correction : p' = σ(a · logit p), a par circuit (a < 1 : on rapproche de 50 %).
RÈGLE FIXÉE LE 23/11/2026, AVANT DE REGARDER CE FICHIER SUR CETTE TRANCHE (ne pas la modifier après coup) :
  • a appris sur les matchs avant le 29/09/2026, jugé sur ceux à partir du 29/09/2026 (même coupure que le 05/11) ;
  • au moins 100 matchs appris ET 100 jugés sur le circuit ;
  • ADOPTÉ DIRECTEMENT (comme le 05/11, décision de Lucas) si, sur le jugement : la log loss baisse d'au moins 0,001,
    a < 1, ET la pente réapprise sur le jugement est elle aussi < 1 (même sens sur les deux périodes) ;
  • retrait : fantomes_circuits.py, comme « documentation_faible » (deux semaines de suite pires) ;
  • les deux tranches ne se recouvrent pas : sous 500, la pente du 05/11 ; de 500 à 1 500, celle-ci.
CONTRÔLE (ne décide rien) : la même mesure sur nos vrais pronostics en direct (journal), avec a appris ci-dessus.
Usage : python simulateur/etude_documentation_moyenne.py /tmp/sackmann [racine]
"""
import datetime as dt
import glob
import gzip
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_documentation as EDO  # noqa: E402

BAS, HAUT = 500, 1500
COUPURE = EDO.COUPURE
MIN_N, MARGE = 100, 0.001
SORTIE = os.path.join(ICI, 'rapport_documentation_moyenne.json')


def dans_tranche(n):
    return BAS <= n < HAUT


def juger(A, J):
    """{appris, juges, pente, pente_jugement, log_loss_sans, log_loss_avec, gain, adopte, raison?}"""
    if len(A) < MIN_N or len(J) < MIN_N:
        return {'appris': len(A), 'juges': len(J), 'adopte': False, 'raison': 'trop peu de matchs dans la tranche'}
    a, aj = EDO.pente(A), EDO.pente(J)
    gain = EDO.ll(J) - EDO.ll(J, a)
    ok = gain >= MARGE and a < 1 and aj < 1
    out = {'appris': len(A), 'juges': len(J), 'pente': round(a, 3), 'pente_jugement': round(aj, 3),
           'log_loss_sans': round(EDO.ll(J), 5), 'log_loss_avec': round(EDO.ll(J, a), 5), 'gain': round(gain, 5),
           'favori_annonce_pct': round(100 * sum(max(p, 1 - p) for p, _ in J) / len(J), 1),
           'favori_gagnant_pct': round(100 * sum((p >= .5) == (y == 1) for p, y in J) / len(J), 1), 'adopte': ok}
    if not ok:
        out['raison'] = ('gain sous 0,001' if gain < MARGE else
                         'pente apprise ≥ 1 (pas trop sûr de lui)' if a >= 1 else 'pente du jugement ≥ 1 (pas le même sens)')
    return out


def lignes(archive, racine):
    """[(jour, circuit, p_algo, y)] des matchs de la tranche, documentation au jour du match."""
    import elo as E
    L = [json.loads(l) for l in gzip.open(os.path.join(ICI, 'pronostics_hors_echantillon.jsonl.gz'), 'rt', encoding='utf-8')]
    info = {}
    for f in glob.glob(os.path.join(racine, 'feuilles', '*.jsonl.gz')):
        for l in gzip.open(f, 'rt', encoding='utf-8'):
            e = json.loads(l)
            info[e['id']] = (E.cle(e['home']['nom']), E.cle(e['away']['nom']))
    Q = sorted([x for x in L if x['id'] in info and x.get('p_algo') is not None and x.get('gagnant') in ('home', 'away')],
               key=lambda x: x['jour'])
    C = EDO.Compteur(EDO.evenements(archive, racine))
    rows = []
    for x in Q:
        n = C.au(x['jour'])
        h, a = info[x['id']]
        if dans_tranche(min(n[h], n[a])):
            rows.append((x['jour'], x['circuit'], float(x['p_algo']), int(x['gagnant'] == 'home')))
    return rows


def controle_direct(archive, racine, pentes):
    """Nos pronostics en direct (dernier % figé avant le match) dans la tranche : log loss avec / sans la pente."""
    import controle_candidates as CC
    import elo as E
    X = CC.charger(racine)
    noms = {}
    for f in sorted(glob.glob(os.path.join(racine, 'simulateur', 'journal_pronostics', '2*.jsonl.gz'))):
        with gzip.open(f, 'rt', encoding='utf-8') as fh:
            for l in fh:
                try:
                    r = json.loads(l)
                except ValueError:
                    continue
                if r.get('uid') and r.get('home') and r.get('away'):
                    noms[(str(r.get('debut_utc') or r.get('debut'))[:10], round(float((r.get('combinaison') or {}).get('p_home') or -1), 4))] = (E.cle(r['home']), E.cle(r['away']))
    C = EDO.Compteur(EDO.evenements(archive, racine))
    out = {}
    for x in sorted(X, key=lambda x: x['debut']):
        k = noms.get((x['debut'], round(x['p'], 4)))
        if not k:
            continue
        n = C.au(x['debut'])
        if dans_tranche(min(n[k[0]], n[k[1]])):
            out.setdefault(x['circuit'], []).append((x['p'], x['y']))
    doc = {}
    for c, R in out.items():
        a = pentes.get(c)
        doc[c] = {'matchs': len(R), 'favori_annonce_pct': round(100 * sum(max(p, 1 - p) for p, _ in R) / len(R), 1),
                  'favori_gagnant_pct': round(100 * sum((p >= .5) == (y == 1) for p, y in R) / len(R), 1),
                  'pente_direct': round(EDO.pente(R), 3) if len(R) >= 30 else None,
                  'log_loss_sans': round(EDO.ll(R), 5),
                  'log_loss_avec': round(EDO.ll(R, a), 5) if a else None}
    return doc


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    rows = lignes(archive, racine)
    out = {}
    for c in ('ATP', 'WTA', 'CH'):
        A = [(p, y) for j, cc, p, y in rows if cc == c and j < COUPURE]
        J = [(p, y) for j, cc, p, y in rows if cc == c and j >= COUPURE]
        out[c] = juger(A, J)
    try:
        direct = controle_direct(archive, racine, {c: v['pente'] for c, v in out.items() if v.get('pente')})
    except Exception as e:  # noqa: BLE001 — le contrôle ne décide rien
        direct = {'erreur': f'{type(e).__name__}: {e}'}
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 368,
           'tranche_balles': [BAS, HAUT],
           'regle': ("a appris avant le 29/09 (≥ 100), jugé à partir du 29/09 (≥ 100) ; adopté directement si −0,001 "
                     "de log loss, a < 1 et pente du jugement < 1"),
           'circuits': out, 'controle_direct': direct}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
