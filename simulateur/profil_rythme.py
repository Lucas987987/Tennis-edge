#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
profil_rythme.py — rythme, longueur et régularité de chaque joueur (28/10/2026). DESCRIPTIF : ne change aucune
probabilité ; la vitrine s'en sert pour la durée prévue de chaque match.

Par joueur (matchs terminés depuis 2021, archive Sackmann ATP/WTA/Challenger puis feuilles TennisApi, poids qui
décroît avec l'ancienneté, demi-vie 365 jours) :
  · points et jeux joués par match, part des matchs en 3 sets (au meilleur des 3), part des matchs avec tie-break ;
  · durée moyenne de ses matchs (minutes, quand la source la donne : archive ATP/WTA) ;
  · RYTHME : temps par point propre au joueur, en % par rapport à la moyenne du circuit et de la surface, appris en
    séparant les deux joueurs de chaque match (3 passes, rappel vers 0 de K_RYTHME matchs). Mesuré le 28/10/2026 :
    très stable d'une période à l'autre (corrélation 0,87 entre 2019-2023 et 2024-2026) ; à nombre de points connu,
    il ramène l'erreur moyenne sur la durée de 8,0 à 6,6 minutes ;
  · RÉGULARITÉ (« jours avec / jours sans ») : écart-type de sa part de points gagnés d'un match à l'autre, au-delà
    de l'attendu (Elo d'avant-match) et du simple hasard des points, ramené vers la moyenne (K_VOL matchs). Trait
    réel et stable (corrélation 0,47 entre deux périodes disjointes) ; testé comme forme du jour propre au joueur
    dans la simulation, il n'a rien amélioré (vainqueur 0,62797 contre 0,62829, scores identiques) : il reste
    descriptif.

Usage : python simulateur/profil_rythme.py <archive Sackmann> [racine]
Sortie : simulateur/profil_rythme.json (artefact régénéré, non commité).
"""
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees  # noqa: E402
import elo as E  # noqa: E402
import feuilles as FE  # noqa: E402

SORTIE = os.path.join('simulateur', 'profil_rythme.json')
DEPUIS = 2021
DEMI_VIE_J = 365.0
K_RYTHME = 8.0
K_VOL = 30.0
PENTE_ELO = 0.0635            # part des points gagnés au-delà de 50 % par tranche de 400 points Elo (mesurée le 28/10)
CIRCUITS = ('ATP', 'WTA', 'CH')
SPP_MIN, SPP_MAX = 15.0, 90.0  # secondes par point plausibles (filtre des durées aberrantes)
MIN_MATCHS_PROFIL = 5


def _points(m):
    d = m.get('detail') or {}
    w, l = d.get('w'), d.get('l')
    if not w or not l or not w[0] or not l[0]:
        return None
    return w, l


def lignes(M, cle_c):
    """Matchs utilisables, chronologiques : (date, g, p, circuit, surface, bo, sets, points, pw_g, minutes)."""
    out = []
    for m in M:
        if m.get('circuit') not in CIRCUITS or not m.get('complet') or m.get('abandon') or m['date'].year < DEPUIS:
            continue
        pts = _points(m)
        sets = m.get('sets') or []
        if not pts or not sets:
            continue
        w, l = pts
        tot = w[0] + l[0]
        if tot < 40:
            continue
        g, p = cle_c(m.get('nom_g')), cle_c(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        pw_g = ((w[2] + w[3]) + (l[0] - l[2] - l[3])) / tot          # points gagnés par le vainqueur (service + retour)
        mins = m.get('minutes')
        if mins and not (SPP_MIN <= mins * 60 / tot <= SPP_MAX):
            mins = None
        out.append((m['date'], g, p, m['circuit'], m['surface'], m.get('bo') or 3, sets, tot, pw_g, mins))
    out.sort(key=lambda x: x[0])
    return out


def _poids(jour, ref):
    return 0.5 ** (max((ref - jour).days, 0) / DEMI_VIE_J)


def calculer(L, ref):
    """{joueur: profil} et bases de rythme {circuit|surface: log secondes par point}."""
    # --- bases de rythme (moyenne pondérée du log temps par point)
    acc_b = collections.defaultdict(lambda: [0.0, 0.0])
    for d, g, p, c, s, bo, sets, tot, pw, mins in L:
        if mins:
            w = _poids(d, ref)
            acc_b[f'{c}|{s}'][0] += w * math.log(mins * 60 / tot)
            acc_b[f'{c}|{s}'][1] += w
    base = {k: a / n for k, (a, n) in acc_b.items() if n > 0}

    def b(c, s):
        return base.get(f'{c}|{s}', base.get(f'ATP|{s}', math.log(38.0)))

    # --- effets de rythme des joueurs (3 passes alternées, rappel vers 0)
    eff = collections.defaultdict(float)
    for _ in range(3):
        acc = collections.defaultdict(lambda: [0.0, 0.0])
        for d, g, p, c, s, bo, sets, tot, pw, mins in L:
            if not mins:
                continue
            w = _poids(d, ref)
            r = math.log(mins * 60 / tot) - b(c, s)
            acc[g][0] += w * (r - eff[p])
            acc[g][1] += w
            acc[p][0] += w * (r - eff[g])
            acc[p][1] += w
        eff = collections.defaultdict(float, {j: a / (n + K_RYTHME) for j, (a, n) in acc.items()})

    # --- régularité : Elo courant, résidus de points gagnés, excès de variance au-delà du binomial
    elo = E.Elo()
    res = collections.defaultdict(list)
    for d, g, p, c, s, bo, sets, tot, pw, mins in L:
        if c == 'CH':
            elo.presenter(g, 1200.0)
            elo.presenter(p, 1200.0)
        dz = (elo.note(g, s) - elo.note(p, s)) / 400
        r = pw - 0.5 - PENTE_ELO * dz
        res[g].append((r, tot))
        res[p].append((-r, tot))
        elo.maj(g, p, s, False, None)

    def exces(R):
        if len(R) < 2:
            return 0.0
        m = sum(x for x, _ in R) / len(R)
        v = sum((x - m) ** 2 for x, _ in R) / len(R)
        return max(v - sum(0.25 / t for _, t in R) / len(R), 0.0)
    tous = [e for R in res.values() for e in R]
    v_glob = max(sum(x * x for x, _ in tous) / len(tous) - sum(0.25 / t for _, t in tous) / len(tous), 0.0) if tous else 0.002
    vol = {j: math.sqrt((len(R) * exces(R) + K_VOL * v_glob) / (len(R) + K_VOL)) for j, R in res.items()}
    # comparaison avec les joueurs du MÊME circuit principal (ATP, WTA ou Challenger) et au moins 30 matchs
    circ = collections.defaultdict(collections.Counter)
    for d, g, p, c, s, bo, sets, tot, pw, mins in L:
        circ[g][c] += 1
        circ[p][c] += 1
    principal = {j: C.most_common(1)[0][0] for j, C in circ.items()}
    ref_vol = collections.defaultdict(list)
    for j, v in vol.items():
        if len(res[j]) >= 30:
            ref_vol[principal[j]].append(v)
    for k in ref_vol:
        ref_vol[k].sort()

    def centile(j, v):
        R_ = ref_vol.get(principal.get(j)) or []
        if not R_:
            return None
        import bisect
        return round(100 * bisect.bisect_left(R_, v) / len(R_))

    # --- descriptifs par joueur (pondérés par l'ancienneté)
    D = collections.defaultdict(lambda: collections.Counter())
    for d, g, p, c, s, bo, sets, tot, pw, mins in L:
        w = _poids(d, ref)
        jeux = sum(a + b_ for a, b_ in sets)
        tb = any(max(a, b_) == 7 and min(a, b_) == 6 for a, b_ in sets)
        for j in (g, p):
            e = D[j]
            e['n'] += 1
            e['w'] += w
            e['points'] += w * tot
            e['jeux'] += w * jeux
            e['tb'] += w * tb
            if bo == 3:
                e['w3'] += w
                e['trois_sets'] += w * (len(sets) == 3)
            if mins:
                e['wm'] += w
                e['minutes'] += w * mins
    profils = {}
    for j, e in D.items():
        if e['n'] < MIN_MATCHS_PROFIL:
            continue
        v = vol.get(j)
        cv = centile(j, v) if v is not None else None
        profils[j] = {
            'matchs': int(e['n']),
            'points_par_match': round(e['points'] / e['w'], 1),
            'jeux_par_match': round(e['jeux'] / e['w'], 1),
            'tiebreak_pct': round(100 * e['tb'] / e['w'], 1),
            'trois_sets_pct': round(100 * e['trois_sets'] / e['w3'], 1) if e['w3'] else None,
            'minutes_par_match': round(e['minutes'] / e['wm']) if e['wm'] else None,
            'rythme_pct': round(100 * (math.exp(eff.get(j, 0.0)) - 1), 1),
            'rythme_log': round(eff.get(j, 0.0), 4),
            'circuit_principal': principal.get(j),
            'regularite': {'volatilite_pts': round(100 * v, 2) if v is not None else None,
                           'centile': cv,
                           'niveau': (None if cv is None or len(res[j]) < 30 else
                                      'jours_sans_frequents' if cv >= 75 else
                                      'tres_regulier' if cv <= 25 else 'habituel')},
        }
    return profils, {k: round(v, 5) for k, v in base.items()}


def construire(racine, archive, maintenant=None):
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    M = donnees.charger(archive, DEPUIS)
    if not M:
        raise ValueError(f'aucun match Sackmann sous {archive}')
    fin = max(m['date'] for m in M)
    F = [m for m in FE.charger(racine) if m['date'] > fin]
    try:
        with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
            alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    cle_c = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    L = lignes(M + F, cle_c)
    profils, bases = calculer(L, maintenant.date())
    return {'schema': 'profil_rythme_v1', 'genere_le': maintenant.isoformat(timespec='seconds'),
            'archive_jusqu_au': fin.isoformat(), 'matchs': len(L), 'bases_log_secondes_par_point': bases,
            'regle': ('Descriptif. Rythme = temps par point propre au joueur (archive ATP/WTA avec durée) ; '
                      'régularité = variabilité de ses points gagnés d’un match à l’autre au-delà de l’attendu. '
                      'Ne modifie aucune probabilité.'),
            'joueurs': profils}


# ------------------------------------------------------------------ prévision de durée d'un match (vitrine)
def points_par_jeu(p):
    """Nombre moyen de points d'un jeu de service gagné avec probabilité p par point."""
    q = 1 - p
    # jeux finis en 4, 5, 6 points, ou passage par égalité (6 points + 2 / (p² + q²) en moyenne)
    p4 = p ** 4 + q ** 4
    p5 = 4 * (p ** 4 * q + q ** 4 * p)
    p6 = 10 * (p ** 4 * q ** 2 + q ** 4 * p ** 2)
    pe = 20 * p ** 3 * q ** 3
    return 4 * p4 + 5 * p5 + 6 * p6 + pe * (6 + 2 / (p * p + q * q))


def prevision(ligne, profils, bases, cle_c):
    """{'points', 'minutes', 'minutes_p10', 'minutes_p90'} pour une ligne de la vitrine, ou None."""
    sim = ligne.get('simulation') or {}
    dist = ligne.get('distribution_scores') or []
    if not sim.get('a') or not sim.get('b') or not dist:
        return None
    ppg = (points_par_jeu(sim['a']) + points_par_jeu(sim['b'])) / 2
    surf = ligne.get('surface')
    c = ligne.get('circuit')
    base = bases.get(f'{c}|{surf}', bases.get(f'ATP|{surf}'))
    if base is None:
        return None
    h, a = cle_c(ligne['home']), cle_c(ligne['away'])
    rl = (profils.get(h) or {}).get('rythme_log', 0.0) + (profils.get(a) or {}).get('rythme_log', 0.0)
    spp = math.exp(base + rl)
    issues = []
    for e in dist:
        sets = e.get('score') or []
        jeux = sum(x + y for x, y in sets)
        tbs = sum(1 for x, y in sets if max(x, y) == 7 and min(x, y) == 6)
        points = (jeux - tbs) * ppg + tbs * 12.0                     # un tie-break ≈ 12 points
        issues.append((points, e.get('probabilite') or 0.0))
    tot = sum(w for _, w in issues)
    if tot <= 0:
        return None
    issues.sort()
    pts_moy = sum(p * w for p, w in issues) / tot

    def q(f):
        acc = 0.0
        for p, w in issues:
            acc += w / tot
            if acc >= f:
                return p
        return issues[-1][0]
    return {'points': round(pts_moy), 'minutes': round(pts_moy * spp / 60),
            'minutes_p10': round(q(0.10) * spp / 60), 'minutes_p90': round(q(0.90) * spp / 60),
            'secondes_par_point': round(spp, 1)}


def main(argv=None):
    argv = argv or sys.argv
    if len(argv) < 2:
        print('Usage : python simulateur/profil_rythme.py <archive Sackmann> [racine]')
        return 2
    racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    doc = construire(racine, argv[1])
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print(f"Profils de rythme : {len(doc['joueurs'])} joueurs · {doc['matchs']} matchs · archive jusqu’au "
          f"{doc['archive_jusqu_au']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
