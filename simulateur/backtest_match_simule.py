#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_match_simule.py — la feuille de match simulée AVANT l'heure tient-elle la route ? (22/10/2026)

Sur les matchs ATP/WTA du 01/01/2024 au 01/02/2026 qui ont une feuille de
match complète (archive Sackmann) et une clôture Pinnacle (tennis-data), on
simule chaque match AVANT de le regarder :
  — profils de service des deux joueurs : uniquement les tournois TERMINÉS
    avant le match (point-in-time) ;
  — niveau : « stats seules » = Elo du même rejeu chronologique que
    backtest_pronostic ; « stats + marché » = Pinnacle sans marge ;
  — un contrôle « joueurs moyens » : même niveau (Pinnacle), mais les deux
    joueurs ont le profil moyen du circuit — mesure ce que les profils apportent.
Puis on compare à la feuille réelle, statistique par statistique (aces,
doubles fautes, % de 1re balle, points gagnés derrière la 1re et la 2e balle,
balles de break obtenues, breaks, jeux) :
  — erreur moyenne (MAE) de la valeur prévue, contre une référence naïve (la
    moyenne du circuit sur 2016–2023, même format de match) ;
  — biais (prévu − réel) ;
  — couverture de la fourchette à 80 % (10e–90e centile des simulations) :
    bien réglée si le réel y tombe ~80 % du temps ;
  — calibration des aces et des breaks par quintile de la valeur prévue.
Rien n'est réglé sur ces résultats : profils, forme du jour (σ = 0,15) et
moteur sont ceux des pronostics.

Usage : python simulateur/backtest_match_simule.py <archive Sackmann> [racine] [--n 300] [--max 2000]
Sortie : simulateur/rapport_match_simule.json
"""
import collections
import datetime as dt
import heapq
import json
import math
import os
import statistics
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import backtest_pronostic as BP  # noqa: E402
import donnees  # noqa: E402
import elo as E  # noqa: E402
import match_simule as S  # noqa: E402
import profils_service as PS  # noqa: E402
import ajustement as AJ  # noqa: E402

SORTIE = os.path.join(ICI, 'rapport_match_simule.json')
CHOIX = os.path.join(ICI, 'choix_simulation.json')
SIGMA = 0.15
STATS = ('aces', 'doubles_fautes', 'premiere_pct', 'gagnes_1re_pct', 'gagnes_2e_pct',
         'balles_break_obtenues', 'breaks', 'jeux')
LIBELLES = {'aces': 'Aces', 'doubles_fautes': 'Doubles fautes', 'premiere_pct': '% de 1re balle',
            'gagnes_1re_pct': '% gagnés derrière la 1re', 'gagnes_2e_pct': '% gagnés derrière la 2e',
            'balles_break_obtenues': 'Balles de break obtenues', 'breaks': 'Breaks réussis', 'jeux': 'Jeux gagnés',
            'total_jeux': 'Total de jeux du match'}


def reel(m):
    """Feuilles réelles (gagnant, perdant) au format de match_simule.feuille_derivee + total de jeux."""
    (sv, in1, w1, w2, ace, df, bpf, bps, sg), (osv, oin1, ow1, ow2, oace, odf, obpf, obps, osg) = m['detail']['w'], m['detail']['l']
    jg = sum(a for a, b in m['sets'])
    jp = sum(b for a, b in m['sets'])

    def f(sv, in1, w1, w2, ace, df, obpf, obps, jeux):
        return {'aces': ace, 'doubles_fautes': df, 'premiere_pct': 100 * in1 / sv,
                'gagnes_1re_pct': 100 * w1 / in1, 'gagnes_2e_pct': 100 * w2 / (sv - in1),
                'balles_break_obtenues': obpf, 'breaks': obpf - obps, 'jeux': jeux}
    return (f(sv, in1, w1, w2, ace, df, obpf, obps, jg), f(osv, oin1, ow1, ow2, oace, odf, bpf, bps, jp)), jg + jp


def bilan_victoire(L):
    """L : probabilité donnée au vrai vainqueur. Réussite (½ si 50 %), log loss, Brier, calibration."""
    n = len(L)
    if not n:
        return {'n': 0}
    ok = sum(1.0 if p > 0.5 else 0.5 if p == 0.5 else 0.0 for p in L)
    ll = -sum(math.log(min(max(p, 1e-6), 1 - 1e-6)) for p in L) / n
    br = sum((1 - p) ** 2 for p in L) / n
    # calibration sur le FAVORI annoncé (probabilité ≥ 50 %)
    cal = []
    for lo in range(50, 100, 10):
        g = [(max(p, 1 - p), p >= 0.5) for p in L if lo <= 100 * max(p, 1 - p) < lo + 10]
        if g:
            cal.append({'tranche': f"{lo}–{lo + 10} %", 'n': len(g), 'prevu': round(100 * sum(x for x, _ in g) / len(g), 1),
                        'reel': round(100 * sum(w for _, w in g) / len(g), 1)})
    return {'n': n, 'reussite_pct': round(100 * ok / n, 1), 'log_loss': round(ll, 4), 'brier': round(br, 4), 'calibration': cal}


class Suivi:
    """Accumule prévu / réel / fourchette par statistique."""

    def __init__(self):
        self.L = collections.defaultdict(list)

    def ajouter(self, stat, prevu, p10, p90, vrai, naif):
        self.L[stat].append((prevu, p10, p90, vrai, naif))

    def rapport(self):
        out = {}
        for k, L in self.L.items():
            n = len(L)
            mae = sum(abs(p - v) for p, _, _, v, _ in L) / n
            mae_n = sum(abs(z - v) for _, _, _, v, z in L) / n
            cov = sum(lo <= v <= hi for _, lo, hi, v, _ in L) / n
            pr, vr = [x[0] for x in L], [x[3] for x in L]
            cor = statistics.correlation(pr, vr) if n > 2 and len(set(pr)) > 1 and len(set(vr)) > 1 else None
            out[k] = {'libelle': LIBELLES.get(k, k), 'n': n, 'prevu_moy': round(sum(pr) / n, 2), 'reel_moy': round(sum(vr) / n, 2),
                      'mae': round(mae, 3), 'mae_naif': round(mae_n, 3),
                      'gain_vs_naif_pct': round(100 * (1 - mae / mae_n), 1) if mae_n else None,
                      'correlation': round(cor, 3) if cor is not None else None,
                      'couverture_80_pct': round(100 * cov, 1),
                      'sous_p10_pct': round(100 * sum(v < lo for _, lo, _, v, _ in L) / n, 1),
                      'au_dessus_p90_pct': round(100 * sum(v > hi for _, _, hi, v, _ in L) / n, 1)}
        return out

    def calibration(self, stat, k=5):
        L = sorted(self.L.get(stat, []))
        if len(L) < 5 * k:
            return []
        out = []
        for q in range(k):
            g = L[q * len(L) // k:(q + 1) * len(L) // k]
            out.append({'quintile': q + 1, 'n': len(g), 'prevu': round(sum(x[0] for x in g) / len(g), 2),
                        'reel': round(sum(x[3] for x in g) / len(g), 2)})
        return out


# ------------------------------------------------------------------ point 1 : combinaison simulation + Elo
DEBUT_JUGE_COMB = dt.date(2025, 1, 1)       # apprise sur 2024, jugée du 01/01/2025 au 01/02/2026


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def ajuster_poids(X, ridge=1.0, tours=30):
    """Régression logistique sans constante, symétrique (chaque match vu des deux côtés) :
    X = [[z_1, z_2, …] du vrai vainqueur]. Renvoie les poids."""
    k = len(X[0])
    b = [1.0 / k] * k
    for _ in range(tours):
        g = [-ridge * (bj - 1.0 / k) for bj in b]
        H = [[-ridge * (i == j) for j in range(k)] for i in range(k)]
        for x in X:
            for sgn, y in ((1, 1), (-1, 0)):
                xs = [sgn * v for v in x]
                p = 1 / (1 + math.exp(-max(min(sum(bj * v for bj, v in zip(b, xs)), 30), -30)))
                for i in range(k):
                    g[i] += (y - p) * xs[i]
                    for j in range(k):
                        H[i][j] -= p * (1 - p) * xs[i] * xs[j]
        # Newton : b ← b − H⁻¹ g (petit système, élimination de Gauss)
        A = [row[:] + [g[i]] for i, row in enumerate(H)]
        for c in range(k):
            piv = max(range(c, k), key=lambda r: abs(A[r][c]))
            A[c], A[piv] = A[piv], A[c]
            for r in range(k):
                if r != c and A[c][c]:
                    f = A[r][c] / A[c][c]
                    A[r] = [a - f * cc for a, cc in zip(A[r], A[c])]
        d = [A[i][k] / A[i][i] if abs(A[i][i]) > 1e-12 else 0.0 for i in range(k)]
        b = [bj - dj for bj, dj in zip(b, d)]
        if max(abs(x) for x in d) < 1e-9:
            break
    return b


melange = S.melange
GRILLE_SIGMA = (0.0, 0.05, 0.10, 0.15)
GRILLE_AMPLIFICATION = (1.0, 1.15, 1.3, 1.5)


def _ll(L):
    return -sum(math.log(min(max(p, 1e-6), 1 - 1e-6)) for p in L) / len(L) if L else None


EXPLORATEUR = 'Tennis_Edge_Lab/live/explorateur_pronostics.json.gz'


def exporter_explorateur(L, sim, cb, chemin):
    """Point 3 (22/10/2026) : tous les matchs ATP/WTA 2024 → 01/2026 rejoués avant l'heure, avec les
    % donnés AU VRAI VAINQUEUR par chaque version et les critères (circuit, surface, format, tour, niveau,
    expérience) — pour croiser les résultats de l'algorithme avec tous les critères dans le Lab."""
    import gzip
    P = cb.get('poids') or cb.get('poids_appris_2024')
    cols = ['date', 'circuit', 'surface', 'bo', 'tour', 'niveau', 'tournoi', 'gagnant', 'perdant', 'matchs_min',
            'elo', 'simulation', 'combinaison', 'pinnacle']
    rows = []
    for x in L:
        c = melange(P, x['elo'], x[sim]) if P else None
        rows.append([x['date'].isoformat(), x['circuit'], x.get('surface'), x.get('bo'), x.get('tour'), x.get('niveau'),
                     x.get('tournoi'), x.get('gagnant'), x.get('perdant'), x.get('matchs_min'),
                     round(x['elo'], 4), round(x[sim], 4), round(c, 4) if c is not None else None, round(x['pinnacle'], 4)])
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'colonnes': cols,
           'lecture': "probabilités données au VRAI vainqueur : > 0,5 = vainqueur trouvé", 'simulation': sim,
           'debut_jugement': DEBUT_JUGE_COMB.isoformat(), 'lignes': rows}
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with gzip.open(chemin, 'wt', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))


def choisir_reglage(L):
    """Règle fixée d'avance (22/10/2026) : (σ, k) de plus petite log loss du vainqueur sur 2024 ; adopté
    s'il fait mieux que le réglage actuel (σ = 0,15, k = 1) sur 2025 →."""
    appr = [x for x in L if x['date'] < DEBUT_JUGE_COMB]
    juge = [x for x in L if x['date'] >= DEBUT_JUGE_COMB]
    if len(appr) < 300 or len(juge) < 300:
        return {'adopte': False, 'sigma': 0.15, 'amplification': 1.0, 'cle': '0.15|1', 'raison': 'pas assez de matchs'}
    cles = list(appr[0]['grille'])
    sc = {k: _ll([x['grille'][k] for x in appr]) for k in cles}
    best = min(sc, key=sc.get)
    actuel = '0.15|1'
    jb, ja = _ll([x['grille'][best] for x in juge]), _ll([x['grille'][actuel] for x in juge])
    rb = bilan_victoire([x['grille'][best] for x in juge])
    ra = bilan_victoire([x['grille'][actuel] for x in juge])
    s_, k_ = best.split('|')
    return {'adopte': best != actuel and jb < ja, 'sigma': float(s_), 'amplification': float(k_), 'cle': best,
            'grille_2024': {k: round(v, 5) for k, v in sorted(sc.items(), key=lambda kv: kv[1])},
            'jugement': {'choisi': rb, 'actuel': ra},
            'raison': (f"choisi sur 2024 : σ = {s_}, k = {k_} ; 2025 → : log loss {round(jb, 4)} contre {round(ja, 4)} "
                       f"(réussite {rb.get('reussite_pct')} % contre {ra.get('reussite_pct')} %, calibration "
                       + ' · '.join(f"{c['tranche']} {c['prevu']}→{c['reel']}" for c in rb.get('calibration', [])) + ")")}


def combinaison(L, sim):
    """Règle fixée d'avance (22/10/2026) : poids appris sur 2024, jugés sur 2025 → ; la combinaison est
    adoptée si sa log loss sur le jugement est plus basse que celle de l'Elo ET de la simulation seuls.
    Si adoptée, les poids des pronostics sont ré-appris sur toute la période."""
    appr = [x for x in L if x['date'] < DEBUT_JUGE_COMB]
    juge = [x for x in L if x['date'] >= DEBUT_JUGE_COMB]
    out = {'simulation': sim, 'apprentissage': len(appr), 'jugement_n': len(juge)}
    if len(appr) < 300 or len(juge) < 300:
        return dict(out, adopte=False, poids=None, jugement={}, raison='pas assez de matchs')
    w = ajuster_poids([[_lg(x['elo']), _lg(x[sim])] for x in appr])
    w1 = ajuster_poids([[_lg(x['elo'])] for x in appr], ridge=0.0)
    w2 = ajuster_poids([[_lg(x[sim])] for x in appr], ridge=0.0)      # la simulation seule, confiance recalée
    P = {'elo': w[0], 'simulation': w[1]}
    J = {'elo': bilan_victoire([x['elo'] for x in juge]),
         'simulation': bilan_victoire([x[sim] for x in juge]),
         'elo_recalibre': bilan_victoire([1 / (1 + math.exp(-w1[0] * _lg(x['elo']))) for x in juge]),
         'simulation_recalibree': bilan_victoire([1 / (1 + math.exp(-w2[0] * _lg(x[sim]))) for x in juge]),
         'combinaison': bilan_victoire([melange(P, x['elo'], x[sim]) for x in juge]),
         'pinnacle': bilan_victoire([x['pinnacle'] for x in juge])}
    ok = J['combinaison']['log_loss'] < min(J['elo']['log_loss'], J['simulation']['log_loss'])
    final = P
    if ok:
        wa = ajuster_poids([[_lg(x['elo']), _lg(x[sim])] for x in L])
        final = {'elo': wa[0], 'simulation': wa[1]}
    return dict(out, adopte=ok, poids={k: round(v, 4) for k, v in final.items()},
                poids_appris_2024={k: round(v, 4) for k, v in P.items()}, elo_recalibre_coef=round(w1[0], 4),
                simulation_recalibree_coef=round(w2[0], 4),
                jugement=J,
                raison=(f"log loss 2025 → : combinaison {J['combinaison']['log_loss']} contre Elo {J['elo']['log_loss']} "
                        f"et simulation {J['simulation']['log_loss']} (Pinnacle {J['pinnacle']['log_loss']})"))


def calibration_detaillee(L, sim, cb):
    """Point 9 : où le modèle se trompe de confiance — par circuit et selon l'expérience des joueurs."""
    P = cb.get('poids_appris_2024')
    juge = [x for x in L if x['date'] >= DEBUT_JUGE_COMB]
    grp = {'tous (2025 →)': juge, 'ATP': [x for x in juge if x['circuit'] == 'ATP'], 'WTA': [x for x in juge if x['circuit'] == 'WTA'],
           'un joueur à moins de 30 matchs': [x for x in juge if x['connus'] < 30],
           'deux joueurs à 30 matchs ou plus': [x for x in juge if x['connus'] >= 30]}
    out = {}
    for nom, g in grp.items():
        d = {'elo': bilan_victoire([x['elo'] for x in g]), 'simulation': bilan_victoire([x[sim] for x in g]),
             'pinnacle': bilan_victoire([x['pinnacle'] for x in g])}
        if P:
            d['combinaison'] = bilan_victoire([melange(P, x['elo'], x[sim]) for x in g])
        out[nom] = d
    return out


def main(argv):
    t0 = time.time()
    args = [a for a in argv[1:] if not a.startswith('--')]
    opt = {a.split('=')[0]: a.split('=')[1] for a in argv[1:] if a.startswith('--') and '=' in a}
    n_sim = int(opt.get('--n', 300))
    n_max = int(opt.get('--max', 2000))
    dossier = args[0] if args else 'sackmann'
    racine = args[1] if len(args) > 1 else os.path.join(ICI, '..')
    td_chemin = opt.get('--td') or os.path.join(racine, 'historique', 'tennis_data.csv.gz')
    M = donnees.charger(dossier, 2016)
    if not M:
        print(f"::error::aucun match Sackmann sous {dossier}")
        return 1
    print(f"Sackmann : {len(M)} matchs, {sum(1 for m in M if m.get('detail'))} avec feuille complète", flush=True)
    td = donnees.charger_td(td_chemin, BP.DEBUT_A.isoformat())
    pin = {}
    for t, m in donnees.joindre(td, M):
        pin[id(m)] = BP.juste(t['psw'], t['psl'])
    print(f"Clôtures Pinnacle jointes : {len(pin)}", flush=True)
    try:                                                   # options de l'Elo retenues par backtest_pronostic
        with open(os.path.join(ICI, 'elo_etat.json'), encoding='utf-8') as f:
            opts_elo = json.load(f).get('options')
    except (OSError, ValueError):
        opts_elo = None
    V = BP.rejouer(M, [], [], E.cle, {}, True, options=opts_elo)   # Elo point-in-time (départ 1200 aux petits niveaux)
    print(f"Elo rejoué ({round(time.time() - t0)} s)", flush=True)

    # Référence naïve : moyenne 2016–2023 par circuit et format (tous joueurs).
    naif_s = collections.defaultdict(lambda: collections.defaultdict(list))
    for m in M:
        if m['date'] < BP.DEBUT_A and m.get('detail') and m['complet'] and m['circuit'] in ('ATP', 'WTA'):
            (fw, fl), tot = reel(m)
            for f in (fw, fl):
                for k in STATS:
                    naif_s[(m['circuit'], m['bo'])][k].append(f[k])
            naif_s[(m['circuit'], m['bo'])]['total_jeux'].append(tot)
    naif = {g: {k: sum(v) / len(v) for k, v in d.items()} for g, d in naif_s.items()}

    elig = [i for i, m in enumerate(M) if BP.DEBUT_A <= m['date'] < BP.FIN_A and m['circuit'] in ('ATP', 'WTA')
            and m.get('detail') and m['complet'] and id(m) in pin and i in V['pred_sack'] and (m['circuit'], m['bo']) in naif]
    pas = max(1, len(elig) // n_max)
    choisis = set(elig[::pas][:n_max])
    elig_set = set(elig)
    LIGNES = []      # 22/10/2026 : TOUS les matchs éligibles (vainqueur seul, limite exacte) → combinaison, calibration
    print(f"Matchs éligibles : {len(elig)} · simulés : {len(choisis)} × {n_sim} fois × 5 versions", flush=True)

    P = PS.Profils()
    attente = []
    R = {v: Suivi() for v in ('simulation_pure_ajustee', 'simulation_pure', 'stats_seules', 'stats_plus_marche', 'joueurs_moyens')}
    VIC = {'simulation_pure_ajustee': [], 'simulation_pure': [], 'elo': [], 'pinnacle': []}   # proba donnée au vrai vainqueur
    adj, mois_adj = None, None                                    # ajustement aux adversaires, refait chaque mois
    try:
        with open(CHOIX, encoding='utf-8') as f:
            choix_avant = json.load(f)
    except (OSError, ValueError):
        choix_avant = {}
    dyn = AJ.lire_dynamique(choix_avant)                             # réglage « dans le temps » s'il a été adopté
    n0, scores_n0 = AJ.choisir_n0(M, E.cle)                         # prior choisi sur 2023 seulement
    print(f"Prior de l'ajustement aux adversaires retenu sur 2023 : N0 = {n0:g}", flush=True)
    connus = collections.Counter()
    for i, m in enumerate(M):
        while attente and attente[0][0] < m['date']:
            _, j = heapq.heappop(attente)
            P.ajouter(M[j], E.cle(M[j]['nom_g']), E.cle(M[j]['nom_p']))
        if m.get('detail'):
            heapq.heappush(attente, (m['fin'], i))
        if i not in elig_set:
            continue
        g, p = E.cle(m['nom_g']), E.cle(m['nom_p'])
        pg, ng = P.profil(g, m['circuit'], m['surface'], m['date'])
        pp, np_ = P.profil(p, m['circuit'], m['surface'], m['date'])
        mu = P.moyenne(m['circuit'], m['surface'])
        sg = 3 if m['bo'] == 5 else 2
        cg, cp = S.composantes(pg, pp, mu), S.composantes(pp, pg, mu)
        cmu = S.composantes(mu, mu, mu)
        debut_mois = m['date'].replace(day=1)
        if mois_adj != debut_mois:                                 # point-in-time : tournois finis avant le 1er du mois
            t1 = time.time()
            adj = AJ.ajuster_choisi(M, debut_mois, E.cle, n0=n0, dyn=dyn, depart=adj, tours=6 if adj is None else 2)
            mois_adj = debut_mois
            print(f"  ajustement aux adversaires au {debut_mois} ({round(time.time() - t1)} s)", flush=True)
        ag, ap = S.composantes_ajustees(adj, g, p, m['circuit'], m['surface']), S.composantes_ajustees(adj, p, g, m['circuit'], m['surface'])
        moy = S.borner(adj.taux('__moyen__', '__moyen__', m['circuit'], m['surface']))
        grille = {}
        for k_amp in GRILLE_AMPLIFICATION:
            a2, p2 = S.amplifier(ag, moy, k_amp), S.amplifier(ap, moy, k_amp)
            for s_ in GRILLE_SIGMA:
                grille[f"{s_:g}|{k_amp:g}"] = S.victoire_pure(a2, p2, sg, s_)
        LIGNES.append({'date': m['date'], 'circuit': m['circuit'], 'connus': V['pred_sack'][i][1],
                       'elo': V['pred_sack'][i][0], 'pinnacle': pin[id(m)],
                       'simulation_pure_ajustee': grille[f"{SIGMA:g}|1"],
                       'simulation_pure': S.victoire_pure(cg, cp, sg, SIGMA), 'grille': grille,
                       # pour l'explorateur des pronostics (point 3, 22/10/2026)
                       'surface': m['surface'], 'bo': m['bo'], 'tour': m.get('tour'), 'niveau': m.get('niveau'),
                       'tournoi': m.get('tournoi'), 'gagnant': m['nom_g'], 'perdant': m['nom_p'],
                       'matchs_min': V['pred_sack'][i][1]})
        if i not in choisis:
            continue
        connus[min(ng, np_) >= 500] += 1
        for k in VIC:
            VIC[k].append(LIGNES[-1][k])
        (fw, fl), tot = reel(m)
        nz = naif[(m['circuit'], m['bo'])]
        for version, (ca, cb, pv) in (('simulation_pure_ajustee', (ag, ap, None)),
                                      ('simulation_pure', (cg, cp, None)),
                                      ('stats_seules', (cg, cp, V['pred_sack'][i][0])),
                                      ('stats_plus_marche', (cg, cp, pin[id(m)])),
                                      ('joueurs_moyens', (cmu, cmu, pin[id(m)]))):
            r = S.simuler(ca, cb, pv, sg, n_sim, SIGMA, cle=f"{i}|{version}")
            for k_j, vrai in ((0, fw), (1, fl)):
                for k in STATS:
                    x = r['feuille'][k_j][k]
                    if x:
                        R[version].ajouter(k, x['moy'], x['p10'], x['p90'], vrai[k], nz[k])
            R[version].ajouter('total_jeux', r['jeux']['moy'], r['jeux']['p10'], r['jeux']['p90'], tot, nz['total_jeux'])
        if len(R['stats_plus_marche'].L['aces']) % 400 == 0:
            print(f"  {len(R['stats_plus_marche'].L['aces']) // 2} matchs ({round(time.time() - t0)} s)", flush=True)

    rap = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'periode': f"{BP.DEBUT_A} → {BP.FIN_A}", 'matchs_simules': len(choisis), 'simulations_par_match': n_sim,
           'joueurs_avec_500_balles_de_service': dict(connus),
           'methode': ("Profils de service point-in-time (tournois terminés avant le match), niveau ancré sur Elo ou "
                       "Pinnacle, forme du jour σ = 0,15. Référence naïve : moyenne du circuit 2016–2023, même format. "
                       "Fourchette 80 % = 10e–90e centile des simulations, bornes incluses : pour un compte entier "
                       "(aces, breaks…) la couverture dépasse naturellement 80 % ; lire aussi « sous p10 » et "
                       "« au-dessus p90 », qui doivent rester proches de 10 % chacun ou en dessous."),
           'versions': {v: s.rapport() for v, s in R.items()},
           'victoire': {v: bilan_victoire(L) for v, L in VIC.items()},
           'victoire_lecture': ("simulation_pure : le match joué avec les seuls taux des deux joueurs (1re balle, aces, "
                                "doubles fautes, points gagnés derrière la 1re et la 2e, qualité de retour), sans Elo ni "
                                "cote : c'est la simulation qui désigne le vainqueur. elo / pinnacle : références."),
           'calibration': {v: {k: s.calibration(k) for k in ('aces', 'doubles_fautes', 'breaks')} for v, s in R.items()},
           'duree_s': round(time.time() - t0)}
    rap['victoire_tous_les_matchs'] = {v: bilan_victoire([x[v] for x in LIGNES]) for v in VIC}
    # Règle fixée d'avance (22/10/2026) : les statistiques AJUSTÉES aux adversaires remplacent les profils
    # bruts dans les pronostics si la simulation pure ajustée trouve mieux le vainqueur (log loss plus basse),
    # sur TOUS les matchs éligibles (limite exacte de la simulation, pas seulement les matchs simulés).
    va, vp = rap['victoire_tous_les_matchs']['simulation_pure_ajustee'], rap['victoire_tous_les_matchs']['simulation_pure']
    ok = bool(va.get('n')) and va['log_loss'] < vp['log_loss']
    rap['choix'] = {'composantes': 'ajustees' if ok else 'profils', 'n0': n0,
                    'n0_choisi_sur_2023': {f"{k:g}": round(v, 5) for k, v in scores_n0.items()},
                    'raison': (f"log loss de la simulation pure : ajustée {va.get('log_loss')} contre profils bruts "
                               f"{vp.get('log_loss')} (réussite {va.get('reussite_pct')} % contre {vp.get('reussite_pct')} %)")}
    sim = 'simulation_pure_ajustee' if ok else 'simulation_pure'
    # 22/10/2026 — réglage de la simulation pure (forme du jour σ, amplification k des écarts au circuit),
    # choisi sur 2024, adopté s'il trouve mieux le vainqueur en 2025 → ; la combinaison est ensuite
    # ré-apprise avec la simulation réglée (son poids monte si elle trouve mieux).
    if ok:
        rap['reglage_simulation'] = choisir_reglage(LIGNES)
        rg = rap['reglage_simulation']
        if rg['adopte']:
            for x in LIGNES:
                x['simulation_reglee'] = x['grille'][rg['cle']]
            sim = 'simulation_reglee'
        rap['choix']['reglage_simulation'] = {k: rg[k] for k in ('adopte', 'sigma', 'amplification', 'raison')}
        print(f"\nRéglage de la simulation (choisi sur 2024, jugé 2025 →) : {'ADOPTÉ' if rg['adopte'] else 'non adopté'} — {rg['raison']}")
    rap['combinaison'] = combinaison(LIGNES, sim)
    rap['calibration_detaillee'] = calibration_detaillee(LIGNES, sim, rap['combinaison'])
    exporter_explorateur(LIGNES, sim, rap['combinaison'], os.path.join(ICI, '..', EXPLORATEUR))
    rap['choix']['combinaison'] = {k: rap['combinaison'][k] for k in ('adopte', 'poids', 'raison', 'simulation')}
    with open(CHOIX, 'w', encoding='utf-8') as f:            # les autres décisions (ex. « dynamique ») sont gardées
        json.dump(dict(choix_avant, **rap['choix'], genere_le=rap['genere_le']), f, ensure_ascii=False, indent=1)
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    print("\nQui gagne ? (probabilité donnée au vrai vainqueur)")
    for v, x in rap['victoire'].items():
        print(f"  {v:<16} réussite {x.get('reussite_pct')} % · log loss {x.get('log_loss')} · Brier {x.get('brier')}")
    print(f"\nChoix pour les pronostics : {rap['choix']['composantes']} — {rap['choix']['raison']}")
    cb = rap['combinaison']
    print(f"\nCombinaison simulation + Elo (apprise sur 2024, jugée 2025 →) : {'ADOPTÉE' if cb['adopte'] else 'non adoptée'}"
          f" — {cb['raison']} · poids {cb['poids']}")
    for v, x in cb['jugement'].items():
        print(f"  {v:<22} réussite {x.get('reussite_pct')} % · log loss {x.get('log_loss')} · Brier {x.get('brier')} (n {x.get('n')})")
    print("\nCalibration (favori annoncé : prévu → réel)")
    for grp, d in rap['calibration_detaillee'].items():
        for v, x in d.items():
            print(f"  {grp:<28} {v:<12} n {x.get('n')} · " + ' · '.join(f"{c['tranche']} {c['prevu']}→{c['reel']}" for c in x.get('calibration', [])))
    for v in ('simulation_pure_ajustee', 'simulation_pure', 'stats_plus_marche', 'joueurs_moyens', 'stats_seules'):
        print(f"\n{v}")
        for k, x in rap['versions'][v].items():
            print(f"  {x['libelle']:<28} prévu {x['prevu_moy']:>6} réel {x['reel_moy']:>6} · MAE {x['mae']:>6} "
                  f"(naïf {x['mae_naif']}) gain {x['gain_vs_naif_pct']} % · corr {x['correlation']} · couverture 80 % : {x['couverture_80_pct']} %")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
