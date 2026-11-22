#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_service_challenger.py — le service est-il sous-estimé en Challenger ? (22/11/2026, paquet 336, demande de Lucas :
« on doit régler ce problème là en Challenger »).

CONSTAT (simulateur/biais_annexes.json, nos matchs Challenger suivis du 05/10 au 16/11/2026, 1 726 valeurs, 682 matchs) :
points gagnés derrière la 1re balle prévus trop bas de 0,9 pt, derrière la 2e de 0,9 pt, % de jeux de service gagnés de
1,8 pt, points gagnés dans le match de 1,6 ; « plus de 19,5 / 20,5 / 21,5 jeux » annoncés 57,8 / 50,7 / 45,8 % pour
62,9 / 55,0 / 50,1 % réels. Lecture : les DEUX joueurs servent mieux que prévu, d'où plus de jeux tenus et des matchs
moins déséquilibrés. Le réglage « longueur commune » existant (reglage_match_simule.py, jeux_delta) a été appris sur
l'ATP et la WTA seulement, et n'a jamais été adopté.

CORRECTION TESTÉE : δ ajouté à la probabilité de gagner le point au service des DEUX joueurs (match_simule.ajuster :
1re et 2e balle décalées ensemble), puis réancrage sur la probabilité de victoire. Le % de victoire ne change donc PAS
(ni le Brier) : seules les statistiques annoncées et les lignes de jeux bougent.

RÈGLE FIXÉE AVANT DE REGARDER (22/11/2026) :
  • population : matchs Challenger au meilleur des 3 sets, terminés (pas d'abandon), avec feuille complète ;
    composantes comme en production (ajustées au niveau des adversaires, choix_simulation.json) ;
  • APPRENTISSAGE 2018–2022 (archive Sackmann) : δ choisi sur la grille −0,02 … +0,03 (pas 0,005) qui minimise la log
    loss moyenne des six lignes « plus de L jeux », L = 18,5 … 23,5 (distribution exacte du total de jeux, moteur DP) ;
  • JUGEMENT 2023 → mai 2026 (archive, jamais vue) ET feuilles TennisApi depuis juin 2026 (là où l'écart a été vu) :
    retenu si la log loss des lignes baisse d'au moins 0,001 sur ≥ 1 000 matchs du jugement archive, baisse aussi sur
    les feuilles TennisApi (même sens), et si l'écart moyen |prévu − réel| du % de points gagnés au service (par
    joueur) ne monte pas de plus de 1 % sur les deux jugements ;
  • rien d'autre n'est réglé ici ; un δ retenu ne touche que le Challenger, et SEULEMENT après le contrôle « comme en
    production » (ce rejeu n'a pas les facteurs du match de la production) : pronostics_du_jour.py exige aussi
    « verifie_comme_en_production », que cette étude ne pose jamais.
DIAGNOSTIC (ne décide rien, sert à comprendre l'écart) : à δ = 0, % de points gagnés au service prévu et réel, total
de jeux prévu et réel, « plus de 20,5 jeux » prévu et réel — par période, et pour les feuilles TennisApi par mois et
par type de court (dur intérieur, dur extérieur, terre). Une première lecture sur 150 matchs allait en sens contraire
entre l'archive (moins de jeux que prévu) et les feuilles 2026 (plus de jeux) : le diagnostic dira si l'écart vient de
la saison intérieure, des courts rapides ou d'un changement récent.
Rapport : simulateur/rapport_service_challenger.json. Lecture seule tant que la règle n'est pas passée.
Usage : python simulateur/etude_service_challenger.py <archive Sackmann> [racine] [--max=3000]
"""
import datetime as dt
import heapq
import json
import math
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import ajustement as AJ  # noqa: E402
import backtest_pronostic as BP  # noqa: E402
import donnees  # noqa: E402
import elo as E  # noqa: E402
import feuilles as FE  # noqa: E402
import match_simule as S  # noqa: E402
import modele as MM  # noqa: E402
import profils_service as PS  # noqa: E402

SORTIE = os.path.join(ICI, 'rapport_service_challenger.json')
SIGMA = 0.15
BAS = ('CH', 'ITF', 'ITFH')
GRILLE = tuple(round(-0.02 + 0.005 * i, 3) for i in range(11))
LIGNES = (18.5, 19.5, 20.5, 21.5, 22.5, 23.5)
APP = (dt.date(2018, 1, 1), dt.date(2023, 1, 1))
JUG = (dt.date(2023, 1, 1), dt.date(2026, 6, 1))
GAIN_MIN, N_MIN, TOL_MAE = 0.001, 1000, 1.01


def decaler(c, delta):
    return c if not delta else S.ajuster(c, max(.15, min(.85, S.p_service(c) + delta)))


def distribution(cg, cp, p_elo, delta):
    """(distribution exacte du total de jeux, p service gagnant, p service perdant) après δ et réancrage."""
    cg, cp = decaler(cg, delta), decaler(cp, delta)
    a, b = S.ancrer_rapide(S.p_service(cg), S.p_service(cp), p_elo, 2, SIGMA)
    return MM.match_forme(a, b, 2, SIGMA)['total_jeux'], a, b


def log_loss_lignes(dist, total):
    ll = 0.0
    for L in LIGNES:
        p = sum(v for k, v in dist.items() if k > L)
        p = min(max(p, 1e-6), 1 - 1e-6)
        ll -= math.log(p if total > L else 1 - p)
    return ll / len(LIGNES)


def evaluer(obs, deltas):
    """obs : (cg, cp, p_elo, total réel, % pts service gagnant réel, % perdant réel) -> {δ: {ll, mae_pts, n}}."""
    out = {}
    for d in deltas:
        ll = mae = 0.0
        for cg, cp, p_elo, total, sg, sp, *_ in obs:
            dist, a, b = distribution(cg, cp, p_elo, d)
            ll += log_loss_lignes(dist, total)
            mae += abs(100 * a - sg) + abs(100 * b - sp)
        n = len(obs)
        out[d] = {'n': n, 'log_loss_lignes': round(ll / n, 5) if n else None,
                  'ecart_pts_service': round(mae / (2 * n), 3) if n else None}
    return out


def diagnostic(obs):
    """À δ = 0 : service prévu / réel (%), jeux prévus / réels, « plus de 20,5 jeux » prévu / réel."""
    n = len(obs)
    if not n:
        return {'n': 0}
    sp = sr = jp = jr = op = orr = 0.0
    for cg, cp, p_elo, total, sg, spp, *_ in obs:
        dist, a, b = distribution(cg, cp, p_elo, 0.0)
        sp += 50 * (a + b)
        sr += (sg + spp) / 2
        tot = sum(dist.values())
        jp += sum(k * v for k, v in dist.items()) / tot
        jr += total
        op += sum(v for k, v in dist.items() if k > 20.5) / tot
        orr += total > 20.5
    r = lambda x: round(x / n, 2)
    return {'n': n, 'service_prevu': r(sp), 'service_reel': r(sr), 'ecart_service': round((sr - sp) / n, 2),
            'jeux_prevus': r(jp), 'jeux_reels': r(jr), 'plus_20_5_prevu': round(100 * op / n, 1),
            'plus_20_5_reel': round(100 * orr / n, 1)}


def court(sol):
    s = str(sol or '').lower()
    if 'clay' in s:
        return 'terre'
    if 'indoor' in s or 'carpet' in s:
        return 'dur intérieur'
    if 'hard' in s:
        return 'dur extérieur'
    return 'autre'


def decider(app, jug_arch, jug_feuilles, delta):
    """Règle de l'en-tête, appliquée telle quelle."""
    if delta == 0.0:
        return False, "l'apprentissage 2018–2022 garde δ = 0 : rien à corriger"
    a0, a1 = jug_arch[0.0], jug_arch[delta]
    f0, f1 = jug_feuilles.get(0.0), jug_feuilles.get(delta)
    if a0['n'] < N_MIN:
        return False, f"jugement archive trop petit ({a0['n']} matchs < {N_MIN})"
    gain_a = a0['log_loss_lignes'] - a1['log_loss_lignes']
    gain_f = (f0['log_loss_lignes'] - f1['log_loss_lignes']) if f0 and f0['n'] else None
    raisons = []
    if gain_a < GAIN_MIN:
        raisons.append(f"gain archive {gain_a:+.4f} < {GAIN_MIN}")
    if gain_f is None or gain_f <= 0:
        raisons.append(f"feuilles TennisApi : gain {gain_f if gain_f is None else round(gain_f, 4)} (même sens exigé)")
    if a1['ecart_pts_service'] > TOL_MAE * a0['ecart_pts_service']:
        raisons.append("écart % points au service dégradé (archive)")
    if f0 and f0['n'] and f1['ecart_pts_service'] > TOL_MAE * f0['ecart_pts_service']:
        raisons.append("écart % points au service dégradé (feuilles)")
    if raisons:
        return False, ' ; '.join(raisons)
    return True, (f"δ = {delta:+.3f} : log loss des lignes {gain_a:+.4f} (archive 2023 → 05/2026, {a0['n']} matchs), "
                  f"{gain_f:+.4f} (feuilles TennisApi, {f0['n']} matchs)")


def pct_service(d):
    """Feuille Sackmann [svpt, 1stIn, 1stWon, 2ndWon, ace, df, …] -> % de points gagnés au service."""
    return 100 * (d[2] + d[3]) / d[0] if d and d[0] else None


def main(argv):
    t0 = time.time()
    args = [a for a in argv[1:] if not a.startswith('--')]
    opt = {a.split('=')[0]: a.split('=')[1] for a in argv[1:] if a.startswith('--') and '=' in a}
    n_max = int(opt.get('--max', 3000))
    dossier = args[0] if args else 'sackmann'
    racine = args[1] if len(args) > 1 else os.path.join(ICI, '..')
    M = donnees.charger(dossier, 2016)
    if not M:
        print(f"::error::aucun match Sackmann sous {dossier}")
        return 1
    fin_sack = max(m['date'] for m in M)
    F = [m for m in FE.charger(racine) if m['date'] > fin_sack]
    tout = sorted(M + F, key=lambda m: (m['date'], m['tour'], m['num']))
    try:
        with open(os.path.join(ICI, 'choix_simulation.json'), encoding='utf-8') as f:
            choix = json.load(f)
    except (OSError, ValueError):
        choix = {}
    ajustees = choix.get('composantes', 'ajustees') == 'ajustees'
    n0 = float(choix.get('n0') or AJ.N0)
    n0_comp = choix.get('n0_par_composante') or None
    dyn = AJ.lire_dynamique(choix)
    elo, bas = E.de_production(racine)          # Elo réglé comme la production, mis à jour après chaque match
    P, attente = PS.Profils(), []
    adj, mois_adj = None, None
    groupes = {'app': [], 'jug': [], 'feuilles': []}
    for i, m in enumerate(tout):
        while attente and attente[0][0] < m['date']:
            _, j = heapq.heappop(attente)
            P.ajouter(tout[j], E.cle(tout[j]['nom_g']), E.cle(tout[j]['nom_p']))
        g, p = E.cle(m['nom_g']), E.cle(m['nom_p'])
        for k in (g, p):
            if bas and m['circuit'] in BAS:
                elo.presenter(k, bas)
        p_elo = elo.proba(g, p, m['surface'])
        det = m.get('detail')
        if (det and m['complet'] and not m.get('abandon') and m['circuit'] == 'CH' and m['bo'] == 3 and m['date'] >= APP[0]):
            grp = ('feuilles' if m.get('source') == 'tennisapi' else
                   'app' if m['date'] < APP[1] else 'jug' if m['date'] < JUG[1] else None)
            total = sum(a + b for a, b in m['sets'] if a >= 0 and b >= 0)
            sg, sp = pct_service(det['w']), pct_service(det['l'])
            if grp and total and sg is not None and sp is not None:
                pg, _ = P.profil(g, m['circuit'], m['surface'], m['date'])
                pp, _ = P.profil(p, m['circuit'], m['surface'], m['date'])
                mu = P.moyenne(m['circuit'], m['surface'])
                cg, cp = S.composantes(pg, pp, mu), S.composantes(pp, pg, mu)
                if ajustees:
                    debut_mois = m['date'].replace(day=1)
                    if mois_adj != debut_mois:
                        adj = AJ.ajuster_choisi(tout, debut_mois, E.cle, n0=n0, dyn=dyn, depart=adj,
                                                tours=6 if adj is None else 2, n0_par_composante=n0_comp)
                        mois_adj = debut_mois
                    cg = S.composantes_ajustees(adj, g, p, m['circuit'], m['surface'])
                    cp = S.composantes_ajustees(adj, p, g, m['circuit'], m['surface'])
                groupes[grp].append((cg, cp, p_elo, total, sg, sp, m['date'], m.get('sol_brut') or m['surface']))
        if det:
            heapq.heappush(attente, (m['fin'], i))
        elo.maj(g, p, m['surface'], m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') else None)
    print(f"Challenger : apprentissage {len(groupes['app'])} · jugement archive {len(groupes['jug'])} · "
          f"feuilles TennisApi {len(groupes['feuilles'])} ({round(time.time() - t0)} s)", flush=True)

    def echantillon(obs):
        pas = max(1, len(obs) // n_max)
        return obs[::pas][:n_max]
    app = evaluer(echantillon(groupes['app']), GRILLE)
    delta = min(app, key=lambda d: (app[d]['log_loss_lignes'], abs(d)))
    jug_a = evaluer(echantillon(groupes['jug']), sorted({0.0, delta}))
    jug_f = evaluer(echantillon(groupes['feuilles']), sorted({0.0, delta})) if groupes['feuilles'] else {}
    ok, raison = decider(app, jug_a, jug_f, delta)
    diag = {'apprentissage': diagnostic(echantillon(groupes['app'])), 'jugement_archive': diagnostic(echantillon(groupes['jug'])),
            'feuilles': diagnostic(groupes['feuilles'])}
    par_mois, par_court = {}, {}
    for o in groupes['feuilles']:
        par_mois.setdefault(o[6].strftime('%Y-%m'), []).append(o)
        par_court.setdefault(court(o[7]), []).append(o)
    diag['feuilles_par_mois'] = {k: diagnostic(v) for k, v in sorted(par_mois.items())}
    diag['feuilles_par_court'] = {k: diagnostic(v) for k, v in sorted(par_court.items())}
    for k, v in diag.items():
        if 'n' in v:
            print(f"  {k} : {v}")
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("δ commun au service des deux joueurs en Challenger, réancré sur la probabilité de victoire ; appris "
                     "2018–2022 (log loss des lignes « plus de 18,5 … 23,5 jeux ») ; retenu si la log loss baisse d'au moins "
                     "0,001 sur ≥ 1 000 matchs 2023 → 05/2026, baisse aussi sur les feuilles TennisApi, et si l'écart du % "
                     "de points au service ne monte pas de plus de 1 %"),
           'delta_appris': delta, 'retenu': ok, 'raison': raison,
           'apprentissage': {str(k): v for k, v in app.items()},
           'jugement_archive': {str(k): v for k, v in jug_a.items()},
           'jugement_feuilles': {str(k): v for k, v in jug_f.items()},
           'matchs': {k: len(v) for k, v in groupes.items()},
           'diagnostic': diag,
           'duree_s': round(time.time() - t0)}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"{'RETENU' if ok else 'NON RETENU'} — {raison}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
