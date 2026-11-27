#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_format_tt.py — TENNIS DE TABLE : PEUT-ON PRÉVOIR LE FORMAT D'UN MATCH « INTERNATIONAL » (3 OU 4 MANCHES
GAGNANTES) ? (27/11/2026, paquet 502, Lucas : « fais le »).

Constat : la source n'annonce pas le format ; les pronostics supposent 3 manches gagnantes. C'est vrai pour toute la
Pologne (197 409 matchs sur 197 409 en 2025–2026), mais pas pour l'International : les tours finaux de certains
tournois (WTT Champions, Coupe du monde, Jeux olympiques…) se jouent en 4 manches gagnantes. Le format ne change
jamais le % ; il change le scénario (scores possibles).

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI. Matchs International terminés normalement, hors compétitions par
équipes, score complet en 3 ou 4 manches gagnantes. Mêmes périodes que les études 487, 494 et 496 : apprentissage
jusqu'au 30/09/2025, JUGEMENT une seule fois du 01/10/2025 au dernier jour.
  Témoin : la part des matchs en 4 manches gagnantes de l'apprentissage, la même pour tous (prédit « 3 »).
  Candidat : table (famille de tournoi × épreuve × tour) apprise sur l'apprentissage, repli sur (famille × épreuve)
             puis sur l'épreuve quand une case a moins de 10 matchs (format_tt.py) ; prédit « 4 » au-delà de 50 %.
  Retenu si, sur au moins 1 000 matchs jugés : la log loss du format réel baisse d'au moins 0,001 ET de 2 erreurs
  types, le taux de format juste n'est pas plus bas que celui du témoin, ET la table apprise sur le jugement fait
  aussi mieux sur l'apprentissage (même sens).
  Le tour vient de la ligne de l'historique (collecte, depuis le paquet 502) ou du rattrapage
  (historique/tennis_de_table/tours_international.json.gz) ; sans tour, la table se replie sur la famille.
Si retenu : table de production apprise sur TOUTES les données (même recette), lue par pronostics_tt.py.
Rapport : tennis_de_table/rapport_format_tt.json (comptes et parts, aucun nom de joueur). Rien d'autre ne change.
Usage : python tennis_de_table/etude_format_tt.py [racine]
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
import format_tt as FT  # noqa: E402
import pronostics_tt as PT  # noqa: E402

PAQUET = 502
SORTIE = FT.RAPPORT
DOSSIER = os.path.join('historique', 'tennis_de_table')
TOURS = os.path.join(DOSSIER, 'tours_international.json.gz')
JUGEMENT = dt.date(2025, 10, 1)
MIN_JUGES, MARGE, ERREURS_TYPES = 1000, 0.001, 2.0


def tours_rattrapes(racine):
    try:
        with gzip.open(os.path.join(racine, TOURS), 'rt', encoding='utf-8') as f:
            return json.load(f).get('tours') or {}
    except (OSError, ValueError):
        return {}


def exemples(racine='.'):
    """[(jour, tournoi, tour | None, format)] des matchs International utilisables, dans l'ordre des jours."""
    T = tours_rattrapes(racine)
    out = []
    for p in sorted(glob.glob(os.path.join(racine, DOSSIER, '20*', '20*.jsonl.gz'))):
        jour = os.path.basename(p)[:10]
        try:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                for l in f:
                    if not l.strip():
                        continue
                    r = json.loads(l)
                    if r.get('ligue') != 'International' or r.get('statut') != 'finished' or r.get('detail'):
                        continue
                    if PT.equipe(r):
                        continue
                    M = r.get('manches') or []
                    mh = sum(1 for x, y in M if x > y)
                    ma = sum(1 for x, y in M if y > x)
                    if mh == ma or max(mh, ma) not in (3, 4):
                        continue
                    out.append((jour, r.get('tournoi'), r.get('tour') or T.get(str(r.get('id'))), max(mh, ma)))
        except (OSError, ValueError):
            continue
    return out


def _ll(p, y4):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return -math.log(p if y4 else 1 - p)


def comparer(table, base, X):
    """Gain de log loss (témoin − candidat, positif = mieux) ± erreur type, et taux de format juste."""
    d, ok_c, ok_t = [], 0, 0
    for _, tournoi, tour, n in X:
        y4 = n == 4
        pc = FT.proba_4(table, tournoi, tour, a_priori=base)
        d.append(_ll(base, y4) - _ll(pc, y4))
        ok_c += int((pc > 0.5) == y4)
        ok_t += int((base > 0.5) == y4)
    if not d:
        return {'matchs': 0}
    g = sum(d) / len(d)
    et = math.sqrt(sum((x - g) ** 2 for x in d) / max(len(d) - 1, 1)) / math.sqrt(len(d))
    return {'matchs': len(d), 'gain': round(g, 5), 'erreur_type': round(et, 5),
            'format_juste_pct': round(100 * ok_c / len(d), 2), 'format_juste_temoin_pct': round(100 * ok_t / len(d), 2)}


def detail_4(table, base, X):
    """Matchs en 4 manches gagnantes : combien sont prévus ; et combien de « 4 » prévus à tort."""
    vrais4 = sum(1 for x in X if x[3] == 4)
    trouves = sum(1 for x in X if x[3] == 4 and FT.proba_4(table, x[1], x[2], base) > 0.5)
    faux4 = sum(1 for x in X if x[3] == 3 and FT.proba_4(table, x[1], x[2], base) > 0.5)
    return {'matchs_en_4': vrais4, 'prevus_en_4': trouves, 'en_4_a_tort': faux4}


def etudier(X, journal=print):
    A = [x for x in X if x[0] < JUGEMENT.isoformat()]
    B = [x for x in X if x[0] >= JUGEMENT.isoformat()]
    if len(A) < MIN_JUGES or len(B) < MIN_JUGES:
        journal(f'pas assez de matchs (apprentissage {len(A)}, jugement {len(B)})')
        return {'verdict': 'donnees_insuffisantes', 'retenu': False}
    TA, TB = FT.apprendre([x[1:] for x in A]), FT.apprendre([x[1:] for x in B])
    baseA = sum(1 for x in A if x[3] == 4) / len(A)
    baseB = sum(1 for x in B if x[3] == 4) / len(B)
    cj = comparer(TA, baseA, B)
    inv = comparer(TB, baseB, A)
    ok = bool(cj['matchs'] >= MIN_JUGES and cj['gain'] >= MARGE and cj['gain'] >= ERREURS_TYPES * cj['erreur_type']
              and cj['format_juste_pct'] >= cj['format_juste_temoin_pct'] and inv.get('gain', 0) > 0)
    couverture = {'apprentissage': round(100 * sum(1 for x in A if x[2]) / len(A), 1),
                  'jugement': round(100 * sum(1 for x in B if x[2]) / len(B), 1)}
    fam = {}
    for x in B:
        k = FT.famille(x[1]) + '|' + FT.epreuve(x[1])
        f = fam.setdefault(k, {'matchs': 0, 'en_4': 0})
        f['matchs'] += 1
        f['en_4'] += int(x[3] == 4)
    rep = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'paquet': PAQUET,
           'apprentissage': len(A), 'jugement': len(B), 'part_4_apprentissage_pct': round(100 * baseA, 2),
           'tour_connu_pct': couverture, 'jugement_candidat': cj, 'sens_inverse': inv.get('gain'),
           'detail_jugement': detail_4(TA, baseA, B), 'familles_jugement': dict(sorted(fam.items())),
           'retenu': ok, 'verdict': 'retenu' if ok else 'non_retenu',
           'table_production': FT.apprendre([x[1:] for x in X]) if ok else None}
    journal(f"format tennis de table (International) : apprentissage {len(A)}, jugement {len(B)}, "
            f"4 manches gagnantes {rep['part_4_apprentissage_pct']} % ; tour connu {couverture}")
    journal(f"  jugement : gain log loss {cj['gain']} ± {cj['erreur_type']}, format juste {cj['format_juste_pct']} % "
            f"(témoin {cj['format_juste_temoin_pct']} %), sens inverse {inv.get('gain')} → {rep['verdict']}")
    journal(f"  matchs en 4 au jugement : {rep['detail_jugement']}")
    for k, f in rep['familles_jugement'].items():
        journal(f"    {k} : {f['matchs']} matchs, {f['en_4']} en 4")
    return rep


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    rep = etudier(exemples(racine))
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
