#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_salle_service.py — en salle, les deux joueurs gagnent-ils plus de points au service que ce que l'algo prévoit ?
(22/11/2026, paquet 343, demande de Lucas : « fais la piste salle »)

D'OÙ VIENT LA QUESTION : sur nos pronostics figés, le % de points gagnés au service réel dépasse le prévu d'environ
1 point ; en Challenger le nombre de jeux, juste avant le 08/11, est trop bas depuis (−0,7 jeu), au moment où la
saison passe en salle ; le diagnostic du paquet 336 donnait +1,6 point au service sur dur en salle contre +0,6 en
moyenne. Aujourd'hui « en salle » ne sert qu'aux statistiques affichées (1res balles, doubles fautes : paquet 238), pas
aux probabilités de point qui font le nombre de jeux.

CE QUI EST TESTÉ, circuit par circuit : probabilité de gagner un point au service = Elo service / retour d'avant-match
(le niveau des deux joueurs est retiré), puis, en logit :
  • COURS : + constante + β · vitesse mesurée dans l'édition en cours jusqu'au tour précédent (ce que la production
            sait déjà : facteurs.py, groupe « vitesse_court ») ;
  • SALLE : COURS + γ · (1 si le match se joue en salle).
  Le terme « salle » sait AVANT le premier match du tournoi ce que la mesure « en cours » ne découvre qu'au fil des tours.

RÈGLE FIXÉE AVANT DE REGARDER (22/11/2026) :
  • mesure : log loss moyenne par point au service (binomiale, par match, les deux serveurs), comme au paquet 340 ;
  • ATP et WTA : « en salle » d'après tournois_en_salle.py (table écrite depuis le calendrier, sans regarder un
    résultat) ; APPRENTISSAGE 2018–2022, JUGEMENT 2023 → mai 2026 (archive) ; matchs dont on ne sait pas s'ils sont en
    salle écartés ;
  • CHALLENGER : l'archive ne dit pas qui joue en salle ; seules les feuilles TennisApi le disent (« Hardcourt
    indoor », depuis juin 2026). APPRENTISSAGE juin → septembre 2026, JUGEMENT à partir du 1er octobre 2026 —
    écart à la règle habituelle assumé et écrit ici avant de regarder, faute d'archive ;
  • RETENU pour un circuit si, sur le jugement : gain ≥ 0,001 sur ≥ 1 000 matchs jugés (dont au moins 300 en salle),
    gain du même sens sur l'apprentissage, significatif après correction de Holm sur les trois circuits (test apparié
    par match, unilatéral) ;
  • rien ne change en production ici : une case retenue passera ensuite par un paquet à part (la salle entrerait dans
    le niveau au service des deux joueurs, avant réancrage : le % de victoire ne bougerait pas).
DIAGNOSTIC (ne décide rien) : écart réel − attendu au service, en salle et en plein air, par circuit et par période.
Sortie : simulateur/rapport_salle_service.json (aucun nom, aucune cote).
Usage : python simulateur/etude_salle_service.py <archive Sackmann> [racine]
"""
import datetime as dt
import json
import math
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import elo_service_retour as SR  # noqa: E402
import etude_vitesse_derive as V  # noqa: E402

SORTIE = os.path.join(ICI, 'rapport_salle_service.json')
CIRCUITS = ('ATP', 'WTA', 'CH')
PERIODES = {'ATP': ((dt.date(2018, 1, 1), dt.date(2023, 1, 1)), (dt.date(2023, 1, 1), dt.date(2026, 6, 1))),
            'WTA': ((dt.date(2018, 1, 1), dt.date(2023, 1, 1)), (dt.date(2023, 1, 1), dt.date(2026, 6, 1))),
            'CH': ((dt.date(2026, 6, 1), dt.date(2026, 10, 1)), (dt.date(2026, 10, 1), dt.date(2100, 1, 1)))}
GAIN_MIN, N_MIN, N_SALLE_MIN = 0.001, 1000, 300
MODELES = {'COURS': (0,), 'SALLE': (0, 1)}


def matchs(archive, racine, depuis=2015):
    """[(jour, tour, num, circuit, surface, tournoi normalisé, nom, gagnant, perdant, stats, salle)] archive puis feuilles.
    salle : True / False / None (inconnu)."""
    import donnees
    import elo as E
    import feuilles as FE
    import tournois_en_salle as TS
    import vitesse_courts as VC
    M = donnees.charger(archive, depuis)
    fin = max(m['date'] for m in M) if M else dt.date(2000, 1, 1)
    F = [m for m in FE.charger(racine) if m['date'] > fin]
    try:
        with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
            alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    out = []
    for m in M + F:
        if not m.get('stats') or not m.get('complet') or m.get('abandon'):
            continue
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not (g and p and g != p):
            continue
        if m.get('source') == 'tennisapi':
            sb = str(m.get('sol_brut') or '').lower()
            salle = True if 'indoor' in sb else (False if sb else None)
        else:
            salle = TS.en_salle(m['circuit'], m.get('tournoi'), m['surface'])
        out.append((m['date'], m.get('tour', 0), m.get('num', 0), m['circuit'], m['surface'], VC.norme(m.get('tournoi')),
                    m.get('tournoi') or '', g, p, m['stats'], salle))
    out.sort(key=lambda x: (x[0], x[1], x[2]))
    return out


def lignes(M, eta=V.ETA):
    """(circuit, date, salle, [(n, w, z0, (4·cours, salle))]) — tout d'avant le match (mise à jour à chaque tour)."""
    el, cle_t, attente, ED, out = SR.EloSR(eta), None, [], {}, []
    for d, tour, _, c, s, t, nom, g, p, st, salle in M:
        if (d, tour) != cle_t:
            for (c_, t_, an_, srvs, g_, p_, s_, st_) in attente:
                acc = ED.setdefault((c_, t_, an_), [0.0, 0.0])
                for srv, rel, n, w in srvs:
                    acc[0] += w - n * el.p_service(srv, rel, c_, s_)
                    acc[1] += n
                el.maj(g_, p_, c_, s_, st_)
            attente, cle_t = [], (d, tour)
        an = V.annee_edition(d)
        cur = ED.get((c, t, an), [0.0, 0.0])
        x_cours = 4 * cur[0] / (cur[1] + V.K_COURS)
        srvs, cotes = [], []
        for srv, rel, cl in ((g, p, 'w'), (p, g, 'l')):
            n, w = st.get(cl) or (0, 0)
            if not n:
                continue
            srvs.append((srv, rel, n, w))
            q = min(max(el.p_service(srv, rel, c, s), 1e-6), 1 - 1e-6)
            cotes.append((n, w, math.log(q / (1 - q)), (x_cours, 1.0 if salle else 0.0)))
        if c in CIRCUITS and cotes and salle is not None:
            out.append((c, d, salle, cotes))
        attente.append((c, t, an, srvs, g, p, s, st))
    return out


def apprendre(L, cols, tours=12, ridge=1e-3):
    k = 1 + len(cols)
    th = [0.0] * k
    for _ in range(tours):
        g, H = [0.0] * k, [[0.0] * k for _ in range(k)]
        for *_, cotes in L:
            for n, w, z0, x in cotes:
                v = [1.0] + [x[i] for i in cols]
                p = V._sg(z0 + sum(a * b for a, b in zip(th, v)))
                r, q = w - n * p, n * p * (1 - p)
                for i in range(k):
                    g[i] += r * v[i]
                    for j in range(k):
                        H[i][j] += q * v[i] * v[j]
        for i in range(k):
            H[i][i] += ridge
            g[i] -= ridge * th[i]
        pas = V.resoudre(H, g)
        th = [a + b for a, b in zip(th, pas)]
        if max(abs(x) for x in pas) < 1e-7:
            break
    return th


def pertes(L, cols, th):
    out = []
    for *_, cotes in L:
        tot, npts = 0.0, 0
        for n, w, z0, x in cotes:
            v = [1.0] + [x[i] for i in cols]
            p = min(max(V._sg(z0 + sum(a * b for a, b in zip(th, v))), 1e-9), 1 - 1e-9)
            tot -= w * math.log(p) + (n - w) * math.log(1 - p)
            npts += n
        out.append(tot / npts)
    return out


def diagnostic(L):
    D = {}
    for c, d, salle, cotes in L:
        per = 'apprentissage' if d < PERIODES[c][0][1] else 'jugement'
        if d < PERIODES[c][0][0]:
            continue
        e = D.setdefault(c, {}).setdefault(per, {}).setdefault('salle' if salle else 'plein_air', [0, 0.0, 0.0])
        e[0] += 1
        for n, w, z0, x in cotes:
            e[1] += w - n * V._sg(z0)
            e[2] += n
    return {c: {per: {k: {'matchs': v[0], 'ecart_service_pts': round(100 * v[1] / v[2], 2) if v[2] else None}
                      for k, v in G.items()} for per, G in P.items()} for c, P in D.items()}


def etudier(L):
    cases, pv = {}, {}
    for c in CIRCUITS:
        (a0, a1), (j0, j1) = PERIODES[c]
        app = [r for r in L if r[0] == c and a0 <= r[1] < a1]
        jug = [r for r in L if r[0] == c and j0 <= r[1] < j1]
        if not app or not jug:
            cases[c] = {'n_app': len(app), 'n_jug': len(jug), 'retenu': False, 'raison': 'données insuffisantes'}
            continue
        th = {m: apprendre(app, cols) for m, cols in MODELES.items()}
        P = {(m, nom): pertes(D, MODELES[m], th[m]) for m in MODELES for nom, D in (('app', app), ('jug', jug))}
        dif = {nom: [a - b for a, b in zip(P[('COURS', nom)], P[('SALLE', nom)])] for nom in ('app', 'jug')}
        gs = {nom: sum(v) / len(v) for nom, v in dif.items()}
        pv[c] = V.p_unilaterale(dif['jug'])
        cases[c] = {'n_app': len(app), 'n_jug': len(jug), 'n_jug_salle': sum(1 for r in jug if r[2]),
                    'coefs': {m: [round(x, 4) for x in v] for m, v in th.items()},
                    'salle_en_points_de_service': round(100 * th['SALLE'][2] * 0.236, 2),
                    'gain_app': round(gs['app'], 5), 'gain_jug': round(gs['jug'], 5), 'p_jug': pv[c]}
    sig = V.holm(pv) if pv else {}
    for c, e in cases.items():
        if 'gain_jug' not in e:
            continue
        raisons = []
        if e['n_jug'] < N_MIN or e['n_jug_salle'] < N_SALLE_MIN:
            raisons.append(f"pas encore jugeable : {e['n_jug']} matchs jugés dont {e['n_jug_salle']} en salle "
                           f"(il en faut {N_MIN} dont {N_SALLE_MIN})")
        if e['gain_jug'] < GAIN_MIN:
            raisons.append(f"gain jugé {e['gain_jug']} < {GAIN_MIN}")
        if e['gain_app'] <= 0 or e['gain_jug'] <= 0:
            raisons.append('pas le même sens sur les deux périodes')
        if not sig.get(c):
            raisons.append('non significatif après Holm')
        e['significatif_holm'] = bool(sig.get(c))
        e['retenu'] = not raisons
        e['raison'] = 'RETENU' if not raisons else ' ; '.join(raisons)
    return cases


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    archive, racine = argv[0], (argv[1] if len(argv) > 1 else os.path.join(ICI, '..'))
    t0 = time.time()
    L = lignes(matchs(archive, racine))
    rapport = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
               'regle': "log loss par point au service ; ATP/WTA appris 2018–2022, jugés 2023 → mai 2026 ; Challenger "
                        "appris juin → septembre 2026, jugé depuis octobre (feuilles) ; retenu si gain ≥ 0,001 sur ≥ "
                        "1 000 matchs jugés dont ≥ 300 en salle, même sens, Holm sur 3 circuits ; rapport seulement",
               'diagnostic': diagnostic(L), 'cases': etudier(L)}
    rapport['duree_s'] = round(time.time() - t0)
    for c, P in rapport['diagnostic'].items():
        print(c, 'écart réel − attendu au service (pts) :', json.dumps(P, ensure_ascii=False))
    for c, e in rapport['cases'].items():
        print(f"{c}: jugés {e.get('n_jug')} (salle {e.get('n_jug_salle')}) · salle ≈ {e.get('salle_en_points_de_service')} "
              f"pt · gain app {e.get('gain_app')} · jug {e.get('gain_jug')} → {e.get('raison')}")
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rapport, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
