#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_profils_amplification.py — les profils service / retour sont-ils trop ramenés vers la moyenne ?
(12/11/2026, audit, paquet 240)

LE CONSTAT (audit, section 9). Les profils (ajustement.py : un effet « service » et un effet « retour » par joueur et
par composante du point, ramenés vers 0 par un prior n0) prévoient les matchs suivants un peu trop prudemment : la
pente du réel contre le prévu vaut 1,05 à 1,22 selon le circuit et la composante (5 photos de 2019–2022). Les gros
serveurs sont écrasés : moins d'aces, moins de jeux de service tenus que la réalité.

LA CORRECTION ÉTUDIÉE : une amplification par circuit et par composante,
    taux' = σ(μ + k · (logit taux − μ)),   μ = moyenne du circuit sur la surface,
appliquée au profil de production (match_simule.composantes_ajustees), donc avant la couche « jeux ».

Rejeu : archive Sackmann, profils ajustés comme en production (ajustement.ajuster, mêmes n0) au premier jour de
chaque trimestre de 2019 à avril 2026 ; chaque photo prévoit les matchs du trimestre qui suit. Une ligne = un joueur
au service dans un match et une composante : essais, réussites, logit prévu, moyenne du circuit.

RÈGLE ÉCRITE À L'AUDIT (rapport_audit.json, constat « profils », paquet 227) :
  une amplification par composante (aces, 1re gagnée, 2e gagnée), choisie sur 2018–2022, jugée sur 2023 → : meilleure
  vraisemblance des points sur les deux périodes, sans dégrader le vainqueur de plus de 0,001.
PRÉCISIONS ÉCRITES LE 12/11/2026, AVANT DE LANCER L'ÉTUDE :
  - les cinq composantes (1re dedans, ace, 1re gagnée, double faute, 2e jouée gagnée), par circuit (ATP, WTA, CH) ;
  - k appris sur 2019–2022 (2018 sert aux profils) par maximum de vraisemblance binomiale ;
  - une case est RETENUE si, sur 2023 → juin 2026 : au moins 1 000 lignes, gain de log-vraisemblance par point
    positif, k jugé du même côté de 1 que k appris ; le gain sur 2019–2022 est positif par construction ;
  - « sans dégrader le vainqueur » : contrôle à part (etude_statistiques_annoncees.py rejoué avec et sans les
    amplifications retenues, sur un match sur trois de la période jugée) — le % de victoire du rejeu ne doit pas
    perdre plus de 0,001 de log loss ; sinon rien n'entre en production.

Usage : python simulateur/etude_profils_amplification.py /tmp/sackmann . [--lignes cache.json.gz]
"""
import datetime as dt
import gzip
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

DEBUT, COUPURE, FIN = dt.date(2019, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
CIRCUITS = ('ATP', 'WTA', 'CH')
MIN_LIGNES = 1000
SORTIE = os.path.join(ICI, 'rapport_profils_amplification.json')


def _sg(z):
    z = max(min(z, 30.0), -30.0)
    return 1.0 / (1.0 + math.exp(-z))


def photos():
    return [dt.date(y, m, 1) for y in range(DEBUT.year, FIN.year + 1) for m in (1, 4, 7, 10) if DEBUT <= dt.date(y, m, 1) < FIN]


def lignes(archive, racine, journal=True):
    import ajustement as AJ
    import donnees as DN
    import elo as E
    with open(os.path.join(racine, 'simulateur', 'choix_simulation.json'), encoding='utf-8') as f:
        ch = json.load(f)
    n0, n0c = float(ch.get('n0') or AJ.N0), ch.get('n0_par_composante') or None
    M = DN.charger(archive, 2014)
    rows = []
    P = photos()
    for i, d in enumerate(P):
        fin = P[i + 1] if i + 1 < len(P) else FIN
        A = AJ.ajuster(M, d, E.cle, n0=n0, n0_par_composante=n0c)
        for m in M:
            det = m.get('detail')
            if (not det or not (d <= m['date'] < fin) or m['circuit'] not in CIRCUITS or m.get('niveau') == 'D'
                    or m.get('abandon') or not det.get('w') or not det.get('l')):
                continue
            a, b = E.cle(m['nom_g']), E.cle(m['nom_p'])
            for srv, ret, dd, da in ((a, b, det['w'], det['l']), (b, a, det['l'], det['w'])):
                tx = A.taux(srv, ret, m['circuit'], m['surface'])
                for c, (n, k) in AJ.essais(dd, da).items():
                    if n > 0:
                        rows.append([m['date'].isoformat(), m['circuit'], c, int(n), int(k), round(AJ._lg(tx[c]), 5),
                                     round(A.mu(c, m['circuit'], m['surface']), 5)])
        if journal:
            print(f"photo {d} : {len(rows)} lignes", flush=True)
    return rows


def ll(R, k):
    """Log-vraisemblance binomiale totale et nombre de points, avec l'amplification k."""
    s = n_ = 0.0
    for _, _, _, n, x, z, mu in R:
        q = min(max(_sg(mu + k * (z - mu)), 1e-9), 1 - 1e-9)
        s += x * math.log(q) + (n - x) * math.log(1 - q)
        n_ += n
    return s, n_


def pente(R):
    b = 1.0
    for _ in range(50):
        g = h = 0.0
        for _, _, _, n, k, z, mu in R:
            x = z - mu
            q = _sg(mu + b * x)
            g += (n * q - k) * x
            h += n * q * (1 - q) * x * x
        if h < 1e-9:
            break
        pas = g / h
        b -= pas
        if abs(pas) < 1e-7:
            break
    return b


def gain(R, k):
    """Gain de log-vraisemblance par point avec k (contre k = 1), et son erreur type (lignes indépendantes)."""
    D, N = [], 0
    for r in R:
        _, _, _, n, x, z, mu = r
        q1 = min(max(_sg(mu + k * (z - mu)), 1e-9), 1 - 1e-9)
        q0 = min(max(_sg(z), 1e-9), 1 - 1e-9)
        D.append(x * math.log(q1 / q0) + (n - x) * math.log((1 - q1) / (1 - q0)))
        N += n
    if not D:
        return None, None
    m = sum(D) / len(D)
    se = math.sqrt(sum((v - m) ** 2 for v in D) / max(1, len(D) - 1) / len(D))
    return sum(D) / N, se * len(D) / N


def juger(rows):
    import ajustement as AJ
    out = {}
    for c in CIRCUITS:
        out[c] = {}
        for comp in AJ.COMPOSANTES:
            R = [r for r in rows if r[1] == c and r[2] == comp]
            A = [r for r in R if r[0] < COUPURE.isoformat()]
            J = [r for r in R if r[0] >= COUPURE.isoformat()]
            if not A or not J:
                continue
            k, kj = pente(A), pente(J)
            ga, sa = gain(A, k)
            gj, sj = gain(J, k)
            raisons = []
            if len(J) < MIN_LIGNES:
                raisons.append(f"moins de {MIN_LIGNES} lignes jugées")
            if gj is None or gj <= 0:
                raisons.append("pas de gain sur 2023 →")
            if (k - 1) * (kj - 1) <= 0:
                raisons.append("pente jugée de l'autre côté de 1")
            prev = lambda L, kk: 100 * sum(r[3] * _sg(r[6] + kk * (r[5] - r[6])) for r in L) / max(1, sum(r[3] for r in L))
            out[c][comp] = {'k_appris': round(k, 3), 'k_sur_2023': round(kj, 3), 'lignes': {'2019_2022': len(A), '2023': len(J)},
                            'gain_par_point_2019_2022': round(ga * 1000, 4), 'gain_par_point_2023': round(gj * 1000, 4),
                            'erreur_type_2023': round(sj * 1000, 4), 'unite_des_gains': 'millièmes de log-vraisemblance par point',
                            'taux_moyen_2023': {'prevu': round(prev(J, 1.0), 2), 'prevu_amplifie': round(prev(J, k), 2),
                                                'reel': round(100 * sum(r[4] for r in J) / sum(r[3] for r in J), 2)},
                            'retenue': not raisons, 'raisons': raisons}
    return out


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 and not argv[2].startswith('--') else '.')
    cache = argv[argv.index('--lignes') + 1] if '--lignes' in argv else None
    if cache and os.path.exists(cache):
        with gzip.open(cache, 'rt', encoding='utf-8') as f:
            rows = json.load(f)
    else:
        rows = lignes(archive, racine)
        if cache:
            with gzip.open(cache, 'wt', encoding='utf-8') as f:
                json.dump(rows, f)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("amplification par circuit et par composante, apprise sur 2019–2022, jugée sur 2023 → juin 2026 : au moins 1 000 "
                     "lignes, gain de vraisemblance des points positif, pente jugée du même côté de 1 ; puis contrôle du vainqueur"),
           'lignes': len(rows), 'circuits': juger(rows)}
    doc['retenues'] = {c: {comp: x['k_appris'] for comp, x in v.items() if x['retenue']} for c, v in doc['circuits'].items()}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for c, v in doc['circuits'].items():
        for comp, x in v.items():
            t = x['taux_moyen_2023']
            print(f"{c:4s} {comp:4s} k {x['k_appris']:.3f} (2023 : {x['k_sur_2023']:.3f}) | gain ‰/pt appr {x['gain_par_point_2019_2022']:.4f} jugé "
                  f"{x['gain_par_point_2023']:.4f} ± {x['erreur_type_2023']:.4f} | {x['lignes']} | {'RETENUE' if x['retenue'] else x['raisons']}")
    print('retenues :', doc['retenues'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
