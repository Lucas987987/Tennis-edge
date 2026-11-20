#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_cpi.py — la vitesse du court (CPI) améliore-t-elle la prévision du vainqueur ? (04/11/2026, demande de Lucas)

Idée : un court rapide avantage le meilleur SERVEUR, un court lent le meilleur RELANCEUR. Variable d'interaction :
    x = (CPI − 35) / 10 × [ (S_A − S_B) − (R_A − R_B) ]
avec S, R les notes au service et au retour de l'Elo service / retour d'avant-match (elo_service_retour.py).
Correction : z = logit p_base + β·x, β appris sur 2016–2022, jugé sur 2023 → 2026 (jamais vu).
Deux bases : l'Elo seul (le modèle principal, ~78 % du mélange) et le mélange 78 % Elo + 22 % Elo service / retour.

A. CPI OFFICIEL (simulateur/cpi_officiel.json) : ATP seulement, éditions où il est publié.
B. CPI ESTIMÉ (vitesse_courts.py), calculé AVANT le jour du match seulement : moitié de l'édition précédente +
   matchs déjà joués de l'édition en cours ; étalonnage du CPI appris sur les éditions ≤ 2022 seulement.
   Tous les tournois, jugé SÉPARÉMENT sur ATP, WTA et Challenger (décision de Lucas, 04/11/2026).

RÈGLE FIXÉE AVANT DE REGARDER (04/11/2026) : sur un circuit, positif si la log loss du vainqueur 2023 → 2026 baisse
d'au moins 0,001 avec les DEUX bases, sur au moins 300 matchs jugés. Positif → modèle fantôme sur les nouveaux matchs de
ce circuit (fantomes_circuits.py : deux semaines gagnantes). Sinon : la vitesse reste une information (et le facteur
« vitesse du court » déjà en place dans le modèle).
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo as E  # noqa: E402
import elo_service_retour as SR  # noqa: E402
import vitesse_courts as V  # noqa: E402

COUPURE = dt.date(2023, 1, 1)
W_ELO = 0.78


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def ll(p, y=1):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p if y else 1 - p)


def apprendre_beta(R):
    b = 0.0
    for _ in range(40):
        g = h = 0.0
        for z, x in R:                          # vainqueur = joueur A (y = 1)
            q = _sg(z + b * x)
            g += (q - 1) * x
            h += q * (1 - q) * x * x
        if h <= 0:
            break
        b -= g / (h + 1.0)
    return b


def main(archive, racine):
    cpi_off = V.lire_cpi(racine)
    M = V.matchs(archive, racine, 2012)
    # étalonnage du CPI estimé sur les éditions ≤ 2022 seulement
    I = V.indices([m for m in M if m[0] < COUPURE])
    et, _ = V.etalonner({k: v for k, v in I.items()}, {k: v for k, v in cpi_off.items() if k[1] < 2023})
    coefs, moyen = et['coefs'], et['cpi_moyen']
    el, sr = E.Elo(), SR.EloSR(0.0015)
    ed = {}                                     # (c, t, an) → [pts, res, res_ace]
    ace_j, ace_c = {}, {}
    jour, attente, rows = None, [], []
    for d, _, _, c, s, t, nom, g, p, st, det in M:
        if d != jour:
            for y in attente:
                gg, pp, cc, ss, stt, aces, ee, gs = y
                sr.maj(gg, pp, cc, ss, stt)
                el.maj(gg, pp, ss, gs, None)
                for srv, (n_, a_) in aces:
                    A = ace_j.setdefault(srv, [0.0, 0.0]); A[0] += a_; A[1] += n_
                    C = ace_c.setdefault(cc, [0.0, 0.0]); C[0] += a_; C[1] += n_
                for k_, v_ in ee:
                    e = ed.setdefault(k_, [0.0, 0.0, 0.0])
                    for i in range(3):
                        e[i] += v_[i]
            attente, jour = [], d
        if c in ('CH', 'ITF'):
            el.presenter(g, 1200.0)
            el.presenter(p, 1200.0)
        an = d.year if not (d.month == 12 and d.day > 25) else d.year + 1
        # CPI estimé AVANT ce jour : moitié de l'édition précédente + édition en cours (matchs des jours précédents)
        cur, prev = ed.get((c, t, an)) or [0, 0, 0], ed.get((c, t, an - 1)) or [0, 0, 0]
        pts = cur[0] + 0.5 * prev[0]
        cpi_e = None
        if pts >= 300:
            v = {'pts': pts, 'service': (cur[1] + 0.5 * prev[1]) / pts, 'aces': (cur[2] + 0.5 * prev[2]) / pts}
            cpi_e = V.cpi_estime(v, coefs, moyen)
        k_off = V.cle_officielle(nom) if c == 'ATP' else None
        cpi_o = cpi_off.get((k_off, an)) if k_off else None
        if c != 'ITF' and sr.connu(g) >= 5 and sr.connu(p) >= 5 and d >= dt.date(2016, 1, 1):
            pe = el.proba(g, p, s)
            ps = sr.proba(g, p, c, s, 2)
            z_elo = _lg(pe)
            z_mix = W_ELO * _lg(pe) + (1 - W_ELO) * _lg(ps)
            serv = (sr.S.get(g, 0) - sr.S.get(p, 0)) - (sr.R.get(g, 0) - sr.R.get(p, 0))
            rows.append({'d': d, 'c': c, 'z_elo': z_elo, 'z_mix': z_mix, 'serv': serv, 'cpi_o': cpi_o, 'cpi_e': cpi_e})
        # mise à jour différée (fin de journée) : indice d'édition et notes
        ee = []
        aces = []
        r_tot = [0.0, 0.0, 0.0]
        for srv, rel, cle in ((g, p, 'w'), (p, g, 'l')):
            n, w = st[cle]
            dd = det.get(cle)
            if not n:
                continue
            r_tot[0] += n
            r_tot[1] += w - n * sr.p_service(srv, rel, c, s)
            if dd:
                C = ace_c.get(c, [0.0, 0.0]); moy = C[0] / C[1] if C[1] else 0.07
                A = ace_j.get(srv, [0.0, 0.0]); r = (A[0] + V.PRIOR_ACES * moy) / (A[1] + V.PRIOR_ACES)
                r_tot[2] += dd[4] - n * r
                aces.append((srv, (n, dd[4])))
        ee.append(((c, t, an), r_tot))
        attente.append((g, p, c, s, st, aces, ee, False))
    out = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'etalonnage_jusqu_2022': et,
           'regle': 'positif si −0,001 de log loss 2023 → avec les deux bases, ≥ 300 matchs jugés, par circuit',
           'A_cpi_officiel': {}, 'B_cpi_estime': {}}
    for nom_t, cle_cpi, circuits in (('A_cpi_officiel', 'cpi_o', ('ATP',)), ('B_cpi_estime', 'cpi_e', ('ATP', 'WTA', 'CH'))):
        for c in circuits:
            R = [r for r in rows if r['c'] == c and r[cle_cpi] is not None]
            av, ju = [r for r in R if r['d'] < COUPURE], [r for r in R if r['d'] >= COUPURE]
            bloc = {'appris': len(av), 'juges': len(ju)}
            ok_tout = len(ju) >= 300
            for base in ('z_elo', 'z_mix'):
                x = lambda r: (r[cle_cpi] - 35.0) / 10.0 * r['serv']
                b = apprendre_beta([(r[base], x(r)) for r in av]) if av else 0.0
                l0 = sum(ll(_sg(r[base])) for r in ju) / max(1, len(ju))
                l1 = sum(ll(_sg(r[base] + b * x(r))) for r in ju) / max(1, len(ju))
                bloc[base] = {'beta': round(b, 4), 'log_loss_sans': round(l0, 5), 'log_loss_avec': round(l1, 5),
                              'gain': round(l0 - l1, 5)}
                ok_tout = ok_tout and (l0 - l1) >= 0.001
            bloc['positif'] = bool(ok_tout)
            if ju:
                bloc['cpi_moyen_juge'] = round(sum(r[cle_cpi] for r in ju) / len(ju), 1)
            out[nom_t][c] = bloc
    with open(os.path.join(ICI, 'rapport_cpi.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(ICI, '..'))
