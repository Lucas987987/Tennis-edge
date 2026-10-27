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
  • RÉGLAGE sur l'archive Sackmann : aces par rapport de sommes, première balle
    par méthode des moments, longueur du match sur un petit maillage de DP exacte.
  • JUGEMENT sur les feuilles collectées APRÈS l'archive. Chaque composante est
    testée seule, puis leur combinaison est obligatoire si plusieurs passent :
      (a) aces : biais relatif absolu réduit ;
      (b) première balle : couverture de l'intervalle plus proche de 80 % ;
      (c) total de jeux : MAE réduite d'au moins 1 % ;
      (d) dans tous les cas, aucune autre MAE n'augmente de plus de 2 %.
    Si la combinaison échoue, une seule composante peut être conservée selon la
    priorité fixée : première balle, jeux, aces. Les réglages rejetés restent off.

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
import ajustement as AJ  # noqa: E402
import backtest_match_simule as BMS  # noqa: E402
import backtest_pronostic as BP  # noqa: E402
import donnees  # noqa: E402
import elo as E  # noqa: E402
import feuilles as FE  # noqa: E402
import match_simule as S  # noqa: E402
import modele as MM  # noqa: E402
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


def apprendre_delta_jeux(obs, limite=800):
    """Règle une longueur commune de service sur l'archive, par DP exacte.

    obs : (composantes gagnant, composantes perdant, p Elo, sets gagnants,
    jeux réels). La même modification est appliquée aux deux joueurs, puis la
    probabilité de victoire est réancrée : ce challenger vise les jeux, pas le
    vainqueur. Le petit maillage est fixé avant le jugement.
    """
    if not obs:
        return 0.0, {}
    pas = max(1, len(obs) // limite)
    choisis = obs[::pas][:limite]
    scores = {}
    for delta in (-.03, -.015, 0.0, .015, .03):
        erreurs = []
        for cg, cp, p_elo, sg, reel in choisis:
            if delta:
                cg = S.ajuster(cg, max(.15, min(.85, S.p_service(cg) + delta)))
                cp = S.ajuster(cp, max(.15, min(.85, S.p_service(cp) + delta)))
            a, b = S.ancrer_rapide(S.p_service(cg), S.p_service(cp), p_elo, sg, SIGMA)
            prev = MM.moyenne(MM.match_forme(a, b, sg, SIGMA)['total_jeux'])
            erreurs.append(abs(prev - reel))
        scores[delta] = sum(erreurs) / len(erreurs) if erreurs else float('inf')
    delta = min(scores, key=lambda x: (scores[x], abs(x), x))
    return delta, {str(k): round(v, 4) for k, v in scores.items()}


def _degradations(base, regle, tolerance=1.02):
    return [k for k in base if k in regle and regle[k]['mae'] > tolerance * base[k]['mae']]


def choisir_reglages(rap, appris):
    """Juge séparément chaque correction, puis leur combinaison si nécessaire.

    Priorité conservative fixée : première balle, total de jeux, aces. Si la
    combinaison échoue, une seule composante peut rester active ; les réglages
    rejetés restent dans le rapport et ne sont jamais réactivés artificiellement.
    """
    base = rap.get('sans_reglage', {})
    if not base or 'aces' not in base or 'premiere_pct' not in base or 'total_jeux' not in base:
        return {}, [], 'pas assez de feuilles collectées pour juger'

    def premiere_ok(r):
        return (abs(r['premiere_pct']['couverture_80_pct'] - 80)
                < abs(base['premiere_pct']['couverture_80_pct'] - 80)
                and not _degradations(base, r))

    def aces_ok(r):
        b = abs(base['aces']['prevu_moy'] - base['aces']['reel_moy']) / max(base['aces']['reel_moy'], 1e-9)
        a = abs(r['aces']['prevu_moy'] - r['aces']['reel_moy']) / max(base['aces']['reel_moy'], 1e-9)
        return a < b and not _degradations(base, r)

    def jeux_ok(r):
        return (r['total_jeux']['mae'] < .99 * base['total_jeux']['mae']
                and not _degradations(base, r))

    regles = {
        'premiere_seule': premiere_ok,
        'jeux_seuls': jeux_ok,
        'aces_seuls': aces_ok,
    }
    admis = [nom for nom, test in regles.items() if test(rap.get(nom, {}))]
    cles = {'premiere_seule': 'tau_f', 'jeux_seuls': 'jeux_delta', 'aces_seuls': 'ace_facteur'}
    complet = rap.get('complet', {})
    complet_ok = complet and all(regles[nom](complet) for nom in admis)
    if len(admis) > 1 and complet_ok:
        return ({cles[nom]: appris[cles[nom]] for nom in admis}, admis + ['complet'],
                'composantes et combinaison validées hors échantillon')
    if admis:
        nom = admis[0]
        raison = 'une seule composante validée' if len(admis) == 1 else 'combinaison rejetée ; composante prioritaire conservée'
        return {cles[nom]: appris[cles[nom]]}, [nom], raison
    pires = _degradations(base, complet) if complet else []
    return {}, [], 'aucune composante ne franchit les critères ; dégradations du complet : ' + (', '.join(pires) or 'aucune')


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
    try:
        with open(os.path.join(ICI, 'choix_simulation.json'), encoding='utf-8') as f:
            choix = json.load(f)
    except (OSError, ValueError):
        choix = {}
    ajustees = choix.get('composantes', 'ajustees') == 'ajustees'
    n0 = float(choix.get('n0') or AJ.N0)
    n0_comp = choix.get('n0_par_composante') or None
    dyn = AJ.lire_dynamique(choix)
    adj, mois_adj = None, None
    obs_f, obs_jeux, ace_num, ace_den = [], [], 0.0, 0.0
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
                if ajustees:
                    debut_mois = m['date'].replace(day=1)
                    if mois_adj != debut_mois:
                        adj = AJ.ajuster_choisi(tout, debut_mois, E.cle, n0=n0, dyn=dyn, depart=adj,
                                                tours=6 if adj is None else 2, n0_par_composante=n0_comp)
                        mois_adj = debut_mois
                    cg = S.composantes_ajustees(adj, g, p, m['circuit'], m['surface'])
                    cp = S.composantes_ajustees(adj, p, g, m['circuit'], m['surface'])
                if entrainement:
                    for c, d in ((cg, det['w']), (cp, det['l'])):
                        sv, in1, ace = d[0], d[1], d[4]
                        obs_f.append((sv, in1, c['f']))
                        ace_num += ace
                        ace_den += in1 * c['a']
                    total_reel = sum(a + b for a, b in m['sets'] if a >= 0 and b >= 0)
                    if total_reel:
                        obs_jeux.append((cg, cp, p_elo, 3 if m['bo'] == 5 else 2, total_reel))
                else:
                    valid.append((m, cg, cp, p_elo))
        if det:
            heapq.heappush(attente, (m['fin'], i))
        elo.maj(g, p, m['surface'], m.get('niveau') == 'G')
    ace_facteur = ace_num / ace_den if ace_den else 1.0
    var_f, tau_f = moments_f(obs_f)
    delta_jeux, mae_jeux = apprendre_delta_jeux(obs_jeux)
    appris = {'ace_facteur': round(ace_facteur, 4), 'tau_f': round(tau_f, 4),
              'jeux_delta': round(delta_jeux, 4)}
    print(f"Réglage (archive 2024 → 01/2026, {len(obs_f)} feuilles de joueur) : ace_facteur {ace_facteur:.3f} · "
          f"tau_f {tau_f:.3f} · jeux_delta {delta_jeux:+.3f}", flush=True)

    pas = max(1, len(valid) // n_max)
    choisis = valid[::pas][:n_max]
    variantes = {
        'sans_reglage': None,
        'premiere_seule': {'tau_f': appris['tau_f']},
        'aces_seuls': {'ace_facteur': appris['ace_facteur']},
        'jeux_seuls': {'jeux_delta': appris['jeux_delta']},
        'complet': appris,
    }
    R = {nom: BMS.Suivi() for nom in variantes}
    for k, (m, cg, cp, p_elo) in enumerate(choisis):
        (fw, fl), tot = BMS.reel(m)
        sg = 3 if m['bo'] == 5 else 2
        for nom, rg in variantes.items():
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
    reglages, adoptes, raison = choisir_reglages(rap, appris)
    ok = bool(reglages)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("Réglé sur l'archive, jugé sur les feuilles postérieures. Chaque composante est jugée seule ; "
                     "leur combinaison doit aussi passer. Première balle : couverture plus proche de 80 %. "
                     "Aces : biais absolu réduit. Jeux : MAE réduite d'au moins 1 %. Dans tous les cas, "
                     "aucune MAE ne doit augmenter de plus de 2 %."),
           'variante_testee': 'composantes_ajustees' if ajustees else 'profils_bruts',
           'reglages': reglages, 'reglages_appris': appris, 'composantes_adoptees': adoptes,
           'adopte': ok, 'raison': raison,
           'entrainement': {'feuilles_de_joueur': len(obs_f), 'matchs_jeux': len(obs_jeux),
                            'mae_jeux_par_delta': mae_jeux, 'periode': f"{BP.DEBUT_A} → {BP.FIN_A}"},
           'jugement': {'matchs': len(choisis), 'simulations_par_match': n_sim,
                        'periode': (f"{choisis[0][0]['date']} → {choisis[-1][0]['date']}" if choisis else None),
                        'versions': rap},
           'duree_s': round(time.time() - t0)}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"\n{'ADOPTÉ' if ok else 'NON ADOPTÉ'} — {raison}")
    for nom in variantes:
        print(f"\n{nom} ({len(choisis)} matchs des feuilles collectées)")
        for k, x in rap[nom].items():
            print(f"  {x['libelle']:<28} prévu {x['prevu_moy']:>6} réel {x['reel_moy']:>6} · MAE {x['mae']:>6} · "
                  f"couverture 80 % : {x['couverture_80_pct']} % (sous {x['sous_p10_pct']} / au-dessus {x['au_dessus_p90_pct']})")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
