#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_forme_match.py — banc d'essai de la FORME des matchs (sets, tie-breaks, nombre de jeux) (04/11/2026, Lucas).

Calcul EXACT (sans tirage) d'un match au meilleur des 3 sets à partir des points de service de chacun (Elo service /
retour d'avant-match, elo_service_retour.py), avec trois corrections candidates, mesurées dans nos études :
  σ   forme du jour : l'écart de forme d = fA − fB ~ N(0, 2σ²) décale le service de A de +d et celui de B de −d
      (le modèle suppose σ = 0,15 ; mesuré 0,27 : rapport_forme_du_jour.json) ;
  tb  au tie-break, chaque serveur décalé de δ_tb en logit (étude des points : −0,58) ;
  set le joueur qui mène d'un set décalé de δ_set au service (étude des points : −1,2 ; possible effet de sélection) ;
  pr  (04/11/2026, point 3) jeux sous pression : à 5-5, 6-5 et 5-6, chaque serveur décalé de δ_pr en logit (si les
      serveurs craquent plus qu'ailleurs, il y a moins de 6-6, donc moins de tie-breaks que la chaîne indépendante).
      MÊME RÈGLE que ci-dessous, fixée avant de regarder ; grille 0 / −0,1 / −0,2 / −0,35 / +0,1.
Le VAINQUEUR est tenu fixe : chaque variante est ré-ancrée (décalage opposé des deux services) sur la probabilité de
victoire de la base (σ = 0,15, sans tb ni set) ; seule la FORME change.

Mesure : log-vraisemblance de la forme réelle = P(vainqueur, nombre de sets, au moins un tie-break, total de jeux).
RÈGLE FIXÉE AVANT DE REGARDER (04/11/2026) : réglages choisis sur 2021–2022 (grilles ci-dessous), jugés sur 2023 → 2026
(échantillon fixe, graine « 20261104-circuit »), PAR CIRCUIT (ATP, WTA, Challenger) : une correction est retenue sur un circuit si
la log-vraisemblance moyenne gagne au moins 0,001 sur le jugement ; elle passe alors en fantôme sur les nouveaux matchs
de ce circuit (deux semaines gagnantes). Matchs au meilleur des 5 sets écartés.
Usage : python simulateur/etude_forme_match.py /tmp/sackmann . [--n 1500]
"""
import datetime as dt
import json
import math
import os
import random
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo_service_retour as SR  # noqa: E402

GRILLES = {'sigma': [0.15, 0.22, 0.27, 0.32], 'tb': [0.0, -0.1, -0.2, -0.35], 'set': [0.0, -0.05, -0.1, -0.2],
           'pr': [0.0, -0.1, -0.2, -0.35, 0.1]}
BASE = {'sigma': 0.15, 'tb': 0.0, 'set': 0.0, 'pr': 0.0}
PRESSION = ((5, 5), (6, 5), (5, 6))
# 7 nœuds de Gauss–Hermite (probabilistes) pour d ~ N(0, 1)
_GH = [(-3.750439717725742, 0.000548268855972), (-2.366759410734541, 0.030757123967586),
       (-1.154405394739968, 0.240123178605013), (0.0, 0.457142857142857),
       (1.154405394739968, 0.240123178605013), (2.366759410734541, 0.030757123967586),
       (3.750439717725742, 0.000548268855972)]


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def tenir(p):
    """P(le serveur gagne son jeu), p = point au service."""
    q = 1 - p
    return p ** 4 * (1 + 4 * q + 10 * q * q) + 20 * p ** 3 * q ** 3 * p * p / (1 - 2 * p * q)


def tiebreak(pa, pb, a_sert):
    """P(A gagne le tie-break à 7) ; pa, pb = points au service ; a_sert = A sert le 1er point."""
    memo = {}

    def serveur(k):
        return a_sert if k == 0 else (a_sert if ((k - 1) // 2) % 2 == 1 else not a_sert)

    def f(x, y):
        if x >= 7 and x - y >= 2:
            return 1.0
        if y >= 7 and y - x >= 2:
            return 0.0
        if x == y and x >= 6:
            a, b = pa * (1 - pb), (1 - pa) * pb          # deux points, un service chacun
            return a / (a + b) if a + b > 0 else 0.5
        k = (x, y)
        if k in memo:
            return memo[k]
        p = pa if serveur(x + y) else 1 - pb
        r = p * f(x + 1, y) + (1 - p) * f(x, y + 1)
        memo[k] = r
        return r
    return f(0, 0)


def set_dist(pa, pb, a_sert, ptb_a, ptb_b, ppr_a=None, ppr_b=None):
    """{(jeux A, jeux B, tie-break): proba} ; ptb_* : points au service pendant le tie-break ; ppr_* : à 5-5, 6-5, 5-6."""
    ha, hb = tenir(pa), tenir(pb)
    hpa, hpb = tenir(ppr_a if ppr_a is not None else pa), tenir(ppr_b if ppr_b is not None else pb)
    tb = tiebreak(ptb_a, ptb_b, a_sert)                   # à 6-6, celui qui servait le 1er jeu sert le 1er point
    out, etats = {}, {(0, 0): 1.0}
    while etats:
        nouv = {}
        for (x, y), pr in etats.items():
            a_sert_ici = a_sert if (x + y) % 2 == 0 else not a_sert
            if (x, y) in PRESSION:
                g = hpa if a_sert_ici else 1 - hpb
            else:
                g = ha if a_sert_ici else 1 - hb
            for (nx, ny), q in (((x + 1, y), g), ((x, y + 1), 1 - g)):
                v = pr * q
                if (nx >= 6 and nx - ny >= 2) or (ny >= 6 and ny - nx >= 2) or nx == 7 or ny == 7:
                    out[(nx, ny, False)] = out.get((nx, ny, False), 0.0) + v
                elif nx == 6 and ny == 6:
                    out[(7, 6, True)] = out.get((7, 6, True), 0.0) + v * tb
                    out[(6, 7, True)] = out.get((6, 7, True), 0.0) + v * (1 - tb)
                else:
                    nouv[(nx, ny)] = nouv.get((nx, ny), 0.0) + v
        etats = nouv
    return out


def match_dist(pa, pb, d_tb=0.0, d_set=0.0, d_pr=0.0):
    """{(A gagne, nb sets, tie-break, total jeux): proba} au meilleur des 3 ; A sert le 1er jeu avec proba 1/2."""
    cache = {}

    def sd(diff, a_sert):
        k = (diff, a_sert)
        if k not in cache:
            za, zb = _lg(pa), _lg(pb)
            if diff > 0:
                za += d_set
            elif diff < 0:
                zb += d_set
            cache[k] = set_dist(_sg(za), _sg(zb), a_sert, _sg(za + d_tb), _sg(zb + d_tb),
                                _sg(za + d_pr) if d_pr else None, _sg(zb + d_pr) if d_pr else None)
        return cache[k]
    out = {}
    for a_premier in (True, False):
        etats = {(0, 0, a_premier, 0, False): 0.5}
        while etats:
            nouv = {}
            for (sa, sb, a_sert, jeux, tbq), pr in etats.items():
                for (x, y, t), q in sd(sa - sb, a_sert).items():
                    na, nb = sa + (x > y), sb + (y > x)
                    suite = a_sert if (x + y) % 2 == 0 else not a_sert
                    cle = (na, nb, suite, jeux + x + y, tbq or t)
                    v = pr * q
                    if na == 2 or nb == 2:
                        k2 = (na == 2, na + nb, tbq or t, jeux + x + y)
                        out[k2] = out.get(k2, 0.0) + v
                    else:
                        nouv[cle] = nouv.get(cle, 0.0) + v
            etats = nouv
    return out


def victoire(dist):
    return sum(v for k, v in dist.items() if k[0])


def avec_forme(pa, pb, sigma, d_tb, d_set, decalage=0.0, d_pr=0.0):
    """Distribution intégrée sur la forme du jour (écart d ~ N(0, 2σ²)), décalage d'ancrage en plus."""
    out = {}
    s = sigma * math.sqrt(2)
    for x, w in _GH:
        d = s * x + decalage
        for k, v in match_dist(_sg(_lg(pa) + d), _sg(_lg(pb) - d), d_tb, d_set, d_pr).items():
            out[k] = out.get(k, 0.0) + w * v
    return out


def ancree(pa, pb, cible, sigma, d_tb, d_set, iterations=14, d_pr=0.0):
    lo, hi = -3.0, 3.0
    for _ in range(iterations):
        m = (lo + hi) / 2
        if victoire(avec_forme(pa, pb, sigma, d_tb, d_set, m, d_pr)) < cible:
            lo = m
        else:
            hi = m
    return avec_forme(pa, pb, sigma, d_tb, d_set, (lo + hi) / 2, d_pr)


def ll_forme(dist, obs):
    return -math.log(max(dist.get(obs, 0.0), 1e-9))


def donnees(archive, racine, depuis=dt.date(2021, 1, 1)):
    """[(jour, circuit, p service vainqueur, p service perdant, forme réelle)] — notes d'avant le jour du match."""
    import json as _j
    import donnees as DN
    import elo as E
    import feuilles as FE
    M = DN.charger(archive, 2015)
    fin = max(m['date'] for m in M)
    M = M + [m for m in FE.charger(racine) if m['date'] > fin]
    try:
        alias = dict(E.migrer_etat(_j.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8'))).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    M.sort(key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    el, jour, attente, out = SR.EloSR(0.0015), None, [], []
    for m in M:
        d = m['date']
        if d != jour:
            for y in attente:
                el.maj(*y)
            attente, jour = [], d
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p or not m.get('complet') or m.get('abandon'):
            continue
        c, s = m['circuit'], m['surface']
        sets = m.get('sets') or []
        if (c in ('ATP', 'WTA', 'CH') and d >= depuis and (m.get('bo') or 3) == 3 and 2 <= len(sets) <= 3
                and el.connu(g) >= 10 and el.connu(p) >= 10 and sum(a > b for a, b in sets) == 2):
            obs = (True, len(sets), any(max(a, b) == 7 and min(a, b) == 6 for a, b in sets), sum(a + b for a, b in sets))
            out.append((d, c, el.p_service(g, p, c, s), el.p_service(p, g, c, s), obs))
        if m.get('stats'):
            attente.append((g, p, c, s, m['stats']))
    return out


def evaluer(rows, reglage):
    tot = 0.0
    for _, _, pa, pb, obs in rows:
        cible = victoire(avec_forme(pa, pb, BASE['sigma'], 0.0, 0.0))
        dist = ancree(pa, pb, cible, reglage['sigma'], reglage['tb'], reglage['set'], d_pr=reglage.get('pr', 0.0))
        tot += ll_forme(dist, obs)
    return tot / max(1, len(rows))


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    archive, racine = args[0], (args[1] if len(args) > 1 else os.path.join(ICI, '..'))
    n = int(next((a.split('=')[1] for a in argv if a.startswith('--n=')), 1200))
    rnd = random.Random(20261104)
    D = donnees(archive, racine)
    out = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'base': BASE,
           'regle': 'réglage choisi sur 2021–2022, jugé 2023 → ; retenu sur un circuit si −0,001 de log-vraisemblance de la forme',
           'circuits': {}}
    seuls = [a.split('=')[1] for a in argv if a.startswith('--c=')]
    for c in (seuls or ['ATP', 'WTA', 'CH']):
        rnd = random.Random(f'20261104-{c}')
        dec = [r for r in D if r[1] == c and r[0] < dt.date(2023, 1, 1)]
        ju = [r for r in D if r[1] == c and r[0] >= dt.date(2023, 1, 1)]
        dec = rnd.sample(dec, min(len(dec), n // 2))
        ju = rnd.sample(ju, min(len(ju), n))
        base_dec = evaluer(dec, BASE)
        bloc = {'decouverte': len(dec), 'jugement': len(ju), 'base_decouverte': round(base_dec, 5)}
        choisis = {}
        corr = [a.split('=')[1] for a in argv if a.startswith('--corr=')]
        for cle, grille in GRILLES.items():
            if corr and cle not in corr:
                continue                       # chaque correction seule, réglée sur la découverte
            best = (base_dec, BASE[cle])
            for v in grille:
                if v == BASE[cle]:
                    continue
                r = dict(BASE, **{cle: v})
                l_ = evaluer(dec, r)
                if l_ < best[0]:
                    best = (l_, v)
            choisis[cle] = best[1]
            print(f"{c} {cle} : choisi {best[1]} (découverte {round(base_dec, 5)} → {round(best[0], 5)})", flush=True)
        base_ju = evaluer(ju, BASE)
        bloc['base_jugement'] = round(base_ju, 5)
        for cle, v in choisis.items():
            if v == BASE[cle]:
                bloc[cle] = {'reglage': v, 'gain': 0.0, 'retenu': False}
                continue
            l_ = evaluer(ju, dict(BASE, **{cle: v}))
            bloc[cle] = {'reglage': v, 'log_vrais': round(l_, 5), 'gain': round(base_ju - l_, 5), 'retenu': base_ju - l_ >= 0.001}
        tous = dict(BASE, **{k: v for k, v in choisis.items()})
        l_t = evaluer(ju, tous)
        bloc['ensemble'] = {'reglage': tous, 'log_vrais': round(l_t, 5), 'gain': round(base_ju - l_t, 5),
                            'retenu': base_ju - l_t >= 0.001}
        out['circuits'][c] = bloc
        print(c, json.dumps(bloc, ensure_ascii=False), flush=True)
    corr = [a.split('=')[1] for a in argv if a.startswith('--corr=')]
    nom = ('rapport_forme_match' + (f'_{"_".join(corr)}' if corr else '') + (f'_{seuls[0]}' if len(seuls) == 1 else '')
           + '.json')
    with open(os.path.join(ICI, nom), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
