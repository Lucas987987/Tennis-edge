#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_resultats.py — la simulation apprend de qui a gagné, version CORRIGÉE (22/10/2026).

LE PROBLÈME IDENTIFIÉ (livraison 46). La couche « résultats » apprenait de TOUS les matchs terminés.
Or le modèle des points (ajustement aux adversaires) est recalculé chaque mois — et toutes les
6 heures en production — sur les statistiques de ces MÊMES matchs : un joueur qui gagne voit déjà
ses taux du point monter. La couche le comptait une deuxième fois. Résultat : utile en 2024, nuisible
en 2025 (log loss 0,6238 → 0,6326).

LA CORRECTION. La couche n'apprend QUE des matchs que le modèle des points ne verra jamais : ceux
sans feuille de statistiques (score seul — ITF, qualifications, Challenger anciens…). Rien n'est
compté deux fois, et c'est exactement ce que la production peut faire.

RÈGLE FIXÉE AVANT DE VOIR LE RÉSULTAT (22/10/2026, 22 h 50) :
  — K (force d'apprentissage) choisi sur 2024 : plus petite log loss du vainqueur, simulation pure
    (σ = 0), tous circuits, matchs avec feuille ;
  — jugé sur une période JAMAIS utilisée pour juger quoi que ce soit : les feuilles TennisApi depuis
    le 1er juin 2026 (2025 a déjà servi à rejeter la première version) ;
  — adopté si la log loss du vainqueur y est plus basse qu'avec la simulation sans couche.
Pour mémoire, la version d'origine (tous les matchs) est mesurée sur la même période : elle ne peut
pas être adoptée, elle sert à vérifier le diagnostic.

VERDICT DU 22/10/2026 (données réelles) : NON ADOPTÉE. K = 0,015 choisi sur 2024 (où même lui fait
déjà moins bien que sans couche : 0,6401 contre 0,6323) ; sur les 9 041 matchs depuis le 01/06/2026 :
0,6491 avec la couche contre 0,6295 sans. Les matchs sans feuille opposent surtout des joueurs que le
modèle des points ne connaît pas : chaque victoire y passe pour une surprise et gonfle le niveau.
Script gardé pour mémoire, PAS lancé chaque semaine : rejuger la même idée sur la même période neuve,
semaine après semaine, finirait par l'adopter par hasard.
Écrit choix_simulation.json → « couche_resultats » ; lu par profils_service.py (export des niveaux)
et donc par pronostics_du_jour.py.
Usage : python simulateur/etude_resultats.py <dossier sackmann> [racine]
"""
import datetime as dt
import json
import math
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import ajustement as AJ  # noqa: E402
import donnees  # noqa: E402
import elo as E  # noqa: E402
import feuilles as FE  # noqa: E402
import match_simule as S  # noqa: E402
import resultats_points as RP  # noqa: E402

CHOIX = os.path.join(ICI, 'choix_simulation.json')
SORTIE = os.path.join(ICI, 'etude_resultats.json')
DEBUT = dt.date(2023, 1, 1)                 # la couche apprend à partir d'ici
CHOIX_K = (dt.date(2024, 1, 1), dt.date(2025, 1, 1))
DEBUT_JUGE = dt.date(2026, 6, 1)            # période neuve : feuilles TennisApi
GRILLE_K = (0.015, 0.04, 0.1)
K_ORIGINE = 0.015                           # la version de la livraison 46 (pour mémoire)


def ll(L):
    return -sum(math.log(min(max(p, 1e-6), 1 - 1e-6)) for p in L) / len(L) if L else None


def reussite(L):
    return round(100 * sum(p > 0.5 for p in L) / len(L), 1) if L else None


def decider(apprendre, juger):
    """apprendre / juger : {variante: [proba donnée au vrai vainqueur]} ; variante 'sans', 'K=…', 'origine'."""
    ks = [k for k in apprendre if k.startswith('K=')]
    if not ks or not apprendre.get('sans') or not juger.get('sans'):
        return {'adopte': False, 'raison': 'pas assez de matchs'}
    k = min(ks, key=lambda v: ll(apprendre[v]))
    l_sans, l_k = ll(juger['sans']), ll(juger[k])
    ok = l_k < l_sans
    out = {'adopte': bool(ok), 'K': float(k[2:]), 'mode': 'scores_seuls',
           'choix_2024': {v: round(ll(L), 5) for v, L in apprendre.items()},
           'jugement': {v: {'n': len(L), 'log_loss': round(ll(L), 5), 'reussite_pct': reussite(L)} for v, L in juger.items()},
           'raison': (f"K = {k[2:]} choisi sur 2024 ; depuis le {DEBUT_JUGE.strftime('%d/%m/%Y')} ({len(juger[k])} matchs) : "
                      f"log loss {round(l_k, 4)} avec la couche contre {round(l_sans, 4)} sans"
                      + (f" (version d'origine, tous les matchs : {round(ll(juger['origine']), 4)})" if juger.get('origine') else '')
                      + (' — ADOPTÉE' if ok else ' — non adoptée'))}
    return out


def main(argv):
    dossier = argv[1] if len(argv) > 1 else 'sackmann'
    racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    t0 = time.time()
    M = donnees.charger(dossier, 2016)
    fin_sack = max(m['date'] for m in M)
    F = [m for m in FE.charger(racine) if m['date'] > fin_sack]
    M = sorted(M + F, key=lambda m: m['date'])
    print(f"Matchs : {len(M)} (dont {len(F)} des feuilles TennisApi après le {fin_sack})", flush=True)
    try:
        with open(CHOIX, encoding='utf-8') as f:
            choix = json.load(f)
    except (OSError, ValueError):
        choix = {}
    n0 = float(choix.get('n0') or 300.0)
    dyn = AJ.lire_dynamique(choix)
    couches = {f"K={k:g}": RP.CoucheResultats(k) for k in GRILLE_K}
    origine = RP.CoucheResultats(K_ORIGINE)
    apprendre = {v: [] for v in ['sans', *couches]}
    juger = {v: [] for v in ['sans', *couches, 'origine']}
    adj, mois = None, None
    for m in M:
        if m['date'] < DEBUT or not m.get('complet') or not m.get('sets'):
            continue
        debut_mois = m['date'].replace(day=1)
        if mois != debut_mois:                                 # point-in-time : tournois finis avant le 1er du mois
            t1 = time.time()
            adj = AJ.ajuster_choisi(M, debut_mois, E.cle, n0=n0, dyn=dyn, depart=adj, tours=6 if adj is None else 2)
            mois = debut_mois
            print(f"  modèle des points au {debut_mois} ({round(time.time() - t1)} s)", flush=True)
        g, p = E.cle(m['nom_g']), E.cle(m['nom_p'])
        sg = 3 if m.get('bo') == 5 else 2
        tg = S.borner(adj.taux(g, p, m['circuit'], m['surface']))
        tp = S.borner(adj.taux(p, g, m['circuit'], m['surface']))
        if m.get('detail'):                                    # match avec feuille : on PRÉDIT
            fen = (apprendre if CHOIX_K[0] <= m['date'] < CHOIX_K[1] else juger if m['date'] >= DEBUT_JUGE else None)
            if fen is not None:
                fen['sans'].append(S.victoire_pure(tg, tp, sg, 0.0))
                for v, C in couches.items():
                    fen[v].append(S.victoire_pure(C.decaler(tg, g, p), C.decaler(tp, p, g), sg, 0.0))
                if fen is juger:
                    juger['origine'].append(S.victoire_pure(origine.decaler(tg, g, p), origine.decaler(tp, p, g), sg, 0.0))
        else:                                                  # score seul : le modèle des points ne le verra jamais
            for C in couches.values():
                C.apprendre(g, p, tg, tp, sg)
        origine.apprendre(g, p, tg, tp, sg)                    # version d'origine : tous les matchs (double compte)
    d = decider(apprendre, juger)
    d['genere_le'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    d['regle'] = ("K choisi sur 2024, jugé sur les feuilles depuis le 01/06/2026 (période jamais utilisée), adopté si la "
                  "log loss du vainqueur y baisse ; la couche n'apprend que des matchs sans feuille (aucun double compte).")
    choix['couche_resultats'] = {k: d.get(k) for k in ('adopte', 'K', 'mode', 'raison', 'genere_le')}
    with open(CHOIX, 'w', encoding='utf-8') as f:
        json.dump(choix, f, ensure_ascii=False, indent=1)
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print(f"\nCouche « résultats » corrigée : {d['raison'] if 'raison' in d else d} ({round(time.time() - t0)} s)")
    for v, x in (d.get('jugement') or {}).items():
        print(f"  {v:<10} n {x['n']} · log loss {x['log_loss']} · réussite {x['reussite_pct']} %")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
