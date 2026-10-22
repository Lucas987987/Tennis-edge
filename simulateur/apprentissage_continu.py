#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apprentissage_continu.py — l'algorithme apprend de SES PROPRES pronostics (22/10/2026).

Chaque match joué est enregistré avec la prédiction faite AVANT le match (live/pronostics_resultats.json,
livraison 41). Une fois assez de matchs joués, on ré-apprend le mélange « simulation + Elo » sur ces
matchs réels — la simulation y tourne avec ses facteurs du match, ce que le test sur l'archive ne voit pas :
  — apprentissage : les matchs joués les plus anciens (70 %) ; jugement : les plus récents (30 %) ;
  — RÈGLE FIXÉE D'AVANCE : les poids appris sur nos matchs remplacent ceux de l'archive s'ils trouvent
    mieux le vainqueur (log loss plus basse) sur les matchs récents ; il faut au moins MIN_MATCHS matchs
    joués avec les deux % (simulation et Elo).
Relancé chaque semaine par « Pronostic - test du modèle » ; écrit la décision dans
simulateur/choix_simulation.json (clé « combinaison_continue »), lue par pronostics_du_jour.

Usage : python simulateur/apprentissage_continu.py [racine]
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import match_simule as MS  # noqa: E402

MIN_MATCHS = 400
PART_JUGEMENT = 0.3
CHOIX = os.path.join(ICI, 'choix_simulation.json')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def ll(L):
    return -sum(math.log(min(max(p, 1e-6), 1 - 1e-6)) for p in L) / len(L) if L else None


def lignes(doc):
    """[(debut, p_elo du vrai vainqueur, p_sim du vrai vainqueur)] depuis pronostics_resultats.json."""
    out = []
    for m in (doc or {}).get('matchs') or []:
        if (m.get('reel') or {}).get('interrompu'):          # abandon / forfait : n'apprend rien sur le pronostic
            continue
        pr = m.get('premier') or {}
        e, s_ = pr.get('stats'), pr.get('simulation')
        if e and s_ and e.get('proba_du_vainqueur') is not None and s_.get('proba_du_vainqueur') is not None:
            out.append((m['debut'], e['proba_du_vainqueur'], s_['proba_du_vainqueur']))
    return sorted(out)


def ajuster(L, ridge=1.0, tours=30):
    """Mêmes poids que backtest_match_simule.ajuster_poids (logistique symétrique sans constante)."""
    import backtest_match_simule as B
    return B.ajuster_poids([[_lg(e), _lg(s_)] for _, e, s_ in L], ridge=ridge, tours=tours)


def decider(L, poids_archive):
    n = len(L)
    out = {'n': n, 'min': MIN_MATCHS}
    if n < MIN_MATCHS:
        return dict(out, adopte=False, raison=f"en attente : {n} matchs joués avec les deux % (il en faut {MIN_MATCHS})")
    k = int(n * (1 - PART_JUGEMENT))
    appr, juge = L[:k], L[k:]
    w = ajuster(appr)
    P = {'elo': w[0], 'simulation': w[1]}
    l_new = ll([MS.melange(P, e, s_) for _, e, s_ in juge])
    l_arch = ll([MS.melange(poids_archive, e, s_) for _, e, s_ in juge]) if poids_archive else None
    l_elo = ll([e for _, e, _ in juge])
    ok = l_arch is None or l_new < l_arch
    final = P
    if ok:
        wa = ajuster(L)
        final = {'elo': wa[0], 'simulation': wa[1]}
    return dict(out, adopte=bool(ok), poids={k_: round(v, 4) for k_, v in final.items()},
                poids_appris={k_: round(v, 4) for k_, v in P.items()},
                jugement={'n': len(juge), 'depuis': juge[0][0], 'log_loss_continu': round(l_new, 5),
                          'log_loss_poids_archive': round(l_arch, 5) if l_arch is not None else None,
                          'log_loss_elo_seul': round(l_elo, 5)},
                raison=(f"sur les {len(juge)} matchs joués les plus récents : poids appris sur nos matchs {round(l_new, 4)} "
                        f"contre poids de l'archive {round(l_arch, 4) if l_arch is not None else '—'} (Elo seul {round(l_elo, 4)})"))


def main(argv):
    racine = argv[1] if len(argv) > 1 else os.path.join(ICI, '..')
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        doc = {}
    try:
        with open(CHOIX, encoding='utf-8') as f:
            choix = json.load(f)
    except (OSError, ValueError):
        choix = {}
    pa = ((choix.get('combinaison') or {}).get('poids')) if (choix.get('combinaison') or {}).get('adopte') else None
    d = decider(lignes(doc), pa)
    d['genere_le'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    choix['combinaison_continue'] = d
    with open(CHOIX, 'w', encoding='utf-8') as f:
        json.dump(choix, f, ensure_ascii=False, indent=1)
    print(f"Apprentissage continu : {'ADOPTÉ' if d['adopte'] else 'non adopté'} — {d['raison']}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
