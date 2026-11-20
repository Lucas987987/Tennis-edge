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
Relancé à chaque passage de « Pronostics du jour » et chaque semaine par
« Pronostic - test du modèle » ; écrit la décision dans simulateur/choix_simulation.json
(clé « combinaison_continue »), lue par pronostics_du_jour. Sans 30 nouveaux matchs
résolus depuis le dernier jugement, le champion reste inchangé et le run continue.

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
MIN_NOUVEAUX = 30
PART_JUGEMENT = 0.3
MARGE_LOG_LOSS = 0.001
CHOIX = os.path.join(ICI, 'choix_simulation.json')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def ll(L):
    return -sum(math.log(min(max(p, 1e-6), 1 - 1e-6)) for p in L) / len(L) if L else None


def brier(L):
    return sum((1-p)**2 for p in L) / len(L) if L else None


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


def decider(L, poids_archive, deja_juge_jusqua=None):
    n = len(L)
    out = {'n': n, 'min': MIN_MATCHS}
    if n < MIN_MATCHS:
        return dict(out, adopte=False, raison=f"en attente : {n} matchs joués avec les deux % (il en faut {MIN_MATCHS})")
    if deja_juge_jusqua:
        # Une période de jugement n'est jamais réutilisée pour retenter une adoption :
        # seuls les matchs arrivés depuis forment le nouveau test hors échantillon.
        appr = [r for r in L if r[0] <= deja_juge_jusqua]
        juge = [r for r in L if r[0] > deja_juge_jusqua]
        if len(juge) < MIN_NOUVEAUX:
            return dict(out, adopte=False, juge_jusqua=deja_juge_jusqua,
                        raison=f"en attente : {len(juge)} nouveaux matchs depuis le dernier jugement "
                               f"(il en faut {MIN_NOUVEAUX})")
    else:
        k = int(n * (1 - PART_JUGEMENT))
        appr, juge = L[:k], L[k:]
    w = ajuster(appr)
    P = {'elo': w[0], 'simulation': w[1]}
    p_new = [MS.melange(P, e, s_) for _, e, s_ in juge]
    p_arch = [MS.melange(poids_archive, e, s_) for _, e, s_ in juge] if poids_archive else []
    p_elo = [e for _, e, _ in juge]
    l_new, l_arch, l_elo = ll(p_new), ll(p_arch) if p_arch else None, ll(p_elo)
    b_new, b_arch, b_elo = brier(p_new), brier(p_arch) if p_arch else None, brier(p_elo)
    # Une amélioration infime ou un simple déplacement de variance ne suffit pas.
    ok = ((l_arch is not None and l_new <= l_arch - MARGE_LOG_LOSS and b_new <= b_arch)
          or (l_arch is None and l_new < l_elo and b_new <= b_elo))
    final = P
    if ok:
        wa = ajuster(L)
        final = {'elo': wa[0], 'simulation': wa[1]}
    return dict(out, adopte=bool(ok), poids={k_: round(v, 4) for k_, v in final.items()},
                poids_appris={k_: round(v, 4) for k_, v in P.items()},
                jugement={'n': len(juge), 'depuis': juge[0][0], 'jusqua': juge[-1][0],
                          'log_loss_continu': round(l_new, 5),
                          'log_loss_poids_archive': round(l_arch, 5) if l_arch is not None else None,
                          'log_loss_elo_seul': round(l_elo, 5),
                          'brier_continu': round(b_new, 5),
                          'brier_poids_archive': round(b_arch, 5) if b_arch is not None else None,
                          'brier_elo_seul': round(b_elo, 5),
                          'gain_log_loss': round(l_arch-l_new, 6) if l_arch is not None else None,
                          'marge_requise': MARGE_LOG_LOSS},
                juge_jusqua=juge[-1][0],
                raison=(f"sur les {len(juge)} matchs joués les plus récents : poids appris sur nos matchs {round(l_new, 4)} "
                        f"contre poids de l'archive {round(l_arch, 4) if l_arch is not None else '—'} (Elo seul {round(l_elo, 4)}) ; "
                        f"marge exigée {MARGE_LOG_LOSS} et Brier non dégradé"))


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
    precedent = choix.get('combinaison_continue') or {}
    suivi = choix.get('apprentissage_continu_suivi') or {}
    deja_juge = suivi.get('juge_jusqua') or (precedent.get('jugement') or {}).get('jusqua')
    d = decider(lignes(doc), pa, deja_juge)
    d['genere_le'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    choix['combinaison_continue'] = d
    if d.get('jugement'):
        choix['apprentissage_continu_suivi'] = {'juge_jusqua': d['jugement']['jusqua']}
    with open(CHOIX, 'w', encoding='utf-8') as f:
        json.dump(choix, f, ensure_ascii=False, indent=1)
    print(f"Apprentissage continu : {'ADOPTÉ' if d['adopte'] else 'non adopté'} — {d['raison']}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
