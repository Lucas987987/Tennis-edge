#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_prior_elo.py — piste d'Ingram (05/11/2026, demande de Lucas) : de meilleures estimations du service et du retour
pour les joueurs PEU VUS.

Aujourd'hui (ajustement.py) chaque qualité de service S et de retour R d'un joueur est ramenée vers 0, c'est-à-dire
vers la MOYENNE DU CIRCUIT, tant qu'il a peu de feuilles de match. Un joueur peu vu mais fort (ou faible) est donc
simulé comme un joueur moyen. Idée du modèle hiérarchique d'Ingram (2019) : ramener vers ce que son NIVEAU laisse
attendre. Ici le niveau = son Elo (résultats seuls, aucune cote) :
    centre S_c(joueur) = β_S,c · (Elo − 1500) / 100      centre R_c(joueur) = β_R,c · (Elo − 1500) / 100
β (par composante f, a, w1, d, w2j) appris UNE fois, le 01/01/2023, par régression pondérée des S et R ajustés des
joueurs bien documentés sur leur Elo du jour.

RÈGLE FIXÉE LE 05/11/2026, AVANT DE REGARDER LE RÉSULTAT (même mesure que le choix de N0 : vraisemblance des points
des 4 mois qui suivent chaque ajustement), jugée sur 6 dates jamais vues (01/01 et 01/07 de 2024, 2025, 2026),
CIRCUIT PAR CIRCUIT (ATP, WTA, Challenger) :
  retenue pour un fantôme de la simulation sur un circuit si
    a) la log-vraisemblance des points baisse sur au moins 5 des 6 dates, ET
    b) chez les serveurs PEU VUS (moins de 2 000 points de service pondérés à la date), elle baisse d'au moins
       0,002 en moyenne sur les 6 dates.
Usage : python simulateur/etude_prior_elo.py /tmp/sackmann .
"""
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import ajustement as AJ  # noqa: E402

APPRENTISSAGE = dt.date(2023, 1, 1)
# 6 dates prévues ; l'archive s'arrête en juin 2026, le 01/07/2026 n'a donc ni matchs ni fenêtre de jugement :
# jugement sur les 5 dates restantes, toutes doivent gagner (« ≥ 5 des 6 » sans la date impossible)
JUGEMENT = [dt.date(a, m, 1) for a in (2024, 2025, 2026) for m in (1, 7)][:5]
PEU_VU, BIEN_VU = 2000.0, 6000.0
SORTIE = os.path.join(ICI, 'rapport_prior_elo.json')


def elos_aux_dates(M, dates, cle):
    import elo as E
    dates = sorted(dates)
    el, out, i = E.Elo(), {}, 0
    jour, attente = None, []
    for m in M:
        while i < len(dates) and m['date'] >= dates[i]:
            for g, p, s, gc in attente:
                el.maj(g, p, s, gc, None)
            attente = []
            out[dates[i]] = {j: el.note(j) for j in set(el.g) | set(el.dep)}
            i += 1
        if m['date'] != jour:
            for g, p, s, gc in attente:
                el.maj(g, p, s, gc, None)
            attente, jour = [], m['date']
        g, p = cle(m.get('nom_g')), cle(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        if m['circuit'] in ('CH', 'ITF'):
            el.presenter(g, 1200.0)
            el.presenter(p, 1200.0)
        attente.append((g, p, m['surface'], m.get('niveau') == 'G'))
    return out, el


def points_service(M, date, cle):
    """Points de service pondérés (demi-vie 1 an, 4 ans) par joueur à la date."""
    out = collections.Counter()
    for a, b, g, s, x, w in AJ.observations(M, date, cle):
        out[a] += w * x['f'][0]
    return out


def apprendre_beta(A, elo, vol):
    beta = {}
    for c in AJ.COMPOSANTES:
        beta[c] = {}
        for etape in ('S', 'R'):
            X = [((elo[j] - 1500) / 100, v) for j, v in A.eff[c][etape].items() if j in elo and vol.get(j, 0) >= BIEN_VU]
            sxx = sum(x * x for x, _ in X)
            beta[c][etape] = round(sum(x * y for x, y in X) / sxx, 5) if sxx else 0.0
    return beta


def centre(beta, elo):
    return {c: {e: {j: beta[c][e] * (v - 1500) / 100 for j, v in elo.items()} for e in ('S', 'R')} for c in beta}


def ll_par_groupe(A, M, debut, fin, cle, vol):
    acc = collections.defaultdict(lambda: [0.0, 0])
    for m in M:
        d = m.get('detail')
        if not d or not (debut <= m['date'] < fin) or m['circuit'] not in ('ATP', 'WTA', 'CH'):
            continue
        a, b = cle(m['nom_g']), cle(m['nom_p'])
        for srv, ret, det, dadv in ((a, b, d['w'], d['l']), (b, a, d['l'], d['w'])):
            t = A.taux(srv, ret, m['circuit'], m['surface'])
            grp = 'peu_vu' if vol.get(srv, 0) < PEU_VU else 'vu'
            for c, (n, k) in AJ.essais(det, dadv).items():
                if n <= 0:
                    continue
                p = min(max(t[c], 1e-6), 1 - 1e-6)
                v = -(k * math.log(p) + (n - k) * math.log(1 - p))
                for key in ((m['circuit'], 'tous'), (m['circuit'], grp)):
                    acc[key][0] += v
                    acc[key][1] += n
    return {k: (s / n if n else None, n) for k, (s, n) in acc.items()}


def main(argv):
    import donnees as DN
    import elo as E
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    with open(os.path.join(ICI, 'choix_simulation.json'), encoding='utf-8') as f:
        ch = json.load(f)
    n0, n0c = float(ch.get('n0') or AJ.N0), ch.get('n0_par_composante') or None
    M = DN.charger(archive, 2015)
    cle = E.cle
    dates = [APPRENTISSAGE] + JUGEMENT
    elos, _ = elos_aux_dates(M, dates, cle)
    A0 = AJ.ajuster(M, APPRENTISSAGE, cle, n0=n0, n0_par_composante=n0c)
    beta = apprendre_beta(A0, elos[APPRENTISSAGE], points_service(M, APPRENTISSAGE, cle))
    print('β appris au 01/01/2023 :', json.dumps(beta))
    res = []
    for d in JUGEMENT:
        fin = (d.replace(day=1) + dt.timedelta(days=125)).replace(day=1)
        vol = points_service(M, d, cle)
        a = AJ.ajuster(M, d, cle, n0=n0, n0_par_composante=n0c)
        b = AJ.ajuster(M, d, cle, n0=n0, n0_par_composante=n0c, centre=centre(beta, elos[d]))
        la, lb = ll_par_groupe(a, M, d, fin, cle, vol), ll_par_groupe(b, M, d, fin, cle, vol)
        ligne = {'date': d.isoformat()}
        for k in la:
            if la[k][0] is not None and lb.get(k, (None,))[0] is not None:
                ligne['|'.join(k)] = {'actuel': round(la[k][0], 5), 'prior_elo': round(lb[k][0], 5),
                                      'gain': round(la[k][0] - lb[k][0], 5), 'points': la[k][1]}
        res.append(ligne)
        print(json.dumps(ligne, ensure_ascii=False))
    verdict = {}
    for c in ('ATP', 'WTA', 'CH'):
        g_tous = [r.get(f'{c}|tous', {}).get('gain') for r in res]
        g_peu = [r.get(f'{c}|peu_vu', {}).get('gain') for r in res]
        g_tous, g_peu = [x for x in g_tous if x is not None], [x for x in g_peu if x is not None]
        a_ = sum(x > 0 for x in g_tous) >= 5
        b_ = bool(g_peu) and sum(g_peu) / len(g_peu) >= 0.002
        verdict[c] = {'dates_gagnantes': sum(x > 0 for x in g_tous), 'gain_moyen_tous': round(sum(g_tous) / max(1, len(g_tous)), 5),
                      'gain_moyen_peu_vus': round(sum(g_peu) / max(1, len(g_peu)), 5) if g_peu else None,
                      'retenu_pour_fantome': bool(a_ and b_)}
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'beta': beta,
           'regle': ("par circuit : log-vraisemblance des points plus basse sur ≥ 5 des 6 dates ET −0,002 en moyenne "
                     "chez les serveurs peu vus (< 2 000 points pondérés)"),
           'dates': res, 'verdict': verdict}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(verdict, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
