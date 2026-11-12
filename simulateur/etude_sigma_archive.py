#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_sigma_archive.py — la « forme du jour » σ rejouée sur l'archive, circuit par circuit (12/11/2026, audit, paquet 243)

LE CONSTAT (audit, section 6, « forme_du_jour »). σ règle la FORME du match (2 ou 3 sets, écart de jeux), pas le
vainqueur : la distribution est ancrée sur le % publié. σ est jugé chaque lundi sur nos matchs suivis
(sigma_circuit.py : quelques centaines de matchs par circuit). Sur l'archive WTA 2018–2022, avec un modèle simplifié,
σ = 0,15 donnait un peu trop de matchs en trois sets (36,1 % contre 33,8 %) et un peu trop peu de larges victoires.

RÈGLE ÉCRITE À L'AUDIT (rapport_audit.json, constat « forme_du_jour », paquet 227) :
  grille σ de 0,15 à 0,22 par pas de 0,01, circuit par circuit, avec les vrais profils ; choisi sur 2018–2022, jugé
  sur 2023 → : au moins 0,005 de log loss sur l'écart de jeux exact, sans dégrader le score en sets de plus de 0,002,
  sur au moins 1 000 matchs ; la variante asymétrique est jugée dans la même étude, avec la même règle.
PRÉCISIONS ÉCRITES LE 12/11/2026, AVANT DE LANCER LE REJEU :
  - matchs : archive Sackmann, au meilleur des 3 sets, score complet, sans abandon, niveau 'D' exclu, deux joueurs à
    au moins 10 matchs d'Elo ; un match sur PAS[circuit], choisi par son numéro ; apprentissage 2019–2022 (2018 sert à
    constituer les profils), jugement 2023 → juin 2026 ;
  - profils comme en production pour la distribution ancrée : ajustement.ajuster chaque trimestre, amplification des
    profils en place (paquet 240) ; niveau ancré sur l'Elo de production corrigé des pentes en place ;
  - distribution exacte (distribution_exacte.distribution_forme), ancrée sur ce niveau : le vainqueur ne dépend pas de σ ;
  - « écart de jeux exact » = jeux du vainqueur − jeux du perdant ; « score en sets » = 2-0 ou 2-1 du vainqueur ;
    log loss = − log de la probabilité de ce qui s'est passé ;
  - référence : σ EN PLACE aujourd'hui (pronostics_du_jour.charger_sigma_circuit : ATP 0,15, WTA 0,15, Challenger 0,18) ;
  - σ choisi sur l'apprentissage = log loss de l'écart de jeux la plus basse de la grille ;
  - VARIANTE ASYMÉTRIQUE : les bons jours du favori n'ont pas la même ampleur que ses mauvais jours :
    écart de forme σ·(1 + κ)·z quand la forme penche vers le favori (z > 0), σ·(1 − κ)·z sinon, au σ choisi,
    κ ∈ {−0,2 ; −0,1 ; 0 ; +0,1 ; +0,2} choisi sur l'apprentissage ; ancrage refait avec ces nœuds ;
  - RETENU pour un circuit si, sur le jugement (≥ 1 000 matchs), l'écart de jeux gagne au moins 0,005 contre σ en place
    et le score en sets ne perd pas plus de 0,002 ; sinon σ en place reste ;
  - si un σ retenu est au bord de la grille (0,15 ou 0,22), il est signalé « à surveiller » : la grille a été écrite
    avant, elle n'est pas élargie après avoir vu le résultat.
Rien ne change le % de victoire : seule la forme du match (scores probables, 3 sets, écart de jeux) change.

Usage : python simulateur/etude_sigma_archive.py /tmp/sackmann . [--entrees cache.pkl.gz] [--processus 2]
"""
import datetime as dt
import gzip
import json
import math
import os
import pickle
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

DEBUT, COUPURE, FIN = dt.date(2019, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
PAS = {'ATP': 5, 'WTA': 5, 'CH': 11}
GRILLE = tuple(round(0.15 + 0.01 * i, 2) for i in range(8))
KAPPAS = (-0.2, -0.1, 0.0, 0.1, 0.2)
GAIN_MIN, PERTE_SETS_MAX, MIN_JUGE = 0.005, 0.002, 1000
SORTIE = os.path.join(ICI, 'rapport_sigma_archive.json')


def entrees(archive, racine, journal=True):
    """[(jour, circuit, cG, cP, p vainqueur, sets)] : les matchs rejoués, profils du moment, vus du vainqueur."""
    import ajustement as AJ
    import donnees as DN
    import elo as E
    import etude_outsiders as EO
    import etude_signaux_reappris as ER
    import match_simule as MS
    import pronostics_du_jour as PJ
    with open(os.path.join(racine, 'simulateur', 'choix_simulation.json'), encoding='utf-8') as f:
        ch = json.load(f)
    n0, n0c = float(ch.get('n0') or AJ.N0), ch.get('n0_par_composante') or None
    amplif = PJ.charger_amplification_profils(racine) or {}
    fmt, gc = ER.pentes_en_place(racine)
    Mt = DN.charger(archive, 2018)
    Mt.sort(key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    k = E.cle
    el, bas = E.de_production(racine)

    def maj(m):
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            return
        if bas and m['circuit'] in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        el.maj(g, p, m['surface'], m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)

    for m in sorted((x for x in DN.charger(archive, 2012) if Mt and x['date'] < Mt[0]['date']),
                    key=lambda x: (x['date'], x.get('tour', 0), x.get('num', 0))):
        maj(m)
    T = sorted(dt.date(y, mo, 1) for y in range(2018, FIN.year + 1) for mo in (1, 4, 7, 10)
               if dt.date(2018, 10, 1) <= dt.date(y, mo, 1) < FIN)
    out, A, ti = [], None, -1
    for m in Mt:
        d = m['date']
        while ti + 1 < len(T) and d >= T[ti + 1]:
            ti += 1
            A = AJ.ajuster(Mt, T[ti], k, n0=n0, n0_par_composante=n0c)
            if journal:
                print(f"ajustement au {T[ti]} ({len(out)} matchs)", flush=True)
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m['surface']
        if bas and c in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        sets = m.get('sets') or []
        if (A is not None and c in PAS and DEBUT <= d < FIN and m.get('bo') == 3 and m.get('complet') and not m.get('abandon')
                and m.get('niveau') != 'D' and 2 <= len(sets) <= 3 and sum(a > b for a, b in sets) == 2
                and int(m.get('num') or 0) % PAS[c] == 0 and el.matchs(g) >= 10 and el.matchs(p) >= 10):
            pg = EO._sg(ER.pente_du_match(m, fmt, gc) * EO._lg(el.proba(g, p, s)))
            pg = min(max(pg, 0.02), 0.98)
            cG, cP = MS.composantes_ajustees(A, g, p, c, s), MS.composantes_ajustees(A, p, g, c, s)
            if amplif.get(c):
                moy = MS.borner(A.taux('__moyen__', '__moyen__', c, s))
                cG, cP = MS.amplifier_composantes(cG, moy, amplif[c]), MS.amplifier_composantes(cP, moy, amplif[c])
            out.append((d.isoformat(), c, dict(cG), dict(cP), pg, [tuple(x) for x in sets]))
        maj(m)
    return out


def noeuds(sigma, kappa, favori_a):
    """[(écart de forme en logit pour A, poids)] ; z > 0 : la forme penche vers le favori."""
    import modele as M
    out = []
    for z, w in zip(M._Z, M._W):
        zf = z if favori_a else -z                              # z vu du favori
        amp = sigma * (1 + kappa if zf > 0 else 1 - kappa)
        out.append((amp * zf * (1 if favori_a else -1), w))
    return out


def distribution(cA, cB, p_victoire, sigma, kappa=0.0):
    """Comme distribution_exacte.distribution_forme (au meilleur des 3), nœuds éventuellement asymétriques."""
    import distribution_exacte as DE
    import match_simule as MS
    if kappa == 0.0:
        return DE.distribution_forme(cA, cB, 2, sigma, p_victoire=p_victoire)
    N = noeuds(sigma, kappa, p_victoire >= 0.5)
    la, lb = MS._lg(MS.p_service(cA)), MS._lg(MS.p_service(cB))
    dA, dB = cA.get('bp', 0.0), cB.get('bp', 0.0)
    lo, hi = -6.0, 6.0
    for _ in range(40):
        dd = (lo + hi) / 2
        v = sum(w * MS.victoire(MS._sg(la + dd + dz), MS._sg(lb - dd - dz), 2, None, dA, dB) for dz, w in N)
        lo, hi = (dd, hi) if v < p_victoire else (lo, dd)
    dd = (lo + hi) / 2
    a, b = MS._sg(la + dd), MS._sg(lb - dd)
    out = {}
    for dz, w in N:
        ca, cb = MS.ajuster(cA, MS._sg(MS._lg(a) + dz)), MS.ajuster(cB, MS._sg(MS._lg(b) - dz))
        for score, pr in DE.distribution_match(MS.p_service(ca), MS.p_service(cb), 2, None, ca.get('bp', 0.0),
                                               cb.get('bp', 0.0)).items():
            out[score] = out.get(score, 0.0) + w * pr
    return out


def mesures(dist, sets):
    """(− log P(écart de jeux observé), − log P(score en sets observé)), vus du vainqueur (A)."""
    ecart = sum(a - b for a, b in sets)
    n3 = len(sets) == 3
    pe = sum(p for s, p in dist.items() if sum(a - b for a, b in s) == ecart)
    ps = sum(p for s, p in dist.items() if (len(s) == 3) == n3 and sum(a > b for a, b in s) == 2)
    return -math.log(max(pe, 1e-12)), -math.log(max(ps, 1e-12))


def _calcul(args):
    e, combos = args
    _, _, cG, cP, pg, sets = e
    return {f"{sg}|{k}": mesures(distribution(cG, cP, pg, sg, k), sets) for sg, k in combos}


def calculer(E, combos, processus=2):
    from multiprocessing import Pool
    with Pool(processus) as pool:
        return pool.map(_calcul, [(e, combos) for e in E], chunksize=20)


def _moy(L):
    return sum(L) / len(L) if L else None


def main(argv):
    import pronostics_du_jour as PJ
    args = [a for a in argv[1:] if not a.startswith('--')]
    opt = {a.split('=')[0]: a.split('=', 1)[1] for a in argv[1:] if a.startswith('--') and '=' in a}
    archive, racine = (args + ['/tmp/sackmann', os.path.join(ICI, '..')])[:2]
    proc = int(opt.get('--processus', 2))
    cache = opt.get('--entrees')
    if cache and os.path.exists(cache):
        E = pickle.load(gzip.open(cache, 'rb'))
    else:
        E = entrees(archive, racine)
        if cache:
            pickle.dump(E, gzip.open(cache, 'wb'))
    en_place = {c: (PJ.charger_sigma_circuit(racine) or {}).get(c, PJ.SIGMA) for c in PAS}
    print(f"{len(E)} matchs ; σ en place {en_place}", flush=True)
    # 1. grille symétrique, tous les matchs
    combos = [(sg, 0.0) for sg in sorted(set(GRILLE) | set(en_place.values()))]
    R = calculer(E, combos, proc)
    rap = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 243,
           'regle': ("grille σ 0,15 → 0,22 (pas 0,01) et variante asymétrique (κ −0,2 → +0,2) choisies sur 2019–2022, "
                     "jugées sur 2023 → juin 2026 contre σ en place : retenu si l'écart de jeux exact gagne au moins 0,005 "
                     "et le score en sets ne perd pas plus de 0,002, sur au moins 1 000 matchs"),
           'pas': PAS, 'grille': GRILLE, 'kappas': KAPPAS, 'sigma_en_place': en_place, 'circuits': {}}
    choix = {}
    for c in PAS:
        ix_a = [i for i, e in enumerate(E) if e[1] == c and e[0] < COUPURE.isoformat()]
        ll = {sg: _moy([R[i][f"{sg}|0.0"][0] for i in ix_a]) for sg in GRILLE}
        choix[c] = min(GRILLE, key=lambda s: ll[s])
    # 2. variante asymétrique au σ choisi
    combos2 = sorted({(choix[c], k) for c in PAS for k in KAPPAS if k != 0.0})
    R2 = calculer(E, combos2, proc)
    for r, r2 in zip(R, R2):
        r.update(r2)
    for c in PAS:
        ia = [i for i, e in enumerate(E) if e[1] == c and e[0] < COUPURE.isoformat()]
        ij = [i for i, e in enumerate(E) if e[1] == c and e[0] >= COUPURE.isoformat()]
        sg = choix[c]
        f = lambda I, cle, j: _moy([R[i][cle][j] for i in I])
        ka = min(KAPPAS, key=lambda k: f(ia, f"{sg}|{k}", 0))
        ref = f"{en_place[c]}|0.0"
        def verdict(cle):
            ge, gs = f(ij, ref, 0) - f(ij, cle, 0), f(ij, ref, 1) - f(ij, cle, 1)
            return {'gain_ecart_de_jeux': round(ge, 5), 'gain_score_en_sets': round(gs, 5),
                    'retenu': len(ij) >= MIN_JUGE and ge >= GAIN_MIN and gs >= -PERTE_SETS_MAX,
                    'meme_sens_en_apprentissage': (f(ia, ref, 0) - f(ia, cle, 0)) > 0}
        part3 = lambda I: round(100 * sum(len(E[i][5]) == 3 for i in I) / len(I), 1) if I else None
        d = {'matchs_apprentissage': len(ia), 'matchs_jugement': len(ij),
             'grille_apprentissage': {str(s): round(f(ia, f"{s}|0.0", 0), 5) for s in GRILLE},
             'grille_jugement': {str(s): round(f(ij, f"{s}|0.0", 0), 5) for s in GRILLE},
             'sigma_choisi': sg, 'au_bord_de_la_grille': sg in (GRILLE[0], GRILLE[-1]),
             'kappa_choisi': ka,
             'kappas_apprentissage': {str(k): round(f(ia, f"{sg}|{k}", 0), 5) for k in KAPPAS},
             'trois_sets_reel_pct_jugement': part3(ij),
             'symetrique': verdict(f"{sg}|0.0"), 'asymetrique': verdict(f"{sg}|{ka}")}
        d['decision'] = ('asymétrique' if d['asymetrique']['retenu'] and ka != 0.0
                         and d['asymetrique']['gain_ecart_de_jeux'] > d['symetrique']['gain_ecart_de_jeux']
                         else 'symétrique' if d['symetrique']['retenu'] else 'σ en place')
        rap['circuits'][c] = d
        print(c, json.dumps({k: d[k] for k in ('sigma_choisi', 'kappa_choisi', 'symetrique', 'asymetrique', 'decision')},
                            ensure_ascii=False), flush=True)
    with open(SORTIE, 'w', encoding='utf-8') as fh:
        json.dump(rap, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
