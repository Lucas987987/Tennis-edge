#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""clv_vs_median_offline.py — Répond au §E : la sélection du meilleur book
explique-t-elle le CLV mesuré, ou le marché bouge-t-il vraiment ? (v1 audit
v4 §Y, réécrit v2 audit v5 §AB, réécrit v3 audit v6 §AF/§AG/§AE.)

CE QUE LA VERSION D'HIER (§AF) COMPARAIT MAL : clv_book (entrée vs clôture
du book CHOISI, le max) contre clv_median (entrée vs clôture MÉDIANE).
L'entrée est un maximum sur ~20 books ; la médiane à la clôture est donc
mécaniquement inférieure à la clôture du meilleur book, indépendamment de
tout mouvement de marché -- l'écart mesuré mélangeait deux effets sans les
séparer.

LA DÉCOMPOSITION QUI RÉPOND VRAIMENT AU §E (audit v6 §AG) :
  PRIME DE SÉLECTION = entry / médiane À L'ENTRÉE (même instant, isole le
                        choix du meilleur book)
  DÉRIVE DU MARCHÉ    = médiane À L'ENTRÉE / médiane À LA CLÔTURE (isole
                        le mouvement du marché, book identique des 2 côtés)
  TOTAL = PRIME x DÉRIVE (approximativement, en %) = ce que clv_book mesure

L'instant d'entrée est reconstruit via `commence_time - lead_min` (les deux
sont dans moves_detail_hist.csv / la partition source).

Écrit clv_vs_median_report.json (audit v6 §AE : un rapport en stdout non
committé, c'est la situation exacte de Q3 avant son correctif -- resté non
lu deux mois et demi).

Usage : python scripts/clv_vs_median_offline.py
"""
import csv
import datetime
import glob
import gzip
import json
import math
import os
import random
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import match_key as mk
import curves_common as cc

SEUIL_PERTINENCE_PTS = 1.0   # audit v6 §AF.2 : un écart <1pt n'est pas actionnable
                             # même si l'IC l'exclut de zéro -- il faut les DEUX.


def _ouvrir(p):
    return gzip.open(p, 'rt', encoding='utf-8', errors='replace') \
        if p.endswith('.gz') else open(p, encoding='utf-8', errors='replace')


def _dt(s):
    """Copie locale volontaire, voir curves_common.py."""
    if not s:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', '')).timestamp()
    except (ValueError, TypeError):
        return None


def _cote_par_noms(steame, home, away):
    """Identifie le côté PAR LES NOMS -- CORRIGÉ LE 28/08/2026 (audit v6
    §AH) : la version d'hier renvoyait 'h' dès que th matchait, SANS
    vérifier que ta ne matchait pas AUSSI -- exactement l'ambiguïté
    (Zverev/Zverev, Wu/Wu) que l'étape 4 de match_key.py avait pour raison
    d'être retirée en passe 3. Risque plus faible ici (comparaison intra-
    match, pas inter-matchs) mais le principe est le même partout dans ce
    dépôt : tester LES DEUX côtés, ne renvoyer que si un seul correspond."""
    ts = mk._toks(steame)
    th, ta = mk._toks(home), mk._toks(away)
    ih = bool(ts and th and (ts <= th or th <= ts))
    ia = bool(ts and ta and (ts <= ta or ta <= ts))
    if ih and not ia:
        return 'h'
    if ia and not ih:
        return 'a'
    return None   # ambigu (ou aucun match) -> on refuse, comme partout ailleurs


def _point_a_ou_avant(points, ts_limite):
    """Dernier point de `points` (liste de (epoch, prix)) daté <= ts_limite."""
    meilleur = None
    for t, prix in points:
        if t <= ts_limite and (meilleur is None or t > meilleur[0]):
            meilleur = (t, prix)
    return meilleur[1] if meilleur else None


def charge_moves():
    moves = []
    for r in csv.DictReader(open('moves_detail_hist.csv', encoding='utf-8')):
        try:
            entry = float(r['entry'])
            lead_min = float(r['lead_min'])
        except (ValueError, KeyError, TypeError):
            continue
        nat = mk.natural_key(r.get('steame', ''), r.get('opp', ''), r.get('date'))
        if not nat[0]:
            continue
        moves.append({'nat': nat, 'entry': entry, 'lead_min': lead_min,
                      'steame': r.get('steame', ''), 'opp': r.get('opp', '')})
    return moves


def charge_courbes(besoins, closing_lines, cl_idx):
    """Ne charge QUE les matchs présents dans `besoins` (les clés naturelles
    des moves) -- pas toute la base, pour rester léger en mémoire tout en
    gardant les courbes complètes (pas juste le dernier point, il faut
    pouvoir chercher le prix À L'INSTANT DE L'ENTRÉE, pas seulement à la
    clôture)."""
    out = {}
    fichiers = sorted(glob.glob('parts/hist_book_*.jsonl') +
                      glob.glob('parts/hist_book_*.jsonl.gz'))
    print(f'  {len(fichiers)} partitions à charger (filtrées aux {len(besoins)} '
         f'matchs nécessaires)...')
    n_croises_tentes, n_croises_resolus = 0, 0
    for f in fichiers:
        with _ouvrir(f) as fh:
            for l in fh:
                try:
                    r = json.loads(l)
                except json.JSONDecodeError:
                    continue
                hc, ac = r.get('home_curve'), r.get('away_curve')
                if not hc or not ac:
                    continue
                nat = mk.natural_key(r.get('home', ''), r.get('away', ''),
                                     r.get('commence_time'))
                if nat not in besoins:
                    continue
                ct = _dt(r.get('commence_time'))
                if ct is None:
                    continue
                n_croises_tentes += 1
                cl_uid = cc.cherche_avec_tolerance(cl_idx, nat)
                ct_croise = _dt((closing_lines.get(cl_uid) or {}).get('commence_time')) \
                    if cl_uid else None
                if ct_croise:
                    n_croises_resolus += 1
                    if ct_croise < ct:
                        ct = ct_croise
                h_pre = cc.tronque_prematch(hc, ct, _dt)
                a_pre = cc.tronque_prematch(ac, ct, _dt)
                if not h_pre or not a_pre:
                    continue
                h_pts = [(_dt(p[0]), float(p[1])) for p in h_pre
                        if _dt(p[0]) is not None]
                a_pts = [(_dt(p[0]), float(p[1])) for p in a_pre
                        if _dt(p[0]) is not None]
                if not h_pts or not a_pts:
                    continue
                m = out.setdefault(nat, {'_home': r.get('home', ''),
                                         '_away': r.get('away', ''), '_ct': ct})
                m[r.get('book')] = {'h': h_pts, 'a': a_pts}
    if n_croises_tentes:
        print(f'  commence_time croisé sur {n_croises_resolus}/{n_croises_tentes} '
             f'lignes ({100*n_croises_resolus/n_croises_tentes:.0f}%)')
    return out


def _ic_bootstrap(valeurs, n_boot=3000, graine=2026828):
    n = len(valeurs)
    if n < 8:
        return st.median(valeurs) if valeurs else 0.0, None, None
    rng = random.Random(graine)
    tirages = []
    for _ in range(n_boot):
        sel = [valeurs[rng.randrange(n)] for _ in range(n)]
        tirages.append(st.median(sel))
    tirages.sort()
    return st.median(valeurs), tirages[int(0.025 * n_boot)], tirages[int(0.975 * n_boot) - 1]


def _verdict(label, med, lo, hi):
    """CORRIGÉ (audit v6 §AF.2) : IC qui exclut 0 ET taille d'effet >= seuil
    de pertinence -- l'un sans l'autre ne suffit pas. À n=661 sur une
    quantité quasi déterministe, un écart de 0,05 pt sortait déjà de l'IC
    hier ; ça ne le rendait pas actionnable."""
    if lo is None:
        return f'{label} : médiane {med:+.2f}% (n trop petit pour un IC)'
    pertinent = abs(med) >= SEUIL_PERTINENCE_PTS
    exclut_zero = lo > 0 or hi < 0
    if pertinent and exclut_zero:
        tag = '✅ effet réel et pertinent'
    elif exclut_zero:
        tag = f'⚠️ IC exclut 0 mais |médiane|<{SEUIL_PERTINENCE_PTS}pt -- pas actionnable'
    else:
        tag = '— IC traverse 0, non démontré'
    return f'{label} : médiane {med:+.2f}% [IC95 {lo:+.2f}, {hi:+.2f}] -> {tag}'


def main():
    print('PONT CLV -> P&L : décomposition prime de sélection / dérive du marché (§E, §AG)')
    closing_lines, cl_idx = cc.build_closing_index()
    moves = charge_moves()
    besoins = {mv['nat'] for mv in moves}
    print(f'  {len(moves)} moves | {len(besoins)} matchs distincts à charger')
    courbes = charge_courbes(besoins, closing_lines, cl_idx)
    print(f'  {len(courbes)} matchs trouvés dans les partitions')

    lignes = []
    n_cote_inconnu, n_incomplet = 0, 0
    for mv in moves:
        m = courbes.get(mv['nat'])
        if not m:
            n_incomplet += 1
            continue
        side = _cote_par_noms(mv['steame'], m.get('_home', ''), m.get('_away', ''))
        if side is None:
            n_cote_inconnu += 1
            continue
        ct = m['_ct']
        instant_entree = ct - mv['lead_min'] * 60

        prix_entree, prix_cloture = [], []
        for bkname, bkval in m.items():
            if bkname.startswith('_') or bkname == 'pinnacle':
                continue
            pts = bkval.get(side)
            if not pts:
                continue
            pe = _point_a_ou_avant(pts, instant_entree)
            pc = pts[-1][1]   # déjà tronqué au pré-match (clôture)
            if pe and pe > 1:
                prix_entree.append(pe)
            if pc and pc > 1:
                prix_cloture.append(pc)
        if len(prix_entree) < 3 or len(prix_cloture) < 3:
            n_incomplet += 1
            continue

        med_entree = st.median(prix_entree)
        med_cloture = st.median(prix_cloture)
        if med_entree <= 1 or med_cloture <= 1:
            continue

        prime = (mv['entry'] / med_entree - 1) * 100
        derive = (med_entree / med_cloture - 1) * 100
        lignes.append({'prime': prime, 'derive': derive,
                       'n_entree': len(prix_entree), 'n_cloture': len(prix_cloture)})

    n = len(lignes)
    print(f'\n  {n_cote_inconnu} côté(s) ambigu(s)/inconnu(s) (audit v6 §AH) | '
         f'{n_incomplet} match(s) incomplet(s) (<3 books à l\'entrée ET/ou à la clôture)')
    print(f'  {n} moves exploitables (>= 3 books à l\'entrée ET à la clôture)')

    rapport = {
        'genere_le': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'n_moves_total': len(moves), 'n_cote_ambigu': n_cote_inconnu,
        'n_incomplet': n_incomplet, 'n_exploitables': n,
    }

    if n < 30:
        print('\n  trop tôt pour conclure (<30 exploitables).')
        rapport['verdict'] = 'trop_tot'
        json.dump(rapport, open('clv_vs_median_report.json', 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        return

    primes = [x['prime'] for x in lignes]
    derives = [x['derive'] for x in lignes]

    mp, lop, hip = _ic_bootstrap(primes)
    md, lod, hid = _ic_bootstrap(derives)
    total_med = ((1 + mp / 100) * (1 + md / 100) - 1) * 100

    ligne_prime = _verdict('PRIME DE SELECTION (entry / mediane a entree)', mp, lop, hip)
    ligne_derive = _verdict('DERIVE DU MARCHE (mediane entree / mediane cloture)', md, lod, hid)
    print(f'\n  {ligne_prime}')
    print(f'  {ligne_derive}')
    print(f'\n  TOTAL (prime x dérive, ce que clv_book mesure) : {total_med:+.2f}%')
    if abs(mp) > 1e-9:
        part_prime = 100 * mp / (mp + md) if (mp + md) else 0
        print(f'  part de la prime de sélection dans le total : ~{part_prime:.0f}%')

    print(f'  %positif prime : {100*sum(1 for x in primes if x>0)/n:.0f}% | '
         f'%positif dérive : {100*sum(1 for x in derives if x>0)/n:.0f}%')
    print('\n  Rappel : ceci mesure la VALIDITÉ du CLV, pas le profit -- le '
         'journal forward reste la seule mesure directe du ROI.')

    rapport.update({
        'verdict': 'calcule',
        'prime_selection_pct': round(mp, 3), 'prime_ic95': [round(lop, 3), round(hip, 3)],
        'derive_marche_pct': round(md, 3), 'derive_ic95': [round(lod, 3), round(hid, 3)],
        'total_pct': round(total_med, 3),
        'part_prime_pct': round(part_prime, 1) if abs(mp) > 1e-9 else None,
        'pct_positif_prime': round(100*sum(1 for x in primes if x>0)/n, 1),
        'pct_positif_derive': round(100*sum(1 for x in derives if x>0)/n, 1),
    })
    json.dump(rapport, open('clv_vs_median_report.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\n  -> clv_vs_median_report.json écrit (audit v6 §AE : plus de '
         'rapport perdu en stdout).')


if __name__ == '__main__':
    main()
