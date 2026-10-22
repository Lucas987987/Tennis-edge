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

SORTIE = os.path.join(ICI, 'rapport_match_simule.json')
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
    V = BP.rejouer(M, [], [], E.cle, {}, True)            # Elo point-in-time (départ 1200 aux petits niveaux)
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
    print(f"Matchs éligibles : {len(elig)} · simulés : {len(choisis)} × {n_sim} fois × 3 versions", flush=True)

    P = PS.Profils()
    attente = []
    R = {v: Suivi() for v in ('stats_seules', 'stats_plus_marche', 'joueurs_moyens')}
    connus = collections.Counter()
    for i, m in enumerate(M):
        while attente and attente[0][0] < m['date']:
            _, j = heapq.heappop(attente)
            P.ajouter(M[j], E.cle(M[j]['nom_g']), E.cle(M[j]['nom_p']))
        if m.get('detail'):
            heapq.heappush(attente, (m['fin'], i))
        if i not in choisis:
            continue
        g, p = E.cle(m['nom_g']), E.cle(m['nom_p'])
        pg, ng = P.profil(g, m['circuit'], m['surface'], m['date'])
        pp, np_ = P.profil(p, m['circuit'], m['surface'], m['date'])
        connus[min(ng, np_) >= 500] += 1
        mu = P.moyenne(m['circuit'], m['surface'])
        sg = 3 if m['bo'] == 5 else 2
        cg, cp = S.composantes(pg, pp, mu), S.composantes(pp, pg, mu)
        cmu = S.composantes(mu, mu, mu)
        (fw, fl), tot = reel(m)
        nz = naif[(m['circuit'], m['bo'])]
        for version, (ca, cb, pv) in (('stats_seules', (cg, cp, V['pred_sack'][i][0])),
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
           'calibration': {v: {k: s.calibration(k) for k in ('aces', 'doubles_fautes', 'breaks')} for v, s in R.items()},
           'duree_s': round(time.time() - t0)}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    for v in ('stats_plus_marche', 'joueurs_moyens', 'stats_seules'):
        print(f"\n{v}")
        for k, x in rap['versions'][v].items():
            print(f"  {x['libelle']:<28} prévu {x['prevu_moy']:>6} réel {x['reel_moy']:>6} · MAE {x['mae']:>6} "
                  f"(naïf {x['mae_naif']}) gain {x['gain_vs_naif_pct']} % · corr {x['correlation']} · couverture 80 % : {x['couverture_80_pct']} %")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
