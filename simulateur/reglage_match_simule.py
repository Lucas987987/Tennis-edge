#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reglage_match_simule.py — corriger les deux défauts mesurés du match simulé (22/10/2026).

Défauts constatés le 22/10 (2 000 matchs ATP/WTA 2024 → janvier 2026) :
  1. aces sous-estimés : 4,3 prévus pour 4,8 réels (−9 %) ;
  2. fourchette du % de 1re balle trop étroite : le réel n'y tombe que 71 % du temps
     au lieu de 80 % — la simulation garde le même % de 1re balle d'un match à
     l'autre, alors qu'il varie selon les jours.

RÈGLE FIXÉE AVANT DE REGARDER LES FEUILLES COLLECTÉES :
  • RÉGLAGE, sur l'archive Sackmann (ATP/WTA, 01/01/2024 → 01/02/2026), profils
    point-in-time, sans simulation :
      ace_facteur = Σ aces réels / Σ (1res balles dans le court × taux d'aces prévu) ;
      tau_f       = écart-type, en logit, de la variation du % de 1re balle d'un match
                    à l'autre, AU-DELÀ du hasard des points (méthode des moments :
                    Σ[(1res dans − n·f)² − n·f·(1−f)] / Σ n², ramené en logit).
  • JUGEMENT, sur les feuilles collectées APRÈS la fin de l'archive (TennisApi,
    ATP/WTA/Challenger), jamais utilisées pour régler : même simulation (niveau Elo
    du rejeu chronologique), sans puis avec réglage. Le réglage est ADOPTÉ si :
      (a) le biais relatif des aces (prévu − réel) / réel diminue en valeur absolue ;
      (b) la couverture de la fourchette du % de 1re balle se rapproche de 80 % ;
      (c) aucune statistique ne voit son écart moyen (MAE) augmenter de plus de 2 %.
    Sinon le match simulé reste tel quel. Aucun autre réglage n'est essayé.

Usage : python simulateur/reglage_match_simule.py <archive Sackmann> [racine] [--n=300] [--max=1500]
Sortie : simulateur/reglages_match_simule.json (lu par pronostics_du_jour.py si adopté).
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
import backtest_match_simule as BMS  # noqa: E402
import backtest_pronostic as BP  # noqa: E402
import donnees  # noqa: E402
import elo as E  # noqa: E402
import feuilles as FE  # noqa: E402
import match_simule as S  # noqa: E402
import profils_service as PS  # noqa: E402

SORTIE = os.path.join(ICI, 'reglages_match_simule.json')
SIGMA = 0.15
BAS = ('CH', 'ITF', 'ITFH')


def moments_f(obs):
    """obs : [(n points de service, 1res dans, f prévu)] -> (variance en proba, tau en logit)."""
    num = sum((k - n * f) ** 2 - n * f * (1 - f) for n, k, f in obs)
    den = sum(n * n for n, _, _ in obs)
    var = max(num / den, 0.0) if den else 0.0
    pq = sum(f * (1 - f) for _, _, f in obs) / len(obs) if obs else 0.25
    return var, (math.sqrt(var) / pq if pq else 0.0)


def adopter(base, regle):
    """Règle fixée d'avance (voir l'en-tête). base / regle : rapports Suivi (par statistique)."""
    if not base or 'aces' not in base or 'premiere_pct' not in base:
        return False, "pas assez de feuilles collectées pour juger"
    b_ace = abs(base['aces']['prevu_moy'] - base['aces']['reel_moy']) / max(base['aces']['reel_moy'], 1e-9)
    r_ace = abs(regle['aces']['prevu_moy'] - regle['aces']['reel_moy']) / max(regle['aces']['reel_moy'], 1e-9)
    b_cov = abs(base['premiere_pct']['couverture_80_pct'] - 80)
    r_cov = abs(regle['premiere_pct']['couverture_80_pct'] - 80)
    pire = [k for k in base if k in regle and regle[k]['mae'] > 1.02 * base[k]['mae']]
    ok = r_ace < b_ace and r_cov < b_cov and not pire
    raison = (f"biais aces {100 * b_ace:.1f} % → {100 * r_ace:.1f} % ; couverture 1re balle à "
              f"{base['premiere_pct']['couverture_80_pct']} % → {regle['premiere_pct']['couverture_80_pct']} % ; "
              f"écart moyen dégradé de plus de 2 % : {', '.join(pire) or 'aucune statistique'}")
    return ok, raison


def main(argv):
    t0 = time.time()
    args = [a for a in argv[1:] if not a.startswith('--')]
    opt = {a.split('=')[0]: a.split('=')[1] for a in argv[1:] if a.startswith('--') and '=' in a}
    n_sim, n_max = int(opt.get('--n', 300)), int(opt.get('--max', 1500))
    dossier = args[0] if args else 'sackmann'
    racine = args[1] if len(args) > 1 else os.path.join(ICI, '..')
    M = donnees.charger(dossier, 2016)
    if not M:
        print(f"::error::aucun match Sackmann sous {dossier}")
        return 1
    fin_sack = max(m['date'] for m in M)
    F = [m for m in FE.charger(racine) if m['date'] > fin_sack]
    tout = sorted(M + F, key=lambda m: (m['date'], m['tour'], m['num']))
    print(f"Archive : {len(M)} matchs jusqu'au {fin_sack} · feuilles collectées ensuite : {len(F)} "
          f"({sum(1 for m in F if m.get('detail'))} avec feuille complète)", flush=True)

    elo, P, attente = E.Elo(), PS.Profils(), []
    obs_f, ace_num, ace_den = [], 0.0, 0.0
    valid = []
    for i, m in enumerate(tout):
        while attente and attente[0][0] < m['date']:
            _, j = heapq.heappop(attente)
            P.ajouter(tout[j], E.cle(tout[j]['nom_g']), E.cle(tout[j]['nom_p']))
        g, p = E.cle(m['nom_g']), E.cle(m['nom_p'])
        for k in (g, p):
            if m['circuit'] in BAS:
                elo.presenter(k, BP.DEPART_BAS)
        p_elo = elo.proba(g, p, m['surface'])
        det = m.get('detail')
        if det and m['complet']:
            entrainement = BP.DEBUT_A <= m['date'] < BP.FIN_A and m['circuit'] in ('ATP', 'WTA') and m.get('source') != 'tennisapi'
            jugement = m.get('source') == 'tennisapi' and m['circuit'] in ('ATP', 'WTA', 'CH')
            if entrainement or jugement:
                pg, _ = P.profil(g, m['circuit'], m['surface'], m['date'])
                pp, _ = P.profil(p, m['circuit'], m['surface'], m['date'])
                mu = P.moyenne(m['circuit'], m['surface'])
                cg, cp = S.composantes(pg, pp, mu), S.composantes(pp, pg, mu)
                if entrainement:
                    for c, d in ((cg, det['w']), (cp, det['l'])):
                        sv, in1, ace = d[0], d[1], d[4]
                        obs_f.append((sv, in1, c['f']))
                        ace_num += ace
                        ace_den += in1 * c['a']
                else:
                    valid.append((m, cg, cp, p_elo))
        if det:
            heapq.heappush(attente, (m['fin'], i))
        elo.maj(g, p, m['surface'], m.get('niveau') == 'G')
    ace_facteur = ace_num / ace_den if ace_den else 1.0
    var_f, tau_f = moments_f(obs_f)
    reglages = {'ace_facteur': round(ace_facteur, 4), 'tau_f': round(tau_f, 4)}
    print(f"Réglage (archive 2024 → 01/2026, {len(obs_f)} feuilles de joueur) : ace_facteur {ace_facteur:.3f} · "
          f"tau_f {tau_f:.3f} (variation de la 1re balle d'un match à l'autre, en logit)", flush=True)

    pas = max(1, len(valid) // n_max)
    choisis = valid[::pas][:n_max]
    R = {'sans_reglage': BMS.Suivi(), 'avec_reglage': BMS.Suivi()}
    for k, (m, cg, cp, p_elo) in enumerate(choisis):
        (fw, fl), tot = BMS.reel(m)
        sg = 3 if m['bo'] == 5 else 2
        for nom, rg in (('sans_reglage', None), ('avec_reglage', reglages)):
            r = S.simuler(cg, cp, p_elo, sg, n_sim, SIGMA, cle=f"{m.get('id')}|{k}", reglages=rg)
            for kj, vrai in ((0, fw), (1, fl)):
                for st in BMS.STATS:
                    x = r['feuille'][kj][st]
                    if x:
                        R[nom].ajouter(st, x['moy'], x['p10'], x['p90'], vrai[st], vrai[st])
            R[nom].ajouter('total_jeux', r['jeux']['moy'], r['jeux']['p10'], r['jeux']['p90'], tot, tot)
        if (k + 1) % 300 == 0:
            print(f"  jugement : {k + 1}/{len(choisis)} matchs ({round(time.time() - t0)} s)", flush=True)
    rap = {nom: s.rapport() for nom, s in R.items()}
    for x in rap.values():
        for v in x.values():
            v.pop('mae_naif', None)
            v.pop('gain_vs_naif_pct', None)
    ok, raison = adopter(rap['sans_reglage'], rap['avec_reglage'])
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("Réglé sur l'archive (ATP/WTA 2024 → 01/2026), jugé sur les feuilles collectées après l'archive "
                     "(ATP/WTA/Challenger). Adopté si le biais des aces baisse, si la couverture de la 1re balle se "
                     "rapproche de 80 % et si aucun écart moyen ne monte de plus de 2 %."),
           'reglages': reglages, 'adopte': ok, 'raison': raison,
           'entrainement': {'feuilles_de_joueur': len(obs_f), 'periode': f"{BP.DEBUT_A} → {BP.FIN_A}"},
           'jugement': {'matchs': len(choisis), 'simulations_par_match': n_sim,
                        'periode': (f"{choisis[0][0]['date']} → {choisis[-1][0]['date']}" if choisis else None),
                        'versions': rap},
           'duree_s': round(time.time() - t0)}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"\n{'ADOPTÉ' if ok else 'NON ADOPTÉ'} — {raison}")
    for nom in ('sans_reglage', 'avec_reglage'):
        print(f"\n{nom} ({len(choisis)} matchs des feuilles collectées)")
        for k, x in rap[nom].items():
            print(f"  {x['libelle']:<28} prévu {x['prevu_moy']:>6} réel {x['reel_moy']:>6} · MAE {x['mae']:>6} · "
                  f"couverture 80 % : {x['couverture_80_pct']} % (sous {x['sous_p10_pct']} / au-dessus {x['au_dessus_p90_pct']})")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
