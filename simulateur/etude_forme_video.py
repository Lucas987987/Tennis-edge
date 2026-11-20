#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_forme_video.py — quelle règle choisit le mieux la FORME du match montré en vidéo (nombre de sets, tie-break) ?
Jugé sur les VRAIS résultats, circuit par circuit (04/11/2026, demande de Lucas).

Règle A (en place depuis le 04/11, match_simule.match_type) : parmi les victoires simulées du FAVORI, le nombre de sets
  le plus fréquent (à égalité : le moins de sets), puis tie-break si plus de la moitié de ces matchs en ont un.
Règle B (globale) : 3 sets si P(3 sets) > 50 % sur TOUS les matchs simulés ; tie-break si P(au moins un tie-break) > 50 %.
Règle C (Lucas, 04/11/2026, retenue) : 3 sets si P(3 sets) du match ≥ moyenne du circuit ; tie-break si P(tie-break) ≥
  moyenne du circuit. Direct : moyennes RÉELLES du circuit (match_simule.MOYENNES_FORME), nos probabilités affichées étant
  étalonnées. Archive : la moyenne des probabilités du calcul exact sur le circuit (il sous-estime les 3 sets en
  Challenger : une moyenne réelle n'y serait presque jamais atteinte) — on juge alors le CLASSEMENT des matchs.
Mesure : part des matchs réels dont le nombre de sets, la présence d'un tie-break, puis les deux ensemble, sont ceux que
la règle aurait montrés ; et l'étalonnage des probabilités (prévu contre réel) par tranche.

Deux populations, jamais agrégées :
  ARCHIVE : tous les matchs au meilleur des 3 sets depuis 2021 (ATP, WTA, Challenger), distribution EXACTE de la forme
            (etude_forme_match.py : Elo service / retour d'avant-match, forme du jour σ = 0,15, Challenger 0,22) ;
  DIRECT  : nos pronostics figés jugés après match (simulateur/journal_pronostics/apres_match), distribution des sets
            réellement affichée (le tie-break par règle A n'y est pas mesurable : seule la probabilité globale est gardée).
Usage : python simulateur/etude_forme_video.py /tmp/sackmann .
"""
import datetime as dt
import glob
import gzip
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_forme_match as FM  # noqa: E402

SIGMA = {'ATP': 0.15, 'WTA': 0.15, 'CH': 0.22}
SORTIE = os.path.join(ICI, 'rapport_forme_video.json')


def regles(dist):
    """dist {(A gagne, nb sets, tie-break, jeux): p} → (fav_est_A, règle A (sets, tb), règle B (sets, tb), P3, Ptb)."""
    pv = sum(v for k, v in dist.items() if k[0])
    fav = pv >= 0.5
    p3 = sum(v for k, v in dist.items() if k[1] == 3)
    ptb = sum(v for k, v in dist.items() if k[2])
    fw = {n: sum(v for k, v in dist.items() if k[0] == fav and k[1] == n) for n in (2, 3)}
    n_a = 3 if fw[3] > fw[2] else 2
    dans = sum(v for k, v in dist.items() if k[0] == fav and k[1] == n_a)
    tb_dans = sum(v for k, v in dist.items() if k[0] == fav and k[1] == n_a and k[2])
    return fav, (n_a, tb_dans > 0.5 * dans), (3 if p3 > 0.5 else 2, ptb > 0.5), p3, ptb


def _un(row):
    d, c, pa, pb, obs = row
    dist = FM.avec_forme(pa, pb, SIGMA.get(c, 0.15), 0.0, 0.0)
    fav, A, B, p3, ptb = regles(dist)
    return {'c': c, 'an': d.year, 'sets': obs[1], 'tb': bool(obs[2]), 'A': A, 'B': B, 'p3': p3, 'ptb': ptb,
            'fav_gagne': fav}


def regle_c(R, seuils):
    """Ajoute r['C'] = (sets, tb) : au-dessus du seuil du circuit."""
    for r in R:
        r['C'] = (3 if r['p3'] >= seuils[0] else 2, (r['ptb'] >= seuils[1]) if r.get('ptb') is not None else None)
    return R


def bilan(R, avec_tb=True):
    n = len(R)
    if not n:
        return None
    pct = lambda f: round(100 * sum(1 for r in R if f(r)) / n, 1)
    out = {'matchs': n, 'reel_3_sets_pct': pct(lambda r: r['sets'] == 3),
           'prevu_3_sets_pct': round(100 * sum(r['p3'] for r in R) / n, 1),
           'sets_juste_A_pct': pct(lambda r: r['A'][0] == r['sets']), 'sets_juste_B_pct': pct(lambda r: r['B'][0] == r['sets']),
           'video_3_sets_A_pct': pct(lambda r: r['A'][0] == 3), 'video_3_sets_B_pct': pct(lambda r: r['B'][0] == 3)}
    if all('C' in r for r in R):
        c3 = [r for r in R if r['C'][0] == 3]
        c2 = [r for r in R if r['C'][0] == 2]
        out['regle_C'] = {'video_3_sets_pct': round(100 * len(c3) / n, 1),
                          'reel_3_sets_si_video_3_pct': round(100 * sum(1 for r in c3 if r['sets'] == 3) / len(c3), 1) if c3 else None,
                          'reel_3_sets_si_video_2_pct': round(100 * sum(1 for r in c2 if r['sets'] == 3) / len(c2), 1) if c2 else None,
                          'sets_juste_pct': pct(lambda r: r['C'][0] == r['sets'])}
        if avec_tb:
            t1 = [r for r in R if r['C'][1]]
            t0 = [r for r in R if not r['C'][1]]
            out['regle_C'].update({'video_tie_break_pct': round(100 * len(t1) / n, 1),
                                   'reel_tb_si_video_tb_pct': round(100 * sum(1 for r in t1 if r['tb']) / len(t1), 1) if t1 else None,
                                   'reel_tb_si_video_sans_pct': round(100 * sum(1 for r in t0 if r['tb']) / len(t0), 1) if t0 else None,
                                   'tb_juste_pct': pct(lambda r: r['C'][1] == r['tb']),
                                   'forme_juste_pct': pct(lambda r: r['C'] == (r['sets'], r['tb']))})
    dif = [r for r in R if r['A'][0] != r['B'][0]]
    out['sets_desaccord'] = {'matchs': len(dif), 'A_juste': sum(1 for r in dif if r['A'][0] == r['sets']),
                             'B_juste': sum(1 for r in dif if r['B'][0] == r['sets'])}
    if avec_tb:
        out.update({'reel_tie_break_pct': pct(lambda r: r['tb']),
                    'prevu_tie_break_pct': round(100 * sum(r['ptb'] for r in R) / n, 1),
                    'tb_juste_A_pct': pct(lambda r: r['A'][1] == r['tb']), 'tb_juste_B_pct': pct(lambda r: r['B'][1] == r['tb']),
                    'forme_juste_A_pct': pct(lambda r: r['A'] == (r['sets'], r['tb'])),
                    'forme_juste_B_pct': pct(lambda r: r['B'] == (r['sets'], r['tb'])),
                    'video_tie_break_A_pct': pct(lambda r: r['A'][1]), 'video_tie_break_B_pct': pct(lambda r: r['B'][1])})
    # étalonnage de P(3 sets) par tranche de 10 points
    cal = []
    for lo in range(0, 100, 10):
        b = [r for r in R if lo <= 100 * r['p3'] < lo + 10]
        if len(b) >= 30:
            cal.append({'tranche': f'{lo}–{lo + 10} %', 'matchs': len(b), 'prevu': round(100 * sum(r['p3'] for r in b) / len(b), 1),
                        'reel': round(100 * sum(1 for r in b if r['sets'] == 3) / len(b), 1)})
    out['etalonnage_3_sets'] = cal
    return out


def direct(racine):
    R = []
    for f in sorted(glob.glob(os.path.join(racine, 'simulateur', 'journal_pronostics', 'apres_match', '*.json.gz'))):
        try:
            B = json.load(gzip.open(f, 'rt', encoding='utf-8')).values()
        except (OSError, ValueError):
            continue
        for b in B:
            S, reel = (b.get('prevu') or {}).get('sets') or {}, b.get('reel') or {}
            if not S or reel.get('nb_sets') not in (2, 3) or set(S) != {'2-0', '2-1', '1-2', '0-2'}:
                continue
            ph = S['2-0'] + S['2-1']
            fav_h = ph >= 0.5
            fw2, fw3 = (S['2-0'], S['2-1']) if fav_h else (S['0-2'], S['1-2'])
            p3 = S['2-1'] + S['1-2']
            R.append({'c': b.get('circuit'), 'sets': reel['nb_sets'], 'tb': bool(reel.get('tie_break')),
                      'A': (3 if fw3 > fw2 else 2, None), 'B': (3 if p3 > 0.5 else 2, None), 'p3': p3, 'ptb': None})
    return R


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    rows = FM.donnees(archive, racine)
    with ProcessPoolExecutor() as ex:
        R = list(ex.map(_un, rows, chunksize=200))
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regles': {'A': 'forme la plus fréquente parmi les victoires du favori (en place)',
                      'B': '3 sets / tie-break seulement au-dessus de 50 % sur tous les matchs'},
           'archive': {}, 'direct': {}}
    import match_simule as MS
    Dr = direct(racine)
    for c in ('ATP', 'WTA', 'CH'):
        Rc = [r for r in R if r['c'] == c]
        if Rc:
            regle_c(Rc, (sum(r['p3'] for r in Rc) / len(Rc), sum(r['ptb'] for r in Rc) / len(Rc)))
        doc['archive'][c] = bilan(Rc)
        Dc = [r for r in Dr if r['c'] == c]
        regle_c(Dc, MS.MOYENNES_FORME[c])
        doc['direct'][c] = bilan(Dc, avec_tb=False)
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
