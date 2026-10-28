#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sigma_circuit.py — la « forme du jour » (σ) propre à chaque circuit (28/10/2026).

La distribution exacte des scores tire, pour chaque match, une forme du jour de chaque joueur (écart-type σ en logit
du point de service), puis l'ancre sur la probabilité publiée : le VAINQUEUR ne change pas, seule la FORME du match
(2 ou 3 sets, tie-breaks, nombre de jeux) dépend de σ. σ = 0,15 venait d'un test tous circuits confondus.

Test du 28/10/2026 (8 634 matchs rejoués ; σ choisi par circuit sur la fenêtre d'apprentissage, jugé sur les 6
semaines de jugement, log-vraisemblance de la forme réelle : camp × tie-break × 3 sets × total de jeux) :
  ATP σ 0,15 (inchangé), WTA σ 0,15 (inchangé), Challenger σ 0,22 → gain total +0,0133, Challenger +0,0216, ATP et
  WTA 0 ; meilleur que la correction de forme par circuit (v3 : +0,0060, ATP −0,0195) et que la version circuit ×
  surface (+0,0036, ATP −0,026, WTA −0,005), toutes deux rejetées. Le Challenger a des journées plus contrastées :
  plus de matchs pliés en deux sets que ne le prévoyait σ 0,15 (c'était l'essentiel du « trop long »).

RÈGLE (fixée le 28/10/2026, avant le test ci-dessus) : chaque semaine (facteurs.py), σ de chaque circuit choisi dans
la GRILLE sur la fenêtre d'apprentissage (≤ 800 matchs par circuit, graine fixe), jugé sur la fenêtre de jugement
contre σ = 0,15 partout. Verdict de la semaine : gain total ≥ 0,001 ET aucun circuit qui perd plus de 0,001.
Adoption deux semaines de suite (stabilite.py, série « sigma_circuit »).
"""
import math
import random

# DÉCISION DE LUCAS LE 28/10/2026 : mis en production sans attendre les deux semaines, au vu du test (+0,0133, Challenger
# +0,0216, ATP et WTA inchangés). Valeurs en place jusqu'au premier jugement hebdomadaire ; ensuite la règle devient la
# SORTIE : retiré (σ 0,15 partout) si le jugement échoue deux semaines de suite.
DECISION = {'CH': 0.22}
GRILLE = (0.15, 0.18, 0.22, 0.26)    # 0,12 et moins : jamais choisis au test du 28/10
BASE = 0.15
CIRCUITS = ('ATP', 'WTA', 'CH')
MARGE = 0.001
MAX_APPR = 800       # par circuit (coût : une distribution exacte par match et par σ)


def sigma_de(sigmas, circuit):
    """σ d'un circuit (dictionnaire adopté), sinon la base."""
    return (sigmas or {}).get(circuit, BASE)


def _masses(ca, cb, sg):
    import distribution_exacte as DE
    import forme_scores as FS
    import match_simule as S
    import modele as Mo
    pv = Mo.match(S.p_service(ca), S.p_service(cb), 2)['victoire']
    return FS.masses(DE.distribution_forme(ca, cb, 2, sg, p_victoire=pv))


def _un(args):
    ca, cb, grille = args
    return {sg: _masses(ca, cb, sg) for sg in grille}


def jeu(lignes, scores_reels, max_par_circuit=None, graine=7, grille=GRILLE):
    """[(circuit, {σ: masses}, observation)] pour les matchs au meilleur des 3 avec score réel complet."""
    import forme_scores as FS
    L = [x for x in lignes if x.get('bo') == 3 and scores_reels.get(x.get('id')) and x.get('circuit') in CIRCUITS]
    if max_par_circuit:
        rng, garde = random.Random(graine), []
        for c in CIRCUITS:
            Lc = [x for x in L if x['circuit'] == c]
            garde += rng.sample(Lc, max_par_circuit) if len(Lc) > max_par_circuit else Lc
        L = garde
    taches = [(x['srv'][0]['tx'], x['srv'][1]['tx'], grille) for x in L]
    try:                                            # en parallèle sur tous les cœurs du runner
        import multiprocessing as mp
        import os
        with mp.Pool(max(1, os.cpu_count() or 1)) as P:
            M = P.map(_un, taches, chunksize=40)
    except Exception:  # noqa: BLE001
        M = [_un(t) for t in taches]
    return [(x['circuit'], m, FS.observation(scores_reels[x['id']])) for x, m in zip(L, M)]


def _ll(m, o):
    """-log P(forme observée | camp observé) : le vainqueur est le même pour tous les σ (ancrage)."""
    cote = sum(v for k, v in m.items() if k[0] == o[0])
    return -math.log(max(m.get(o, 0.0) / cote, 1e-12)) if cote else 0.0


def log_vrais(D, sigmas):
    return sum(_ll(M[sigma_de(sigmas, c)], o) for c, M, o in D) / len(D) if D else None


def choisir(D):
    """{circuit: σ} qui maximise la vraisemblance de la forme sur D (apprentissage)."""
    out = {}
    for c in CIRCUITS:
        Dc = [x for x in D if x[0] == c]
        if Dc:
            sc = {sg: sum(_ll(M[sg], o) for _, M, o in Dc) for sg in Dc[0][1]}
            out[c] = min(sc, key=sc.get)
    return out


def verdict(gain, par_circuit):
    pire = min((v['gain'] for v in (par_circuit or {}).values()), default=0.0)
    return bool(gain is not None and gain >= MARGE and pire >= -MARGE)


def juger(appr, juge, scores_reels):
    """Rapport et verdict BRUT de la règle fixée (la stabilité est appliquée par l'appelant)."""
    Da = jeu(appr, scores_reels, MAX_APPR)
    Dj = jeu(juge, scores_reels)
    sig = choisir(Da)
    l0, l1 = log_vrais(Dj, {}), log_vrais(Dj, sig)
    gain = (l0 - l1) if l0 is not None and l1 is not None else None
    par = {}
    for c in CIRCUITS:
        D_ = [x for x in Dj if x[0] == c]
        if D_:
            par[c] = {'n': len(D_), 'sigma': sig.get(c, BASE), 'gain': round(log_vrais(D_, {}) - log_vrais(D_, sig), 6)}
    return {'sigmas': sig, 'apprentissage': len(Da), 'jugement': len(Dj), 'par_circuit': par,
            'gain': round(gain, 6) if gain is not None else None, 'adopte': verdict(gain, par),
            'regle': ("σ de la forme du jour choisi par circuit sur l'apprentissage ; jugé contre 0,15 partout : gain total "
                      "≥ 0,001 et aucun circuit qui perd plus de 0,001 ; deux semaines de suite (série sigma_circuit)")}
